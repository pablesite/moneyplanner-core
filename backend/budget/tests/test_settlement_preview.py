from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from budget.models import (
    AnnualExpenseEntry,
    MonthlyClose,
    SettlementAccount,
    SettlementOpeningBalance,
    SettlementProfile,
    SettlementSnapshot,
    SettlementWalletNormalization,
)
from budget.services_monthly_close import finalize_monthly_close, reopen_monthly_close
from budget.services_settlement_preview import (
    _allocate,
    _month_end,
    compute_monthly_close_settlement,
)
from memberships.models import (
    FamilyMember,
    Ownership,
    OwnershipAllocationSnapshot,
    OwnershipLink,
)
from net_worth.models import Asset, Liability


class SettlementPreviewTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="preview", password="pass")
        self.member_a = FamilyMember.objects.create(user=self.user, name="Pablo")
        self.member_b = FamilyMember.objects.create(user=self.user, name="Ana")
        self.individual_a = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.member_a
        )
        self.individual_b = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.member_b
        )
        self.shared = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED)
        self.shared.splits.create(member=self.member_a, percent=Decimal("50"))
        self.shared.splits.create(member=self.member_b, percent=Decimal("50"))
        self.operating, self.operating_ledger = self._account_asset(
            "Compartida", Decimal("1000"), self.shared
        )
        self.personal_a, self.personal_a_ledger = self._account_asset(
            "Personal Pablo", Decimal("100"), self.individual_a
        )
        self.personal_b, self.personal_b_ledger = self._account_asset(
            "Personal Ana", Decimal("200"), self.individual_b
        )
        self.profile = SettlementProfile.objects.create(
            user=self.user,
            is_enabled=True,
            activation_date=date(2026, 3, 1),
            base_currency="EUR",
            readiness_status=SettlementProfile.ReadinessStatus.READY,
        )
        self.operating_config = self._settlement_account(
            self.operating, SettlementAccount.Role.OPERATING
        )
        self.personal_a_config = self._settlement_account(
            self.personal_a,
            SettlementAccount.Role.PERSONAL_DESTINATION,
            member=self.member_a,
            primary=True,
        )
        self.personal_b_config = self._settlement_account(
            self.personal_b,
            SettlementAccount.Role.PERSONAL_DESTINATION,
            member=self.member_b,
            primary=True,
        )
        self._opening(self.operating_config, self.member_a, Decimal("500"))
        self._opening(self.operating_config, self.member_b, Decimal("500"))
        self._opening(self.personal_a_config, self.member_a, Decimal("100"))
        self._opening(self.personal_b_config, self.member_b, Decimal("200"))

    def _account_asset(self, name, amount, ownership):
        asset = Asset.objects.create(
            user=self.user,
            name=name,
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=amount,
            currency="EUR",
            start_date=date(2025, 1, 1),
        )
        ledger = LedgerAccount.objects.create(
            user=self.user,
            name=name,
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        asset.accounting_account_id = ledger.id
        asset.save(update_fields=["accounting_account_id"])
        OwnershipLink.objects.create(
            user=self.user,
            ownership=ownership,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=asset.id,
        )
        return asset, ledger

    def _settlement_account(self, asset, role, *, member=None, primary=False):
        return SettlementAccount.objects.create(
            profile=self.profile,
            asset=asset,
            role=role,
            member=member,
            currency="EUR",
            is_primary=primary,
        )

    def _opening(self, account, member, amount):
        SettlementOpeningBalance.objects.create(
            profile=self.profile,
            account=account,
            member=member,
            amount=amount,
            currency="EUR",
        )

    def _flow(self, *, booking_date, amount, ownership, cash_account, family, description):
        counterparty = LedgerAccount.objects.create(
            user=self.user,
            name=f"{family}-{description}",
            account_type=(
                LedgerAccount.AccountType.INCOME
                if family == LedgerEntry.FlowFamily.INCOME
                else LedgerAccount.AccountType.EXPENSE
            ),
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=booking_date,
            value_date=booking_date,
            description=description,
            status=LedgerTransaction.Status.POSTED,
            ownership=ownership,
            quick_entry_kind=(
                LedgerTransaction.QuickEntryKind.INCOME
                if family == LedgerEntry.FlowFamily.INCOME
                else LedgerTransaction.QuickEntryKind.EXPENSE
            ),
        )
        if family == LedgerEntry.FlowFamily.INCOME:
            cash_side, flow_side = LedgerEntry.Side.DEBIT, LedgerEntry.Side.CREDIT
        else:
            cash_side, flow_side = LedgerEntry.Side.CREDIT, LedgerEntry.Side.DEBIT
        LedgerEntry.objects.create(
            transaction=tx,
            account=cash_account,
            side=cash_side,
            amount=amount,
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=counterparty,
            side=flow_side,
            amount=amount,
            currency="EUR",
            flow_family=family,
            category_key="salary"
            if family == LedgerEntry.FlowFamily.INCOME
            else "consumption_expenses",
            subcategory_key="employee_salary"
            if family == LedgerEntry.FlowFamily.INCOME
            else "living_expenses",
        )
        return tx

    def _transfer(self, *, amount, source, destination):
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 20),
            value_date=date(2026, 3, 20),
            description="Transferencia interna",
            status=LedgerTransaction.Status.POSTED,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=source,
            side=LedgerEntry.Side.CREDIT,
            amount=amount,
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=destination,
            side=LedgerEntry.Side.DEBIT,
            amount=amount,
            currency="EUR",
        )

    def _ordinary_reserve(self):
        return AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Casa",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT,
            cashflow_role=AnnualExpenseEntry.CashflowRole.OPERATING,
            amount_annual=Decimal("1200"),
            fiscal_year=2026,
            currency="EUR",
            ownership=self.shared,
            settlement_account=self.operating_config,
        )

    def test_aggregate_ordinary_budget_uses_the_only_operating_account(self):
        entry = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Mantenimiento agregado",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT,
            cashflow_role=AnnualExpenseEntry.CashflowRole.OPERATING,
            amount_annual=Decimal("1200"),
            fiscal_year=2026,
            currency="EUR",
        )

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        self.assertEqual(result["status"], "ready", result["quality"])
        reserve = next(row for row in result["reserves"] if row["entry_id"] == entry.id)
        self.assertEqual(reserve["settlement_account_id"], self.operating_config.id)
        self.assertEqual(reserve["ownership_id"], self.shared.id)
        self.assertEqual([row["amount"] for row in reserve["members"]], ["50.00", "50.00"])

    def test_cross_payments_and_internal_transfer_reconcile(self):
        self._ordinary_reserve()
        salary = self._flow(
            booking_date=date(2026, 3, 5),
            amount=Decimal("1000"),
            ownership=self.individual_a,
            cash_account=self.operating_ledger,
            family=LedgerEntry.FlowFamily.INCOME,
            description="Nomina Pablo",
        )
        meal = self._flow(
            booking_date=date(2026, 3, 10),
            amount=Decimal("100"),
            ownership=self.shared,
            cash_account=self.personal_a_ledger,
            family=LedgerEntry.FlowFamily.EXPENSE,
            description="Comida familiar",
        )
        self._transfer(
            amount=Decimal("50"),
            source=self.operating_ledger,
            destination=self.personal_b_ledger,
        )
        self.operating.amount = Decimal("1950")
        self.operating.save(update_fields=["amount"])
        self.personal_a.amount = Decimal("0")
        self.personal_a.save(update_fields=["amount"])
        self.personal_b.amount = Decimal("250")
        self.personal_b.save(update_fields=["amount"])

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        self.assertEqual(result["status"], "ready", result["quality"])
        self.assertEqual(result["reconciliation"]["physical_total"], "2200.00")
        self.assertEqual(result["reconciliation"]["economic_total"], "2200.00")
        balances = {row["member_id"]: row for row in result["economic_balances"]}
        self.assertEqual(
            balances[self.member_a.id],
            {
                "member_id": self.member_a.id,
                "opening": "600.00",
                "income": "1000.00",
                "expense": "50.00",
                "compensation": "550.00",
                "requirement": "50.00",
                "closing": "1550.00",
                "excess": "1500.00",
            },
        )
        self.assertEqual(
            balances[self.member_b.id],
            {
                "member_id": self.member_b.id,
                "opening": "700.00",
                "income": "0.00",
                "expense": "50.00",
                "compensation": "-550.00",
                "requirement": "50.00",
                "closing": "650.00",
                "excess": "600.00",
            },
        )
        by_tx = {row["transaction_id"]: row for row in result["compensations"]}
        self.assertEqual(
            by_tx[salary.id]["members"],
            [
                {"member_id": self.member_a.id, "amount": "500.00"},
                {"member_id": self.member_b.id, "amount": "-500.00"},
            ],
        )
        self.assertEqual(
            by_tx[meal.id]["members"],
            [
                {"member_id": self.member_a.id, "amount": "50.00"},
                {"member_id": self.member_b.id, "amount": "-50.00"},
            ],
        )
        self.assertNotIn(
            "Transferencia interna", {row["description"] for row in result["compensations"]}
        )
        self.assertEqual(
            sum(Decimal(row["amount"]) for row in result["recommendations"]), Decimal("1850.00")
        )

    def test_credit_card_debt_is_automatic_and_monthly_payment_is_internal(self):
        card = Liability.objects.create(
            user=self.user,
            name="Tarjeta compartida",
            category=Liability.Category.CREDIT_CARD,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            amount=Decimal("0"),
            currency="EUR",
            start_date=date(2020, 1, 1),
        )
        card_ledger = LedgerAccount.objects.create(
            user=self.user,
            name=card.name,
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=card,
        )
        card.accounting_account_id = card_ledger.id
        card.save(update_fields=["accounting_account_id"])
        OwnershipLink.objects.create(
            user=self.user,
            ownership=self.shared,
            target_type=OwnershipLink.TargetType.LIABILITY,
            target_id=card.id,
        )

        # Existing debt is part of the activation net position, not August spending.
        opening = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 1),
            value_date=date(2026, 3, 1),
            description="Deuda inicial tarjeta",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=card_ledger,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("100"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening,
            account=LedgerAccount.objects.create(
                user=self.user,
                name="Contrapartida inicial tarjeta",
                account_type=LedgerAccount.AccountType.EQUITY,
                currency="EUR",
            ),
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100"),
            currency="EUR",
        )
        self._flow(
            booking_date=date(2026, 3, 10),
            amount=Decimal("50"),
            ownership=self.shared,
            cash_account=card_ledger,
            family=LedgerEntry.FlowFamily.EXPENSE,
            description="Compra con tarjeta",
        )
        self._transfer(amount=Decimal("100"), source=self.operating_ledger, destination=card_ledger)
        self.operating.amount = Decimal("900")
        self.operating.save(update_fields=["amount"])

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        self.assertEqual(result["status"], "ready", result["quality"])
        card_row = next(row for row in result["accounts"] if row["liability_id"] == card.id)
        self.assertEqual(card_row["opening"], "-100.00")
        self.assertEqual(card_row["physical_delta"], "50.00")
        self.assertEqual(card_row["observed_close"], "-50.00")
        self.assertEqual(result["reconciliation"]["physical_total"], "1150.00")
        self.assertEqual(result["reconciliation"]["economic_total"], "1150.00")
        balances = {row["member_id"]: row for row in result["economic_balances"]}
        self.assertEqual(balances[self.member_a.id]["expense"], "25.00")
        self.assertEqual(balances[self.member_b.id]["expense"], "25.00")

    def test_broker_cash_and_investment_position_keep_funding_inside_perimeter(self):
        broker, broker_ledger = self._account_asset(
            "Efectivo bróker", Decimal("0"), self.individual_a
        )
        investment = Asset.objects.create(
            user=self.user,
            name="ETF de Pablo",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            amount=Decimal("0"),
            currency="EUR",
            start_date=date(2020, 1, 1),
        )
        investment_ledger = LedgerAccount.objects.create(
            user=self.user,
            name=investment.name,
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment,
        )
        investment.accounting_account_id = investment_ledger.id
        investment.save(update_fields=["accounting_account_id"])
        OwnershipLink.objects.create(
            user=self.user,
            ownership=self.individual_a,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=investment.id,
        )
        self._transfer(
            amount=Decimal("100"), source=self.operating_ledger, destination=broker_ledger
        )
        contribution = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 20),
            value_date=date(2026, 3, 20),
            description="Compra ETF",
            status=LedgerTransaction.Status.POSTED,
            ownership=self.individual_a,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.INFLOW,
        )
        LedgerEntry.objects.create(
            transaction=contribution,
            account=broker_ledger,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("100"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=contribution,
            account=investment_ledger,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="financial_investments",
            subcategory_key="etf",
        )
        self.operating.amount = Decimal("900")
        self.operating.save(update_fields=["amount"])

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        self.assertEqual(result["status"], "ready", result["quality"])
        positions = {row["name"]: row for row in result["accounts"]}
        self.assertEqual(positions["Efectivo bróker"]["role"], "investment_cash")
        self.assertEqual(positions["ETF de Pablo"]["role"], "investment_position")
        self.assertEqual(positions["Efectivo bróker"]["observed_close"], "0.00")
        self.assertEqual(positions["ETF de Pablo"]["observed_close"], "100.00")

    def test_wallet_normalization_closes_the_modeled_gap_without_moving_physical_cash(self):
        wallet_a, wallet_a_ledger = self._account_asset(
            "Monedero Pablo", Decimal("0"), self.individual_a
        )
        wallet_a.subcategory = Asset.Subcategory.WALLET
        wallet_a.save(update_fields=["subcategory"])
        wallet_shared, wallet_shared_ledger = self._account_asset(
            "Monedero compartido", Decimal("20"), self.shared
        )
        wallet_shared.subcategory = Asset.Subcategory.WALLET
        wallet_shared.save(update_fields=["subcategory"])
        wallet_a_config = self._settlement_account(wallet_a, SettlementAccount.Role.PHYSICAL_CASH)
        wallet_a_config.accepted_physical_balance = Decimal("0")
        wallet_a_config.modeled_balance_at_activation = Decimal("100")
        wallet_a_config.save(
            update_fields=["accepted_physical_balance", "modeled_balance_at_activation"]
        )
        wallet_shared_config = self._settlement_account(
            wallet_shared, SettlementAccount.Role.PHYSICAL_CASH
        )
        wallet_shared_config.accepted_physical_balance = Decimal("20")
        wallet_shared_config.modeled_balance_at_activation = Decimal("-80")
        wallet_shared_config.save(
            update_fields=["accepted_physical_balance", "modeled_balance_at_activation"]
        )
        self._opening(wallet_a_config, self.member_a, Decimal("0"))
        self._opening(wallet_shared_config, self.member_a, Decimal("10"))
        self._opening(wallet_shared_config, self.member_b, Decimal("10"))
        normalization = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 5),
            value_date=date(2026, 3, 5),
            description="Cierre del monedero virtual",
            status=LedgerTransaction.Status.POSTED,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
        )
        LedgerEntry.objects.create(
            transaction=normalization,
            account=wallet_a_ledger,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("100"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=normalization,
            account=wallet_shared_ledger,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100"),
            currency="EUR",
        )
        SettlementWalletNormalization.objects.create(
            profile=self.profile, transaction=normalization
        )

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        self.assertEqual(result["status"], "ready", result["quality"])
        wallets = {row["name"]: row for row in result["accounts"] if row["role"] == "physical_cash"}
        self.assertEqual(wallets["Monedero Pablo"]["observed_close"], "0.00")
        self.assertEqual(wallets["Monedero Pablo"]["physical_delta"], "0.00")
        self.assertEqual(wallets["Monedero Pablo"]["normalization_delta"], "-100.00")
        self.assertEqual(wallets["Monedero compartido"]["observed_close"], "20.00")

        march_close = MonthlyClose.objects.create(
            user=self.user,
            fiscal_year=2026,
            month=3,
            status=MonthlyClose.Status.FINALIZED,
        )
        SettlementSnapshot.objects.create(
            monthly_close=march_close,
            profile=self.profile,
            status=SettlementSnapshot.Status.READY,
            base_currency="EUR",
            period_start=date(2026, 3, 2),
            period_end=date(2026, 3, 31),
            target_year=2026,
            target_month=4,
            opening_source="activation",
            source_hash="wallet-normalized",
            account_balances=result["accounts"],
        )

        april = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=4)
        april_wallets = {
            row["name"]: row for row in april["accounts"] if row["role"] == "physical_cash"
        }
        self.assertEqual(april["status"], "ready", april["quality"])
        self.assertEqual(april_wallets["Monedero Pablo"]["observed_close"], "0.00")
        self.assertEqual(april_wallets["Monedero compartido"]["observed_close"], "20.00")

    def test_dynamic_split_and_fixed_allocation_reconcile_to_cent(self):
        self.shared.allocation_basis = Ownership.AllocationBasis.RECURRING_INCOME_12M
        self.shared.save(update_fields=["allocation_basis"])
        for year, month in [(2025, month) for month in range(3, 13)] + [(2026, 1), (2026, 2)]:
            for ownership, amount, label in (
                (self.individual_a, Decimal("610"), "Pablo"),
                (self.individual_b, Decimal("390"), "Ana"),
            ):
                income = LedgerAccount.objects.create(
                    user=self.user,
                    name=f"Historico {label} {year}-{month}",
                    account_type=LedgerAccount.AccountType.INCOME,
                    currency="EUR",
                )
                tx = LedgerTransaction.objects.create(
                    user=self.user,
                    booking_date=date(year, month, 15),
                    value_date=date(year, month, 15),
                    description=f"Nomina historica {label}",
                    ownership=ownership,
                )
                LedgerEntry.objects.create(
                    transaction=tx,
                    account=income,
                    side=LedgerEntry.Side.CREDIT,
                    amount=amount,
                    currency="EUR",
                    flow_family=LedgerEntry.FlowFamily.INCOME,
                    category_key="salary",
                    subcategory_key="employee_salary",
                )
        investment_ownership = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED)
        investment_ownership.splits.create(member=self.member_a, percent=Decimal("50"))
        investment_ownership.splits.create(member=self.member_b, percent=Decimal("50"))
        investment, _investment_ledger = self._account_asset(
            "MyInvestor", Decimal("0"), investment_ownership
        )
        investment.category = Asset.Category.INVESTMENTS
        investment.save(update_fields=["category"])
        investment_config = self._settlement_account(
            investment, SettlementAccount.Role.ALLOCATION_DESTINATION
        )
        self._ordinary_reserve()
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Aportacion MyInvestor",
            category=AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
            subcategory="etf_indexed",
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT,
            cashflow_role=AnnualExpenseEntry.CashflowRole.INVESTMENT,
            amount_annual=Decimal("2400"),
            fiscal_year=2026,
            currency="EUR",
            ownership=investment_ownership,
            settlement_account=investment_config,
        )
        self._flow(
            booking_date=date(2026, 3, 5),
            amount=Decimal("610"),
            ownership=self.individual_a,
            cash_account=self.operating_ledger,
            family=LedgerEntry.FlowFamily.INCOME,
            description="Nomina marzo Pablo",
        )
        self._flow(
            booking_date=date(2026, 3, 6),
            amount=Decimal("390"),
            ownership=self.individual_b,
            cash_account=self.operating_ledger,
            family=LedgerEntry.FlowFamily.INCOME,
            description="Nomina marzo Ana",
        )
        self.operating.amount = Decimal("2000")
        self.operating.save(update_fields=["amount"])

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        self.assertEqual(result["status"], "ready", result["quality"])
        reserve = next(row for row in result["reserves"] if row["kind"] == "reserve")
        allocation = next(row for row in result["reserves"] if row["kind"] == "allocation")
        self.assertEqual([row["amount"] for row in reserve["members"]], ["61.00", "39.00"])
        self.assertEqual([row["amount"] for row in allocation["members"]], ["100.00", "100.00"])
        self.assertEqual(result["reconciliation"]["economic_vs_target"], "0.00")

        close = MonthlyClose.objects.create(user=self.user, fiscal_year=2026, month=3)
        finalized = finalize_monthly_close(monthly_close=close, user=self.user)
        dynamic_snapshots = OwnershipAllocationSnapshot.objects.filter(ownership=self.shared)
        self.assertTrue(dynamic_snapshots.exists())
        self.assertFalse(dynamic_snapshots.filter(is_frozen=False).exists())
        reopen_monthly_close(monthly_close=finalized)
        self.assertFalse(dynamic_snapshots.filter(is_frozen=True).exists())

    def test_individual_expense_from_shared_account_charges_only_that_member(self):
        self._ordinary_reserve()
        expense = self._flow(
            booking_date=date(2026, 3, 12),
            amount=Decimal("100"),
            ownership=self.individual_b,
            cash_account=self.operating_ledger,
            family=LedgerEntry.FlowFamily.EXPENSE,
            description="Compra personal Ana",
        )
        self.operating.amount = Decimal("900")
        self.operating.save(update_fields=["amount"])

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        balances = {row["member_id"]: row["closing"] for row in result["economic_balances"]}
        self.assertEqual(balances[self.member_a.id], "600.00")
        self.assertEqual(balances[self.member_b.id], "600.00")
        compensation = next(
            row for row in result["compensations"] if row["transaction_id"] == expense.id
        )
        self.assertEqual(
            compensation["members"],
            [
                {"member_id": self.member_a.id, "amount": "50.00"},
                {"member_id": self.member_b.id, "amount": "-50.00"},
            ],
        )

    def test_insufficient_member_balance_routes_an_inverse_contribution(self):
        self._ordinary_reserve()
        self._flow(
            booking_date=date(2026, 3, 12),
            amount=Decimal("800"),
            ownership=self.individual_b,
            cash_account=self.operating_ledger,
            family=LedgerEntry.FlowFamily.EXPENSE,
            description="Gasto personal grande Ana",
        )
        self.operating.amount = Decimal("200")
        self.operating.save(update_fields=["amount"])

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        personal_b_target = next(
            row for row in result["accounts"] if row["account_id"] == self.personal_b_config.id
        )
        self.assertEqual(personal_b_target["target_close"], "-150.00")
        self.assertTrue(
            any(
                row["from_account_id"] == self.personal_b_config.id
                for row in result["recommendations"]
            )
        )

    def test_explicit_route_selects_between_equivalent_operating_accounts(self):
        second_asset, _second_ledger = self._account_asset(
            "Compartida ahorro", Decimal("0"), self.shared
        )
        second_config = self._settlement_account(second_asset, SettlementAccount.Role.OPERATING)
        self._opening(second_config, self.member_a, Decimal("0"))
        self._opening(second_config, self.member_b, Decimal("0"))
        entry = self._ordinary_reserve()
        entry.settlement_account = second_config
        entry.save(update_fields=["settlement_account"])

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        reserve = result["reserves"][0]
        self.assertEqual(reserve["settlement_account_id"], second_config.id)
        self.assertTrue(
            any(
                row["from_account_id"] == self.operating_config.id
                and row["to_account_id"] == second_config.id
                for row in result["recommendations"]
            )
        )

    def test_next_month_includes_active_term_commitment_and_excludes_one_off(self):
        term = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Prestamo temporal",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            term_start_month=4,
            term_end_month=6,
            term_end_year=2026,
            amount_annual=Decimal("300"),
            fiscal_year=2026,
            currency="EUR",
            ownership=self.shared,
            settlement_account=self.operating_config,
        )
        one_off = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Viaje puntual",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            expense_type=AnnualExpenseEntry.ExpenseType.ONE_OFF,
            time_profile=AnnualExpenseEntry.TimeProfile.ONE_OFF,
            cashflow_role=AnnualExpenseEntry.CashflowRole.OPERATING,
            target_month=4,
            amount_annual=Decimal("500"),
            fiscal_year=2026,
            currency="EUR",
            ownership=self.shared,
            settlement_account=self.operating_config,
        )

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        entry_ids = {row["entry_id"] for row in result["reserves"]}
        self.assertIn(term.id, entry_ids)
        self.assertNotIn(one_off.id, entry_ids)

    def test_query_count_is_constant_for_ten_thousand_movements(self):
        self._ordinary_reserve()
        income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos masivos",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        transactions = LedgerTransaction.objects.bulk_create(
            [
                LedgerTransaction(
                    user=self.user,
                    booking_date=date(2026, 3, (index % 28) + 2),
                    value_date=date(2026, 3, (index % 28) + 2),
                    description=f"Ingreso {index}",
                    status=LedgerTransaction.Status.POSTED,
                    ownership=self.individual_a,
                    quick_entry_kind=LedgerTransaction.QuickEntryKind.INCOME,
                )
                for index in range(10_000)
            ]
        )
        LedgerEntry.objects.bulk_create(
            [
                entry
                for tx in transactions
                for entry in (
                    LedgerEntry(
                        transaction=tx,
                        account=self.operating_ledger,
                        side=LedgerEntry.Side.DEBIT,
                        amount=Decimal("0.01"),
                        currency="EUR",
                    ),
                    LedgerEntry(
                        transaction=tx,
                        account=income_account,
                        side=LedgerEntry.Side.CREDIT,
                        amount=Decimal("0.01"),
                        currency="EUR",
                        flow_family=LedgerEntry.FlowFamily.INCOME,
                        category_key="salary",
                        subcategory_key="employee_salary",
                    ),
                )
            ],
            batch_size=2000,
        )
        self.operating.amount = Decimal("1100")
        self.operating.save(update_fields=["amount"])

        with CaptureQueriesContext(connection) as queries:
            result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)

        self.assertEqual(result["status"], "ready", result["quality"])
        self.assertLess(len(queries), 80)

    def test_finalize_freezes_and_reopen_recalculates(self):
        self._ordinary_reserve()
        close = MonthlyClose.objects.create(user=self.user, fiscal_year=2026, month=3)
        finalize_monthly_close(monthly_close=close, user=self.user)
        frozen = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)
        self.assertEqual(frozen["status"], "finalized")
        self.assertTrue(frozen["is_frozen"])
        self.assertTrue(SettlementSnapshot.objects.filter(monthly_close=close).exists())

        self.operating.amount = Decimal("9999")
        self.operating.save(update_fields=["amount"])
        unchanged = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)
        self.assertEqual(unchanged["source_hash"], frozen["source_hash"])

        reopen_monthly_close(monthly_close=close)
        recalculated = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=3)
        self.assertFalse(SettlementSnapshot.objects.filter(monthly_close=close).exists())
        self.assertEqual(recalculated["status"], "not_ready")

    def test_non_consecutive_close_advances_from_previous_snapshot(self):
        self._ordinary_reserve()
        march = MonthlyClose.objects.create(user=self.user, fiscal_year=2026, month=3)
        finalize_monthly_close(monthly_close=march, user=self.user)
        self._flow(
            booking_date=date(2026, 4, 15),
            amount=Decimal("100"),
            ownership=self.individual_a,
            cash_account=self.operating_ledger,
            family=LedgerEntry.FlowFamily.INCOME,
            description="Ingreso abril",
        )
        self.operating.amount = Decimal("1100")
        self.operating.save(update_fields=["amount"])

        result = compute_monthly_close_settlement(user=self.user, fiscal_year=2026, month=5)

        self.assertEqual(result["status"], "ready", result["quality"])
        self.assertEqual(result["period"]["start"], "2026-04-01")
        self.assertEqual(result["reconciliation"]["economic_total"], "1400.00")

    def test_not_ready_settlement_does_not_block_finalize(self):
        self.operating_config.delete()
        close = MonthlyClose.objects.create(user=self.user, fiscal_year=2026, month=3)

        finalized = finalize_monthly_close(monthly_close=close, user=self.user)

        self.assertEqual(finalized.status, MonthlyClose.Status.FINALIZED)
        self.assertEqual(finalized.settlement_snapshot.status, SettlementSnapshot.Status.NOT_READY)


class DisabledSettlementRegressionTests(APITestCase):
    def test_monthly_close_payload_remains_available_without_profile(self):
        user = get_user_model().objects.create_user(username="disabled", password="pass")

        result = compute_monthly_close_settlement(user=user, fiscal_year=2026, month=3)

        self.assertEqual(result["status"], "disabled")


class SettlementMathTests(SimpleTestCase):
    def test_three_member_rounding_and_leap_month_end_are_deterministic(self):
        allocated = _allocate(
            Decimal("100"),
            {1: Decimal("33.33"), 2: Decimal("33.33"), 3: Decimal("33.34")},
        )

        self.assertEqual(allocated, {1: Decimal("33.33"), 2: Decimal("33.33"), 3: Decimal("33.34")})
        self.assertEqual(sum(allocated.values()), Decimal("100.00"))
        self.assertEqual(_month_end(2028, 2), date(2028, 2, 29))
