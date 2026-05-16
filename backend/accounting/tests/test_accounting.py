from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounting.services_budget import build_budget_derived_suggestions
from accounting.services_ledger import (
    ensure_net_worth_opening_balance_transaction,
    get_account_balance,
)
from accounting.services_summaries import (
    build_account_balances_summary,
    build_monthly_accounting_summary,
)
from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from core.models import FxRate
from memberships.models import FamilyMember, Ownership, OwnershipLink, OwnershipSplit
from net_worth.models import Asset, Liability


class AccountingServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="acct_user", password="pass1234")

    def test_get_account_balance_uses_account_nature(self):
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Caja",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income = LedgerAccount.objects.create(
            user=self.user,
            name="Nomina",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Cobro",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )

        self.assertEqual(get_account_balance(account=cash), Decimal("1000.00"))
        self.assertEqual(get_account_balance(account=income), Decimal("1000.00"))

    def test_get_account_balance_can_be_cut_by_date_and_status(self):
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Caja",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income = LedgerAccount.objects.create(
            user=self.user,
            name="Ventas",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        posted_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Cobro febrero",
            status=LedgerTransaction.Status.POSTED,
        )
        draft_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 5),
            value_date=date(2026, 3, 5),
            description="Borrador marzo",
            status=LedgerTransaction.Status.DRAFT,
        )
        for tx, amount in ((posted_tx, Decimal("1000.00")), (draft_tx, Decimal("300.00"))):
            LedgerEntry.objects.create(
                transaction=tx,
                account=cash,
                side=LedgerEntry.Side.DEBIT,
                amount=amount,
                currency="EUR",
            )
            LedgerEntry.objects.create(
                transaction=tx,
                account=income,
                side=LedgerEntry.Side.CREDIT,
                amount=amount,
                currency="EUR",
            )

        self.assertEqual(
            get_account_balance(
                account=cash,
                as_of_date=date(2026, 2, 28),
                status=LedgerTransaction.Status.POSTED,
            ),
            Decimal("1000.00"),
        )
        self.assertEqual(get_account_balance(account=cash), Decimal("1300.00"))

    def test_build_monthly_summary_aggregates_category_first_entries(self):
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Alquiler",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="housing_home",
            amount_annual=Decimal("7200.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        expense = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        tx_income = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 5),
            value_date=date(2026, 1, 5),
            description="Nomina enero",
        )
        LedgerEntry.objects.create(
            transaction=tx_income,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_income,
            account=income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="salary",
            subcategory_key="employee_salary",
        )

        tx_expense = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 8),
            value_date=date(2026, 1, 8),
            description="Alquiler enero",
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=expense,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("600.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="housing_home",
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=cash,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("600.00"),
            currency="EUR",
        )

        summary = build_monthly_accounting_summary(user_id=self.user.id, fiscal_year=2026)
        january = summary["months"][0]
        self.assertEqual(january["income_total"], "1000.00")
        self.assertEqual(january["expense_total"], "600.00")

    def test_build_budget_derived_suggestions_returns_stable_monthly_series_from_ledger_taxonomy(
        self,
    ):
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("24000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Supermercado",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            amount_annual=Decimal("7200.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingreso",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gasto",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        tx_income_1 = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 12, 5),
            value_date=date(2025, 12, 5),
            description="Nomina dic",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_income_1,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1500.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_income_1,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1500.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="salary",
            subcategory_key="employee_salary",
        )

        tx_income_2 = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 5),
            value_date=date(2026, 1, 5),
            description="Nomina ene",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_income_2,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1500.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_income_2,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1500.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="salary",
            subcategory_key="employee_salary",
        )

        tx_expense = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 3),
            value_date=date(2026, 2, 3),
            description="Supermercado",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("400.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="living_expenses",
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=cash,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("400.00"),
            currency="EUR",
        )

        suggestions = build_budget_derived_suggestions(
            user_id=self.user.id,
            fiscal_year=2026,
            lookback_years=2,
        )
        self.assertEqual(suggestions["window_months"], 24)
        self.assertEqual(len(suggestions["income"]["series"]), 24)
        self.assertEqual(len(suggestions["expense"]["series"]), 24)

        income_sub = suggestions["income"]["subcategories"][0]
        self.assertEqual(income_sub["category"], "salary")
        self.assertEqual(income_sub["subcategory"], "employee_salary")
        self.assertEqual(income_sub["window_total"], "3000.00")
        self.assertEqual(income_sub["suggested_annual"], "1500.00")
        self.assertEqual(income_sub["observed_months"], 2)

        expense_sub = suggestions["expense"]["subcategories"][0]
        self.assertEqual(expense_sub["category"], "consumption_expenses")
        self.assertEqual(expense_sub["subcategory"], "living_expenses")
        self.assertEqual(expense_sub["window_total"], "400.00")
        self.assertEqual(expense_sub["suggested_annual"], "200.00")
        self.assertEqual(expense_sub["observed_months"], 1)

    def test_build_account_balances_summary_handles_multiple_accounts_and_foreign_currency(self):
        euro_cash = LedgerAccount.objects.create(
            user=self.user,
            name="Caja EUR",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        euro_income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos EUR",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        usd_cash = LedgerAccount.objects.create(
            user=self.user,
            name="Caja USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )
        usd_income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos USD",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="USD",
        )

        euro_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 3),
            value_date=date(2026, 4, 3),
            description="Ingreso EUR",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=euro_tx,
            account=euro_cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=euro_tx,
            account=euro_income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )

        usd_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 4),
            value_date=date(2026, 4, 4),
            description="Ingreso USD",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=usd_tx,
            account=usd_cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("250.00"),
            currency="USD",
        )
        LedgerEntry.objects.create(
            transaction=usd_tx,
            account=usd_income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("250.00"),
            currency="USD",
        )

        summary = build_account_balances_summary(
            user_id=self.user.id,
            fiscal_year=2026,
            month=4,
            account_type=LedgerAccount.AccountType.ASSET,
        )

        self.assertEqual(summary["filters"]["year"], 2026)
        self.assertEqual(summary["filters"]["month"], 4)
        self.assertEqual(summary["filters"]["account_type"], LedgerAccount.AccountType.ASSET)
        self.assertEqual(summary["totals_by_account_type"]["asset"], "1250.00")
        self.assertEqual(len(summary["accounts"]), 2)

        accounts_by_id = {row["account_id"]: row for row in summary["accounts"]}
        self.assertEqual(accounts_by_id[euro_cash.id]["currency"], "EUR")
        self.assertEqual(accounts_by_id[euro_cash.id]["current_balance"], "1000.00000000")
        self.assertEqual(accounts_by_id[euro_cash.id]["period_net_change"], "1000.00")
        self.assertEqual(accounts_by_id[usd_cash.id]["currency"], "USD")
        self.assertEqual(accounts_by_id[usd_cash.id]["current_balance"], "250.00000000")
        self.assertEqual(accounts_by_id[usd_cash.id]["period_net_change"], "250.00")

    def test_build_account_balances_summary_with_accounts_of_different_types(self):
        asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Caja",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Tarjeta",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
        )

        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 5, 12),
            value_date=date(2026, 5, 12),
            description="Movimiento mixto",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=asset_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("500.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=liability_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("200.00"),
            currency="EUR",
        )

        summary = build_account_balances_summary(
            user_id=self.user.id,
            fiscal_year=2026,
            month=5,
        )

        accounts_by_id = {row["account_id"]: row for row in summary["accounts"]}
        self.assertEqual(summary["totals_by_account_type"]["asset"], "500.00")
        self.assertEqual(summary["totals_by_account_type"]["liability"], "200.00")
        self.assertEqual(accounts_by_id[asset_account.id]["current_balance"], "500.00000000")
        self.assertEqual(accounts_by_id[liability_account.id]["current_balance"], "200.00000000")

    def test_build_account_balances_summary_includes_foreign_currency_accounts(self):
        usd_cash = LedgerAccount.objects.create(
            user=self.user,
            name="Caja USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )

        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 6, 7),
            value_date=date(2026, 6, 7),
            description="Ingreso USD",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=usd_cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("125.00"),
            currency="USD",
        )

        summary = build_account_balances_summary(
            user_id=self.user.id,
            fiscal_year=2026,
            month=6,
        )

        self.assertEqual(len(summary["accounts"]), 1)
        self.assertEqual(summary["accounts"][0]["currency"], "USD")
        self.assertEqual(summary["accounts"][0]["current_balance"], "125.00000000")

    def test_build_account_balances_summary_includes_investment_contributed_totals(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Cartera indexada",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("0.00"),
            is_active=True,
        )
        cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta corriente",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker indexado",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )

        tx_inflow = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 6, 1),
            value_date=date(2026, 6, 1),
            description="Aporte cartera",
            status=LedgerTransaction.Status.POSTED,
            quick_entry_kind="investment",
            investment_direction="inflow",
        )
        LedgerEntry.objects.create(
            transaction=tx_inflow,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("500.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=tx_inflow,
            account=cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("500.00"),
            currency="EUR",
        )

        tx_outflow = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 6, 20),
            value_date=date(2026, 6, 20),
            description="Desinversion parcial",
            status=LedgerTransaction.Status.POSTED,
            quick_entry_kind="investment",
            investment_direction="outflow",
        )
        LedgerEntry.objects.create(
            transaction=tx_outflow,
            account=cash_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("200.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_outflow,
            account=investment_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("200.00"),
            currency="EUR",
            asset=investment_asset,
        )

        summary = build_account_balances_summary(
            user_id=self.user.id,
            fiscal_year=2026,
            month=6,
            account_type=LedgerAccount.AccountType.ASSET,
        )
        by_id = {row["account_id"]: row for row in summary["accounts"]}
        investment_row = by_id[investment_account.id]
        self.assertEqual(investment_row["investment_inflow_total"], "500.00")
        self.assertEqual(investment_row["investment_outflow_total"], "200.00")
        self.assertEqual(investment_row["investment_net_contributed"], "300.00")

    def test_ensure_net_worth_opening_balance_transaction_creates_once_and_is_idempotent(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Vivienda",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1234.56"),
            is_active=True,
        )
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta vivienda",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )

        first_transaction = ensure_net_worth_opening_balance_transaction(
            user=self.user,
            account=account,
            amount=Decimal("1234.56"),
            booking_date=date(2026, 1, 15),
            asset=asset,
        )
        second_transaction = ensure_net_worth_opening_balance_transaction(
            user=self.user,
            account=account,
            amount=Decimal("1234.56"),
            booking_date=date(2026, 1, 15),
            asset=asset,
        )

        self.assertIsNotNone(first_transaction)
        self.assertEqual(first_transaction.id, second_transaction.id)
        self.assertEqual(
            LedgerTransaction.objects.filter(
                user=self.user,
                origin=LedgerTransaction.Origin.SYSTEM,
                notes=f"net_worth_opening_balance:asset:{asset.id}",
            ).count(),
            1,
        )
        self.assertEqual(LedgerEntry.objects.filter(transaction=first_transaction).count(), 2)
        self.assertTrue(
            LedgerEntry.objects.filter(transaction=first_transaction, account=account).exists()
        )
        self.assertTrue(
            LedgerAccount.objects.filter(
                user=self.user,
                account_type=LedgerAccount.AccountType.EQUITY,
                origin=LedgerAccount.Origin.SYSTEM,
            ).exists()
        )


class AccountingApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="acct_api_user",
            password="pass1234",
        )
        self.client.force_authenticate(user=self.user)
        self.cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta corriente",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        self.income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos salariales",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )

    def test_create_balanced_transaction_and_list_entries(self):
        create_res = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-15",
                "value_date": "2026-02-15",
                "description": "Nomina febrero",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": self.cash_account.id,
                        "side": "debit",
                        "amount": "2100.00",
                        "currency": "eur",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "2100.00",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "salary",
                        "subcategory_key": "employee_salary",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(len(create_res.data["entries"]), 2)
        classified_entry = next(
            row for row in create_res.data["entries"] if row["account_id"] == self.income_account.id
        )
        self.assertEqual(classified_entry["flow_family"], "income")
        self.assertEqual(classified_entry["category_key"], "salary")
        self.assertEqual(classified_entry["subcategory_key"], "employee_salary")

        accounts_res = self.client.get("/api/accounting/accounts/")
        self.assertEqual(accounts_res.status_code, status.HTTP_200_OK)
        self.assertEqual(accounts_res.data[0]["current_balance"], "2100.00000000")

        entries_res = self.client.get("/api/accounting/entries/")
        self.assertEqual(entries_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(entries_res.data), 2)
        self.assertTrue(any(entry["flow_family"] == "income" for entry in entries_res.data))

    def test_transaction_entries_include_amount_converted_to_user_base_currency(self):
        crypto_account = LedgerAccount.objects.create(
            user=self.user,
            name="Bitcoin",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
        )
        FxRate.objects.create(
            from_currency="BTC",
            to_currency="EUR",
            rate=Decimal("65000.00000000"),
            rate_date=date(2026, 4, 8),
            source="test",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 8),
            value_date=date(2026, 4, 8),
            description="Compra BTC",
            status=LedgerTransaction.Status.POSTED,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.INFLOW,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=crypto_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("0.00030000"),
            currency="BTC",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="financial_investments",
            subcategory_key="crypto",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("19.50"),
            currency="EUR",
        )

        response = self.client.get("/api/accounting/transactions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        crypto_entry = next(
            row
            for row in response.data["results"][0]["entries"]
            if row["account_id"] == crypto_account.id
        )
        self.assertEqual(crypto_entry["amount"], "0.00030000")
        self.assertEqual(crypto_entry["amount_base"], "19.50")

    def test_account_list_current_balance_excludes_draft_transactions(self):
        posted_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 15),
            value_date=date(2026, 2, 15),
            description="Ingreso contabilizado",
            status=LedgerTransaction.Status.POSTED,
        )
        draft_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 16),
            value_date=date(2026, 2, 16),
            description="Ingreso previsto",
            status=LedgerTransaction.Status.DRAFT,
        )
        for tx, amount in ((posted_tx, Decimal("1000.00")), (draft_tx, Decimal("300.00"))):
            LedgerEntry.objects.create(
                transaction=tx,
                account=self.cash_account,
                side=LedgerEntry.Side.DEBIT,
                amount=amount,
                currency="EUR",
            )
            LedgerEntry.objects.create(
                transaction=tx,
                account=self.income_account,
                side=LedgerEntry.Side.CREDIT,
                amount=amount,
                currency="EUR",
            )

        accounts_res = self.client.get("/api/accounting/accounts/")
        self.assertEqual(accounts_res.status_code, status.HTTP_200_OK)
        self.assertEqual(accounts_res.data[0]["current_balance"], "1000.00000000")

    def test_create_transaction_rejects_unbalanced_entries(self):
        response = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-15",
                "value_date": "2026-02-15",
                "description": "Asiento invalido",
                "entries": [
                    {
                        "account_id": self.cash_account.id,
                        "side": "debit",
                        "amount": "100.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "80.00",
                        "currency": "EUR",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("entries", response.data["error"]["details"])

    def test_create_transaction_updates_accounting_asset_start_date_when_booking_is_earlier(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            currency="EUR",
            start_date=date(2026, 1, 1),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Bitcoin account",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        asset.accounting_account_id = investment_account.id
        asset.save(update_fields=["accounting_account_id", "updated_at"])

        response = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2025-10-09",
                "value_date": "2025-10-09",
                "description": "Movimiento antiguo",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": investment_account.id,
                        "side": "debit",
                        "amount": "300.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "300.00",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "capital_gains",
                        "subcategory_key": "sale_financial_assets",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        asset.refresh_from_db()
        self.assertEqual(asset.start_date, date(2025, 10, 9))

    def test_update_transaction_updates_accounting_asset_start_date_when_booking_is_earlier(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            currency="EUR",
            start_date=date(2026, 1, 1),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Bitcoin account",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        asset.accounting_account_id = investment_account.id
        asset.save(update_fields=["accounting_account_id", "updated_at"])

        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Movimiento reciente",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.MANUAL,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("100.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

        response = self.client.patch(
            f"/api/accounting/transactions/{tx.id}/",
            {
                "booking_date": "2025-08-15",
                "value_date": "2025-08-15",
                "description": "Movimiento corregido",
                "entries": [
                    {
                        "account_id": investment_account.id,
                        "side": "debit",
                        "amount": "120.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "120.00",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "capital_gains",
                        "subcategory_key": "sale_financial_assets",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        asset.refresh_from_db()
        self.assertEqual(asset.start_date, date(2025, 8, 15))

    def test_update_legacy_multicurrency_transaction_allows_amount_change_with_same_structure(self):
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="Bitcoin",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 10, 9),
            value_date=date(2025, 10, 9),
            description="ST Criptos",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.IMPORT,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INCOME,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=btc_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("0.00283275"),
            currency="BTC",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("300.90"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

        response = self.client.patch(
            f"/api/accounting/transactions/{tx.id}/",
            {
                "booking_date": "2025-10-09",
                "value_date": "2025-10-09",
                "description": "ST Criptos",
                "entries": [
                    {
                        "account_id": btc_account.id,
                        "side": "debit",
                        "amount": "0.00250000",
                        "currency": "BTC",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "265.56",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "capital_gains",
                        "subcategory_key": "sale_financial_assets",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        tx.refresh_from_db()
        btc_entry = tx.entries.get(account=btc_account)
        eur_entry = tx.entries.get(account=self.income_account)
        self.assertEqual(btc_entry.amount, Decimal("0.00250000"))
        self.assertEqual(eur_entry.amount, Decimal("265.56000000"))

    def test_update_investment_allows_cross_currency_structure_change(self):
        btc_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("0.01000000"),
            is_active=True,
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="BTC wallet",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=btc_asset,
        )
        usd_liquidity = LedgerAccount.objects.create(
            user=self.user,
            name="Spot Binance USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 8, 19),
            value_date=date(2025, 8, 19),
            description="ST Criptos",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.IMPORT,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.INFLOW,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=btc_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("0.00013201"),
            currency="BTC",
            asset=btc_asset,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("12.80000000"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

        response = self.client.patch(
            f"/api/accounting/transactions/{tx.id}/",
            {
                "booking_date": "2025-08-19",
                "value_date": "2025-08-19",
                "description": "ST Criptos",
                "quick_entry_kind": "investment",
                "investment_direction": "inflow",
                "entries": [
                    {
                        "account_id": btc_account.id,
                        "side": "debit",
                        "amount": "0.00013201",
                        "currency": "BTC",
                        "asset_id": btc_asset.id,
                    },
                    {
                        "account_id": usd_liquidity.id,
                        "side": "credit",
                        "amount": "14.94",
                        "currency": "USD",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        tx.refresh_from_db()
        self.assertEqual(tx.quick_entry_kind, LedgerTransaction.QuickEntryKind.INVESTMENT)
        self.assertEqual(tx.investment_direction, LedgerTransaction.InvestmentDirection.INFLOW)
        btc_entry = tx.entries.get(account=btc_account)
        usd_entry = tx.entries.get(account=usd_liquidity)
        self.assertEqual(btc_entry.currency, "BTC")
        self.assertEqual(btc_entry.amount, Decimal("0.00013201"))
        self.assertEqual(usd_entry.currency, "USD")
        self.assertEqual(usd_entry.amount, Decimal("14.94000000"))

    def test_update_transfer_allows_cross_currency_structure_change(self):
        eth_account = LedgerAccount.objects.create(
            user=self.user,
            name="MetaMask ETH",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="ETH",
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="Binance BTC",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 10, 17),
            value_date=date(2025, 10, 17),
            description="Swap cripto",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("50.00000000"),
            currency="EUR",
        )
        eur_destination = LedgerAccount.objects.create(
            user=self.user,
            name="Destino EUR inicial",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=eur_destination,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("50.00000000"),
            currency="EUR",
        )

        response = self.client.patch(
            f"/api/accounting/transactions/{tx.id}/",
            {
                "booking_date": "2025-10-17",
                "value_date": "2025-10-17",
                "description": "Swap cripto",
                "quick_entry_kind": "transfer",
                "entries": [
                    {
                        "account_id": eth_account.id,
                        "side": "credit",
                        "amount": "0.11000000",
                        "currency": "ETH",
                    },
                    {
                        "account_id": btc_account.id,
                        "side": "debit",
                        "amount": "0.00395872",
                        "currency": "BTC",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        tx.refresh_from_db()
        eth_entry = tx.entries.get(account=eth_account)
        btc_entry = tx.entries.get(account=btc_account)
        self.assertEqual(eth_entry.currency, "ETH")
        self.assertEqual(eth_entry.amount, Decimal("0.11000000"))
        self.assertEqual(btc_entry.currency, "BTC")
        self.assertEqual(btc_entry.amount, Decimal("0.00395872"))

    def test_account_create_validates_owned_asset_and_currency(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Banco",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("100.00"),
            is_active=True,
        )
        create_res = self.client.post(
            "/api/accounting/accounts/",
            {
                "name": "Cuenta liquidez",
                "account_type": "asset",
                "currency": "eur",
                "origin": "user",
                "asset_id": asset.id,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(create_res.data["asset_id"], asset.id)

    def test_queryset_is_user_scoped(self):
        other_user = get_user_model().objects.create_user(
            username="acct_other",
            password="pass1234",
        )
        other_account = LedgerAccount.objects.create(
            user=other_user,
            name="Otra cuenta",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=other_user,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            description="Ajeno",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=other_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=other_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10.00"),
            currency="EUR",
        )

        accounts_res = self.client.get("/api/accounting/accounts/")
        transactions_res = self.client.get("/api/accounting/transactions/")
        entries_res = self.client.get("/api/accounting/entries/")

        self.assertEqual(accounts_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(accounts_res.data), 2)
        self.assertEqual(len(transactions_res.data["results"]), 0)
        self.assertEqual(transactions_res.data["total_count"], 0)
        self.assertIsNone(transactions_res.data["next_cursor"])
        self.assertEqual(len(entries_res.data), 0)

    def test_transactions_list_returns_cursor_envelope_and_activity_kind(self):
        for booking_date, description in (
            ("2026-02-10", "Nomina"),
            ("2026-02-09", "Nomina extra"),
            ("2026-02-08", "Nomina variable"),
        ):
            create_res = self.client.post(
                "/api/accounting/transactions/",
                {
                    "booking_date": booking_date,
                    "value_date": booking_date,
                    "description": description,
                    "status": "posted",
                    "origin": "manual",
                    "entries": [
                        {
                            "account_id": self.cash_account.id,
                            "side": "debit",
                            "amount": "100.00",
                            "currency": "EUR",
                        },
                        {
                            "account_id": self.income_account.id,
                            "side": "credit",
                            "amount": "100.00",
                            "currency": "EUR",
                            "flow_family": "income",
                            "category_key": "salary",
                            "subcategory_key": "employee_salary",
                        },
                    ],
                },
                format="json",
            )
            self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)

        first_page = self.client.get("/api/accounting/transactions/?page_size=2")
        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(first_page.data["results"]), 2)
        self.assertEqual(first_page.data["total_count"], 3)
        self.assertIsNotNone(first_page.data["next_cursor"])
        self.assertTrue(all("activity_kind" in row for row in first_page.data["results"]))
        self.assertTrue(all(row["activity_kind"] == "income" for row in first_page.data["results"]))

        second_page = self.client.get(
            f"/api/accounting/transactions/?page_size=2&cursor={first_page.data['next_cursor']}"
        )
        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second_page.data["results"]), 1)
        self.assertIsNone(second_page.data["next_cursor"])
        first_page_ids = {row["id"] for row in first_page.data["results"]}
        second_page_ids = {row["id"] for row in second_page.data["results"]}
        self.assertTrue(first_page_ids.isdisjoint(second_page_ids))

    def test_transactions_list_can_skip_total_count(self):
        create_res = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-10",
                "value_date": "2026-02-10",
                "description": "Nomina",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": self.cash_account.id,
                        "side": "debit",
                        "amount": "100.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "100.00",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "salary",
                        "subcategory_key": "employee_salary",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)

        response = self.client.get("/api/accounting/transactions/?include_total=false")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_count", response.data)
        self.assertIsNone(response.data["total_count"])
        self.assertEqual(len(response.data["results"]), 1)

    def test_transactions_list_rejects_invalid_include_total(self):
        response = self.client.get("/api/accounting/transactions/?include_total=maybe")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("include_total", response.data["error"]["details"])

    def test_transactions_list_can_skip_entries(self):
        create_res = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-10",
                "value_date": "2026-02-10",
                "description": "Nomina",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": self.cash_account.id,
                        "side": "debit",
                        "amount": "100.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "100.00",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "salary",
                        "subcategory_key": "employee_salary",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)

        response = self.client.get("/api/accounting/transactions/?include_entries=false")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertNotIn("entries", response.data["results"][0])
        self.assertEqual(response.data["results"][0]["activity_kind"], "income")

    def test_transactions_list_rejects_invalid_include_entries(self):
        response = self.client.get("/api/accounting/transactions/?include_entries=maybe")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("include_entries", response.data["error"]["details"])

    def test_transactions_list_returns_account_balance_after_across_cursor_pages(self):
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos corrientes",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        for booking_date, description, cash_side, counterparty_account, amount in (
            (
                "2026-02-10",
                "Nomina",
                LedgerEntry.Side.DEBIT,
                self.income_account,
                Decimal("100.00"),
            ),
            (
                "2026-02-09",
                "Supermercado",
                LedgerEntry.Side.CREDIT,
                expense_account,
                Decimal("30.00"),
            ),
            (
                "2026-02-08",
                "Ingreso inicial",
                LedgerEntry.Side.DEBIT,
                self.income_account,
                Decimal("50.00"),
            ),
        ):
            counterparty_side = (
                LedgerEntry.Side.CREDIT
                if cash_side == LedgerEntry.Side.DEBIT
                else LedgerEntry.Side.DEBIT
            )
            create_res = self.client.post(
                "/api/accounting/transactions/",
                {
                    "booking_date": booking_date,
                    "value_date": booking_date,
                    "description": description,
                    "status": "posted",
                    "origin": "manual",
                    "entries": [
                        {
                            "account_id": self.cash_account.id,
                            "side": cash_side,
                            "amount": str(amount),
                            "currency": "EUR",
                        },
                        {
                            "account_id": counterparty_account.id,
                            "side": counterparty_side,
                            "amount": str(amount),
                            "currency": "EUR",
                        },
                    ],
                },
                format="json",
            )
            self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)

        first_page = self.client.get(
            f"/api/accounting/transactions/?account_id={self.cash_account.id}&page_size=2"
        )
        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["account_balance_after"] for row in first_page.data["results"]],
            ["120.00000000", "20.00000000"],
        )
        self.assertIsNotNone(first_page.data["next_cursor"])

        second_page = self.client.get(
            f"/api/accounting/transactions/?account_id={self.cash_account.id}&page_size=2"
            f"&cursor={first_page.data['next_cursor']}"
        )
        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second_page.data["results"]), 1)
        self.assertEqual(second_page.data["results"][0]["account_balance_after"], "50.00000000")
        self.assertIsNone(second_page.data["next_cursor"])

    def test_transactions_list_filters_support_combination(self):
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Supermercado",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        savings_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta ahorro",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        create_income = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-10",
                "value_date": "2026-02-10",
                "description": "Nomina febrero",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": self.cash_account.id,
                        "side": "debit",
                        "amount": "2000.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "2000.00",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "salary",
                        "subcategory_key": "employee_salary",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_income.status_code, status.HTTP_201_CREATED, create_income.data)
        create_expense = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-09",
                "value_date": "2026-02-09",
                "description": "Compra supermercado",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": expense_account.id,
                        "side": "debit",
                        "amount": "120.00",
                        "currency": "EUR",
                        "flow_family": "expense",
                        "category_key": "consumption_expenses",
                        "subcategory_key": "housing_home",
                    },
                    {
                        "account_id": self.cash_account.id,
                        "side": "credit",
                        "amount": "120.00",
                        "currency": "EUR",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_expense.status_code, status.HTTP_201_CREATED, create_expense.data)
        create_transfer = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-08",
                "value_date": "2026-02-08",
                "description": "Transferencia ahorro",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": self.cash_account.id,
                        "side": "credit",
                        "amount": "300.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": savings_account.id,
                        "side": "debit",
                        "amount": "300.00",
                        "currency": "EUR",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_transfer.status_code, status.HTTP_201_CREATED, create_transfer.data)

        filtered = self.client.get(
            "/api/accounting/transactions/?kind=expense&query=super&date_from=2026-02-09&date_to=2026-02-10"
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["total_count"], 1)
        self.assertEqual(filtered.data["results"][0]["activity_kind"], "expense")

        by_account = self.client.get(
            f"/api/accounting/transactions/?account_id={savings_account.id}"
        )
        self.assertEqual(by_account.status_code, status.HTTP_200_OK)
        self.assertEqual(by_account.data["total_count"], 1)
        self.assertEqual(by_account.data["results"][0]["description"], "Transferencia ahorro")

        by_account_name_query = self.client.get(
            "/api/accounting/transactions/?query=Cuenta%20ahorro"
        )
        self.assertEqual(by_account_name_query.status_code, status.HTTP_200_OK)
        self.assertEqual(by_account_name_query.data["total_count"], 1)
        self.assertEqual(
            by_account_name_query.data["results"][0]["description"], "Transferencia ahorro"
        )

    def test_transactions_list_kind_transfer_includes_legacy_asset_transfers(self):
        savings_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta ahorro legacy",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 11),
            value_date=date(2026, 2, 11),
            description="Transferencia legacy entre cuentas",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind="",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("25.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=savings_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("25.00"),
            currency="EUR",
        )

        response = self.client.get("/api/accounting/transactions/?kind=transfer")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["total_count"], 1)
        self.assertEqual(response.data["results"][0]["description"], tx.description)

    def test_transactions_list_kind_investment_purchase_excludes_revaluation(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Cartera indexada",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker cartera",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto tecnico",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
        )
        investment_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 17),
            value_date=date(2026, 3, 17),
            description="Aporte broker marzo",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
        )
        LedgerEntry.objects.create(
            transaction=investment_tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("30.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=investment_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("30.00"),
            currency="EUR",
        )
        transfer_tagged_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 17),
            value_date=date(2026, 3, 17),
            description="Transfer mal etiquetada sobre inversion",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
        )
        LedgerEntry.objects.create(
            transaction=transfer_tagged_tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("22.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=transfer_tagged_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("22.00"),
            currency="EUR",
        )

        revaluation_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Revalorizacion cartera marzo",
            origin=LedgerTransaction.Origin.SYSTEM,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("15.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("15.00"),
            currency="EUR",
        )

        filtered = self.client.get("/api/accounting/transactions/?kind=investment_purchase")
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["total_count"], 1)
        self.assertEqual(filtered.data["results"][0]["description"], "Aporte broker marzo")
        self.assertEqual(filtered.data["results"][0]["activity_kind"], "investment_purchase")

    def test_transactions_list_kind_debt_payment_excludes_revaluation(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca principal",
            category=Liability.Category.MORTGAGE,
            currency="EUR",
            amount=Decimal("120000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo hipoteca",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto tecnico",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
        )

        debt_payment_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 5),
            value_date=date(2026, 3, 5),
            description="Cuota hipoteca marzo",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.DEBT_PAYMENT,
        )
        LedgerEntry.objects.create(
            transaction=debt_payment_tx,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("500.00"),
            currency="EUR",
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=debt_payment_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("500.00"),
            currency="EUR",
        )

        revaluation_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Revalorizacion pasivo marzo",
            origin=LedgerTransaction.Origin.SYSTEM,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("120.00"),
            currency="EUR",
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("120.00"),
            currency="EUR",
        )

        filtered = self.client.get("/api/accounting/transactions/?kind=debt_payment")
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["total_count"], 1)
        self.assertEqual(filtered.data["results"][0]["description"], "Cuota hipoteca marzo")
        self.assertEqual(filtered.data["results"][0]["activity_kind"], "debt_payment")

    def test_transactions_list_classifies_system_opening_balance_as_opening_balance(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta inicial",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        opening_account = LedgerAccount.objects.create(
            user=self.user,
            name="Caja inicial",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto tecnico",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 10),
            value_date=date(2026, 3, 10),
            description="Saldo inicial contable: Caja inicial",
            origin=LedgerTransaction.Origin.SYSTEM,
            notes="net_worth_opening_balance:asset:999",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=opening_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            asset=asset,
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )

        response = self.client.get("/api/accounting/transactions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        found = next((row for row in response.data["results"] if row["id"] == opening_tx.id), None)
        self.assertIsNotNone(found)
        self.assertEqual(found["activity_kind"], "opening_balance")

    def test_transactions_list_kind_opening_balance_excludes_revaluation(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Activo apertura",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta apertura",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto tecnico",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 11),
            value_date=date(2026, 3, 11),
            description="Saldo inicial contable: Cuenta apertura",
            origin=LedgerTransaction.Origin.SYSTEM,
            notes="net_worth_opening_balance:asset:1001",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=asset_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            asset=asset,
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )

        revaluation_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Revalorizacion cartera marzo",
            origin=LedgerTransaction.Origin.SYSTEM,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=asset_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("15.00"),
            currency="EUR",
            asset=asset,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("15.00"),
            currency="EUR",
        )

        opening_filtered = self.client.get("/api/accounting/transactions/?kind=opening_balance")
        self.assertEqual(opening_filtered.status_code, status.HTTP_200_OK, opening_filtered.data)
        self.assertEqual(opening_filtered.data["total_count"], 1)
        self.assertEqual(
            opening_filtered.data["results"][0]["description"],
            "Saldo inicial contable: Cuenta apertura",
        )
        self.assertEqual(opening_filtered.data["results"][0]["activity_kind"], "opening_balance")

        revaluation_filtered = self.client.get("/api/accounting/transactions/?kind=revaluation")
        self.assertEqual(
            revaluation_filtered.status_code,
            status.HTTP_200_OK,
            revaluation_filtered.data,
        )
        self.assertEqual(revaluation_filtered.data["total_count"], 1)
        self.assertEqual(
            revaluation_filtered.data["results"][0]["description"], "Revalorizacion cartera marzo"
        )
        self.assertEqual(revaluation_filtered.data["results"][0]["activity_kind"], "revaluation")

    def test_kind_filters_prioritize_quick_entry_kind_over_legacy_markers(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin test",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="EUR",
            amount=Decimal("100.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="BTC broker test",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo test",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("1000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo test",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )

        investment_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 20),
            value_date=date(2026, 3, 20),
            description="Inversion con marca legacy de ingreso",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
        )
        LedgerEntry.objects.create(
            transaction=investment_tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=investment_tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

        transfer_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 21),
            value_date=date(2026, 3, 21),
            description="Transferencia con estructura no canonica",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
        )
        LedgerEntry.objects.create(
            transaction=transfer_tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("5.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=transfer_tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("5.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

        investment_with_liability_marker_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 22),
            value_date=date(2026, 3, 22),
            description="Inversion con marca de deuda legacy",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
        )
        LedgerEntry.objects.create(
            transaction=investment_with_liability_marker_tx,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("7.00"),
            currency="EUR",
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=investment_with_liability_marker_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("7.00"),
            currency="EUR",
        )

        debt_payment_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 23),
            value_date=date(2026, 3, 23),
            description="Pago deuda test",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.DEBT_PAYMENT,
        )
        LedgerEntry.objects.create(
            transaction=debt_payment_tx,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("50.00"),
            currency="EUR",
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=debt_payment_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("50.00"),
            currency="EUR",
        )

        income_filtered = self.client.get("/api/accounting/transactions/?kind=income")
        self.assertEqual(income_filtered.status_code, status.HTTP_200_OK, income_filtered.data)
        income_descriptions = {row["description"] for row in income_filtered.data["results"]}
        self.assertNotIn("Inversion con marca legacy de ingreso", income_descriptions)
        self.assertNotIn("Transferencia con estructura no canonica", income_descriptions)

        debt_filtered = self.client.get("/api/accounting/transactions/?kind=debt_payment")
        self.assertEqual(debt_filtered.status_code, status.HTTP_200_OK, debt_filtered.data)
        debt_descriptions = {row["description"] for row in debt_filtered.data["results"]}
        self.assertIn("Pago deuda test", debt_descriptions)
        self.assertNotIn("Inversion con marca de deuda legacy", debt_descriptions)

        transfer_filtered = self.client.get("/api/accounting/transactions/?kind=transfer")
        self.assertEqual(transfer_filtered.status_code, status.HTTP_200_OK, transfer_filtered.data)
        transfer_descriptions = {row["description"] for row in transfer_filtered.data["results"]}
        self.assertIn("Transferencia con estructura no canonica", transfer_descriptions)

    def test_monthly_summary_endpoint(self):
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Vivienda",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Alquiler",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="housing_home",
            amount_annual=Decimal("8400.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 2),
            value_date=date(2026, 3, 2),
            description="Alquiler marzo",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("700.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="housing_home",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("700.00"),
            currency="EUR",
        )

        response = self.client.get("/api/accounting/transactions/monthly-summary/?year=2026")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["months"][2]["expense_total"], "700.00")

    def test_account_create_rejects_foreign_liability_reference(self):
        other_user = get_user_model().objects.create_user(
            username="liab_other",
            password="pass1234",
        )
        liability = Liability.objects.create(
            user=other_user,
            name="Prestamo ajeno",
            category=Liability.Category.OTHER,
            currency="EUR",
            amount=Decimal("50.00"),
        )
        response = self.client.post(
            "/api/accounting/accounts/",
            {
                "name": "Deuda",
                "account_type": "liability",
                "currency": "EUR",
                "liability_id": liability.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("liability_id", response.data["error"]["details"])

    def test_account_delete_allows_unlinked_account_without_entries(self):
        transient_account = LedgerAccount.objects.create(
            user=self.user,
            name="Temporal",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            origin=LedgerAccount.Origin.USER,
        )

        response = self.client.delete(f"/api/accounting/accounts/{transient_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        self.assertFalse(LedgerAccount.objects.filter(id=transient_account.id).exists())

    def test_account_delete_removes_related_transactions_and_entries(self):
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 1),
            value_date=date(2026, 4, 1),
            description="Saldo inicial",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10.00"),
            currency="EUR",
        )

        response = self.client.delete(f"/api/accounting/accounts/{self.cash_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        self.assertFalse(LedgerAccount.objects.filter(id=self.cash_account.id).exists())
        self.assertEqual(LedgerEntry.objects.filter(transaction=tx).count(), 0)
        self.assertFalse(LedgerTransaction.objects.filter(id=tx.id).exists())

    def test_account_delete_unlinks_asset_accounting_reference(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Banco enlazado",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("100.00"),
            is_active=True,
        )
        linked_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta enlazada",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
            origin=LedgerAccount.Origin.USER,
        )

        response = self.client.delete(f"/api/accounting/accounts/{linked_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        asset.refresh_from_db()
        self.assertIsNone(asset.accounting_account_id)
        self.assertEqual(asset.tracking_mode, Asset.TrackingMode.MANUAL)

    def test_account_delete_unlinks_liability_accounting_reference(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Pasivo enlazado",
            category=Liability.Category.OTHER,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id=None,
            currency="EUR",
            annual_interest_tae=None,
            amount=Decimal("1000.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        linked_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta pasivo enlazada",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
            origin=LedgerAccount.Origin.USER,
        )
        liability.accounting_account_id = linked_account.id
        liability.save(update_fields=["accounting_account_id"])

        response = self.client.delete(f"/api/accounting/accounts/{linked_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        liability.refresh_from_db()
        self.assertIsNone(liability.accounting_account_id)
        self.assertEqual(liability.tracking_mode, Liability.TrackingMode.MANUAL)

    def test_account_delete_rejects_system_accounts(self):
        system_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingreso: Nomina",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
        )

        response = self.client.delete(f"/api/accounting/accounts/{system_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("detail", response.data["error"]["details"])

    def test_quick_entry_income_creates_balanced_transaction_with_system_income_account(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-01",
                "value_date": "2026-04-01",
                "description": "Nomina abril",
                "amount": "2000.00",
                "account_id": self.cash_account.id,
                "category_key": "salary",
                "subcategory_key": "employee_salary",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data["entries"]), 2)
        income_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] != self.cash_account.id
        )
        self.assertEqual(income_entry["flow_family"], "income")
        self.assertEqual(income_entry["category_key"], "salary")
        self.assertEqual(income_entry["subcategory_key"], "employee_salary")
        self.assertTrue(
            LedgerAccount.objects.filter(
                user=self.user,
                account_type=LedgerAccount.AccountType.INCOME,
                origin=LedgerAccount.Origin.SYSTEM,
                name="Ingresos sin categoria",
            ).exists()
        )
        self.cash_account.refresh_from_db()
        self.assertEqual(
            LedgerEntry.objects.filter(transaction_id=response.data["id"]).count(),
            2,
        )
        self.assertEqual(
            self.client.get("/api/accounting/accounts/").data[0]["current_balance"], "2000.00000000"
        )

    def test_quick_entry_income_accepts_category_without_annual_link(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-06",
                "value_date": "2026-04-06",
                "description": "Ingreso clasificado sin linea anual",
                "amount": "550.00",
                "account_id": self.cash_account.id,
                "category_key": "salary",
                "subcategory_key": "employee_salary",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        income_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] != self.cash_account.id
        )
        self.assertEqual(income_entry["flow_family"], "income")
        self.assertEqual(income_entry["category_key"], "salary")
        self.assertEqual(income_entry["subcategory_key"], "employee_salary")
        self.assertNotIn("annual_income_entry_id", income_entry)

    def test_quick_entry_expense_requires_category_when_annual_link_is_missing(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-04-06",
                "value_date": "2026-04-06",
                "description": "Gasto sin clasificar",
                "amount": "90.00",
                "account_id": self.cash_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("subcategory_key", response.data["error"]["details"])

    def test_quick_entry_expense_uses_expense_counterpart_and_updates_monthly_summary(self):
        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-01",
                "value_date": "2026-04-01",
                "description": "Saldo inicial",
                "amount": "1500.00",
                "account_id": self.cash_account.id,
                "category_key": "salary",
                "subcategory_key": "employee_salary",
            },
            format="json",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-04-02",
                "value_date": "2026-04-02",
                "description": "Compra semanal",
                "amount": "120.00",
                "account_id": self.cash_account.id,
                "category_key": "consumption_expenses",
                "subcategory_key": "living_expenses",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        expense_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] != self.cash_account.id
        )
        self.assertEqual(expense_entry["flow_family"], "expense")
        self.assertEqual(expense_entry["category_key"], "consumption_expenses")
        self.assertEqual(expense_entry["subcategory_key"], "living_expenses")
        self.assertTrue(
            LedgerAccount.objects.filter(
                user=self.user,
                account_type=LedgerAccount.AccountType.EXPENSE,
                origin=LedgerAccount.Origin.SYSTEM,
                name="Gastos sin categoria",
            ).exists()
        )

        summary = self.client.get("/api/accounting/transactions/monthly-summary/?year=2026")
        self.assertEqual(summary.status_code, status.HTTP_200_OK, summary.data)
        self.assertEqual(summary.data["months"][3]["income_total"], "1500.00")
        self.assertEqual(summary.data["months"][3]["expense_total"], "120.00")

    def test_quick_entry_expense_with_explicit_classification_updates_monthly_summary(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-05-04",
                "value_date": "2026-05-04",
                "description": "Compra clasificada",
                "amount": "130.00",
                "account_id": self.cash_account.id,
                "flow_family": "expense",
                "category_key": "consumption_expenses",
                "subcategory_key": "living_expenses",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        expense_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] != self.cash_account.id
        )
        self.assertEqual(expense_entry["flow_family"], "expense")
        self.assertEqual(expense_entry["category_key"], "consumption_expenses")
        self.assertEqual(expense_entry["subcategory_key"], "living_expenses")

        summary = self.client.get("/api/accounting/transactions/monthly-summary/?year=2026")
        self.assertEqual(summary.status_code, status.HTTP_200_OK, summary.data)
        self.assertEqual(summary.data["months"][4]["expense_total"], "130.00")

    def test_quick_entry_expense_allows_liability_origin_account(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Tarjeta ECI",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            amount=Decimal("0.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Tarjeta ECI Pablo",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-05-06",
                "value_date": "2026-05-06",
                "description": "Parking",
                "amount": "4.95",
                "account_id": liability_account.id,
                "flow_family": "expense",
                "category_key": "consumption_expenses",
                "subcategory_key": "transport_mobility",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["quick_entry_kind"], "expense")
        liability_entry = next(
            row for row in response.data["entries"] if row["account_id"] == liability_account.id
        )
        expense_entry = next(
            row for row in response.data["entries"] if row["flow_family"] == "expense"
        )
        self.assertEqual(liability_entry["side"], "credit")
        self.assertEqual(liability_entry["amount"], "4.95000000")
        self.assertEqual(expense_entry["side"], "debit")
        self.assertEqual(expense_entry["category_key"], "consumption_expenses")
        self.assertEqual(expense_entry["subcategory_key"], "transport_mobility")

    def test_ledger_entry_with_classification_is_reflected_in_monthly_summary(self):
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos clasificados",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 6, 10),
            value_date=date(2026, 6, 10),
            description="Gasto clasificado",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("80.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="housing_home",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("80.00"),
            currency="EUR",
        )

        summary = build_monthly_accounting_summary(user_id=self.user.id, fiscal_year=2026)
        self.assertEqual(summary["months"][5]["expense_total"], "80.00")

    def test_quick_entry_transfer_requires_different_liquidity_account(self):
        second_cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ahorro",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

        valid_response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-03",
                "value_date": "2026-04-03",
                "description": "Mover a ahorro",
                "amount": "300.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": second_cash_account.id,
            },
            format="json",
        )
        self.assertEqual(valid_response.status_code, status.HTTP_201_CREATED, valid_response.data)

        invalid_response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-03",
                "value_date": "2026-04-03",
                "description": "Duplicada",
                "amount": "10.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": self.cash_account.id,
            },
            format="json",
        )
        self.assertEqual(
            invalid_response.status_code, status.HTTP_400_BAD_REQUEST, invalid_response.data
        )
        self.assertIn("counterparty_account_id", invalid_response.data["error"]["details"])

    def test_quick_entry_transfer_allows_liquidity_to_credit_card_liability(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Tarjeta ECI",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            amount=Decimal("0.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Tarjeta ECI Pablo",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-03",
                "value_date": "2026-04-03",
                "description": "Transferencia a Tarjeta ECI desde ING",
                "amount": "136.47",
                "account_id": self.cash_account.id,
                "counterparty_account_id": liability_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["quick_entry_kind"], "transfer")
        liability_entry = next(
            row for row in response.data["entries"] if row["account_id"] == liability_account.id
        )
        origin_entry = next(
            row for row in response.data["entries"] if row["account_id"] == self.cash_account.id
        )
        self.assertEqual(liability_entry["side"], "debit")
        self.assertEqual(origin_entry["side"], "credit")

    def test_quick_entry_transfer_allows_cross_currency_with_destination_amount(self):
        usd_account = LedgerAccount.objects.create(
            user=self.user,
            name="Spot Binance",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-20",
                "value_date": "2026-04-20",
                "description": "Traspaso a Spot Binance",
                "amount": "250.00",
                "destination_amount": "270.15",
                "account_id": self.cash_account.id,
                "counterparty_account_id": usd_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        eur_credit = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == self.cash_account.id
        )
        usd_debit = next(
            entry for entry in response.data["entries"] if entry["account_id"] == usd_account.id
        )
        self.assertEqual(eur_credit["side"], "credit")
        self.assertEqual(eur_credit["currency"], "EUR")
        self.assertEqual(eur_credit["amount"], "250.00000000")
        self.assertEqual(usd_debit["side"], "debit")
        self.assertEqual(usd_debit["currency"], "USD")
        self.assertEqual(usd_debit["amount"], "270.15000000")

    def test_quick_entry_transfer_cross_currency_requires_destination_amount(self):
        usd_account = LedgerAccount.objects.create(
            user=self.user,
            name="Spot Binance",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-20",
                "value_date": "2026-04-20",
                "description": "Traspaso a Spot Binance",
                "amount": "250.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": usd_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("destination_amount", response.data["error"]["details"])

    def test_quick_entry_income_rejects_foreign_account_reference(self):
        other_user = get_user_model().objects.create_user(
            username="acct_foreign_income",
            password="pass1234",
        )
        foreign_account = LedgerAccount.objects.create(
            user=other_user,
            name="Cuenta ajena",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-07",
                "value_date": "2026-04-07",
                "description": "Ingreso con cuenta ajena",
                "amount": "50.00",
                "account_id": foreign_account.id,
                "category_key": "salary",
                "subcategory_key": "employee_salary",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("account_id", response.data["error"]["details"])

    def test_quick_entry_income_allows_investment_account_for_reinvested_yield(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Crowdlending position",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CROWDLENDING,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            currency="EUR",
            start_date=date(2025, 1, 1),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("0.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Crowdlending - ViaInvest / EUR",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )
        investment_asset.accounting_account_id = investment_account.id
        investment_asset.save(update_fields=["accounting_account_id", "updated_at"])

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-07",
                "value_date": "2026-04-07",
                "description": "Intereses crowdlending",
                "amount": "14.29",
                "account_id": investment_account.id,
                "category_key": "passive_income",
                "subcategory_key": "p2p_lending",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["activity_kind"], "income")
        self.assertEqual(response.data["quick_entry_kind"], "income")
        self.assertEqual(len(response.data["entries"]), 2)
        investment_entry = next(
            row for row in response.data["entries"] if row["account_id"] == investment_account.id
        )
        classified_entry = next(
            row for row in response.data["entries"] if row["flow_family"] == "income"
        )
        self.assertEqual(investment_entry["side"], "debit")
        self.assertEqual(investment_entry["amount"], "14.29000000")
        self.assertEqual(classified_entry["category_key"], "passive_income")
        self.assertEqual(classified_entry["subcategory_key"], "p2p_lending")

    def test_quick_entry_transfer_rejects_foreign_counterparty_reference(self):
        other_user = get_user_model().objects.create_user(
            username="acct_foreign_transfer",
            password="pass1234",
        )
        foreign_counterparty = LedgerAccount.objects.create(
            user=other_user,
            name="Ahorro ajeno",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-08",
                "value_date": "2026-04-08",
                "description": "Transferencia con contrapartida ajena",
                "amount": "75.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": foreign_counterparty.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("counterparty_account_id", response.data["error"]["details"])

    def test_quick_entry_rejects_partial_functional_classification(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-04-11",
                "value_date": "2026-04-11",
                "description": "Clasificacion incompleta",
                "amount": "90.00",
                "account_id": self.cash_account.id,
                "flow_family": "expense",
                "category_key": "consumption_expenses",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("subcategory_key", response.data["error"]["details"])

    def test_quick_entry_adjustment_creates_equity_counterparty_automatically(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "adjustment",
                "booking_date": "2026-04-12",
                "value_date": "2026-04-12",
                "description": "Ajuste conciliacion BTC",
                "amount": "-0.00078100",
                "account_id": self.cash_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["quick_entry_kind"], "adjustment")
        self.assertEqual(response.data["activity_kind"], "adjustment")
        self.assertEqual(len(response.data["entries"]), 2)

        account_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == self.cash_account.id
        )
        self.assertEqual(account_entry["side"], "credit")
        self.assertEqual(account_entry["amount"], "0.00078100")

        equity_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] != self.cash_account.id
        )
        self.assertEqual(equity_entry["side"], "debit")
        self.assertEqual(equity_entry["amount"], "0.00078100")
        equity_account = LedgerAccount.objects.get(id=equity_entry["account_id"])
        self.assertEqual(equity_account.account_type, LedgerAccount.AccountType.EQUITY)
        self.assertEqual(equity_account.currency, self.cash_account.currency)

    def test_quick_entry_adjustment_rejects_non_operational_account(self):
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio tecnico",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "adjustment",
                "booking_date": "2026-04-12",
                "value_date": "2026-04-12",
                "description": "Ajuste invalido",
                "amount": "10.00",
                "account_id": equity_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("account_id", response.data["error"]["details"])

    def test_transactions_filter_kind_adjustment_returns_only_adjustments(self):
        second_asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ahorro filtro",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "adjustment",
                "booking_date": "2026-04-12",
                "value_date": "2026-04-12",
                "description": "Ajuste 1",
                "amount": "10.00",
                "account_id": self.cash_account.id,
            },
            format="json",
        )
        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-13",
                "value_date": "2026-04-13",
                "description": "Transferencia 1",
                "amount": "10.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": second_asset_account.id,
            },
            format="json",
        )

        response = self.client.get("/api/accounting/transactions/?kind=adjustment")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertGreaterEqual(response.data["total_count"], 1)
        self.assertTrue(response.data["results"])
        self.assertTrue(
            all(row["activity_kind"] == "adjustment" for row in response.data["results"])
        )

    def test_quick_entry_investment_purchase_creates_balanced_entries_with_asset_link(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Fondo indexado",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment_purchase",
                "booking_date": "2026-04-12",
                "value_date": "2026-04-12",
                "description": "Compra fondo abril",
                "amount": "250.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": investment_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data["entries"]), 2)
        debit_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == investment_account.id
        )
        self.assertEqual(debit_entry["side"], "debit")
        self.assertEqual(debit_entry["asset_id"], investment_asset.id)

    def test_quick_entry_investment_outflow_reverses_entry_sides_and_persists_direction(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="ETF cartera",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("1500.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker principal",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "outflow",
                "booking_date": "2026-04-14",
                "value_date": "2026-04-14",
                "description": "Desinversion parcial",
                "amount": "180.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": investment_account.id,
                "realized_cost_basis": "150.00",
                "realized_gain_loss": "30.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["quick_entry_kind"], "investment")
        self.assertEqual(response.data["investment_direction"], "outflow")
        self.assertEqual(response.data["realized_cost_basis"], "150.00000000")
        self.assertEqual(response.data["realized_gain_loss"], "30.00000000")
        debit_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == self.cash_account.id
        )
        credit_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == investment_account.id
        )
        self.assertEqual(debit_entry["side"], "debit")
        self.assertEqual(credit_entry["side"], "credit")

    def test_quick_entry_investment_deposit_forces_deposit_budget_subcategory(self):
        deposit_asset = Asset.objects.create(
            user=self.user,
            name="Deposito 1M",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.SHORT_TERM_DEPOSIT,
            currency="EUR",
            amount=Decimal("5000.00"),
            deposit_term_months=1,
            is_active=True,
        )
        deposit_account = LedgerAccount.objects.create(
            user=self.user,
            name="Deposito 1M cuenta",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=deposit_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "inflow",
                "booking_date": "2026-04-16",
                "value_date": "2026-04-16",
                "description": "Alta deposito",
                "amount": "1000.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": deposit_account.id,
                "category_key": "financial_investments",
                "subcategory_key": "other_financial_investments",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        deposit_entry = next(
            entry for entry in response.data["entries"] if entry["account_id"] == deposit_account.id
        )
        self.assertEqual(deposit_entry["subcategory_key"], "deposits_fixed_income")

    def test_quick_entry_investment_allows_cross_currency_with_destination_amount(self):
        btc_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("0.01000000"),
            is_active=True,
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="BTC Broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=btc_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "inflow",
                "booking_date": "2026-04-16",
                "value_date": "2026-04-16",
                "description": "Compra BTC",
                "amount": "25.00",
                "destination_amount": "0.00042000",
                "account_id": self.cash_account.id,
                "counterparty_account_id": btc_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        cash_credit = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == self.cash_account.id
        )
        btc_debit = next(
            entry for entry in response.data["entries"] if entry["account_id"] == btc_account.id
        )
        self.assertEqual(cash_credit["side"], "credit")
        self.assertEqual(cash_credit["currency"], "EUR")
        self.assertEqual(cash_credit["amount"], "25.00000000")
        self.assertEqual(btc_debit["side"], "debit")
        self.assertEqual(btc_debit["currency"], "BTC")
        self.assertEqual(btc_debit["amount"], "0.00042000")

    def test_quick_entry_investment_cross_currency_requires_destination_amount(self):
        btc_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("0.01000000"),
            is_active=True,
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="BTC Broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=btc_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "inflow",
                "booking_date": "2026-04-16",
                "value_date": "2026-04-16",
                "description": "Compra BTC sin destino",
                "amount": "25.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": btc_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("destination_amount", response.data["error"]["details"])

    def test_quick_entry_investment_outflow_uses_capital_gains_classification(self):
        btc_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("0.01000000"),
            is_active=True,
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="BTC Broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=btc_asset,
        )
        usd_liquidity = LedgerAccount.objects.create(
            user=self.user,
            name="Spot USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "outflow",
                "booking_date": "2026-04-16",
                "value_date": "2026-04-16",
                "description": "Venta BTC",
                "amount": "0.00042000",
                "destination_amount": "25.00",
                "account_id": usd_liquidity.id,
                "counterparty_account_id": btc_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        classified_entry = next(
            row for row in response.data["entries"] if row["flow_family"] == "income"
        )
        self.assertEqual(classified_entry["category_key"], "capital_gains")
        self.assertEqual(classified_entry["subcategory_key"], "sale_financial_assets")

    def test_quick_entry_investment_reinvestment_moves_between_investment_accounts(self):
        source_asset = Asset.objects.create(
            user=self.user,
            name="Fondo origen",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            is_active=True,
        )
        destination_asset = Asset.objects.create(
            user=self.user,
            name="Fondo destino",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("400.00"),
            is_active=True,
        )
        source_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker origen",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=source_asset,
        )
        destination_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker destino",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=destination_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "reinvestment",
                "booking_date": "2026-04-16",
                "value_date": "2026-04-16",
                "description": "Traspaso entre fondos",
                "amount": "250.00",
                "account_id": source_account.id,
                "counterparty_account_id": destination_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["investment_direction"], "reinvestment")
        debit_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == destination_account.id
        )
        credit_entry = next(
            entry for entry in response.data["entries"] if entry["account_id"] == source_account.id
        )
        self.assertEqual(debit_entry["side"], "debit")
        self.assertEqual(debit_entry["asset_id"], destination_asset.id)
        self.assertEqual(credit_entry["side"], "credit")
        self.assertEqual(credit_entry["asset_id"], source_asset.id)
        self.assertEqual(debit_entry["flow_family"], "")
        self.assertEqual(credit_entry["flow_family"], "")

    def test_quick_entry_investment_reinvestment_cross_currency_requires_destination_amount(self):
        eur_asset = Asset.objects.create(
            user=self.user,
            name="Fondo EUR",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            is_active=True,
        )
        btc_asset = Asset.objects.create(
            user=self.user,
            name="BTC",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("0.01000000"),
            is_active=True,
        )
        eur_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker EUR",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=eur_asset,
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker BTC",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=btc_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "reinvestment",
                "booking_date": "2026-04-16",
                "value_date": "2026-04-16",
                "description": "Reinversion sin destino",
                "amount": "250.00",
                "account_id": eur_account.id,
                "counterparty_account_id": btc_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("destination_amount", response.data["error"]["details"])

    def test_quick_entry_mortgage_payment_uses_fixed_real_estate_classification(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca casa",
            category=Liability.Category.MORTGAGE,
            currency="EUR",
            amount=Decimal("120000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo hipoteca",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-20",
                "value_date": "2026-04-20",
                "description": "Pago hipoteca",
                "amount": "500.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "principal_amount": "500.00",
                "interest_amount": "0.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        classified_entry = next(
            row for row in response.data["entries"] if row["flow_family"] == "expense"
        )
        self.assertEqual(classified_entry["category_key"], "real_estate_assets")
        self.assertEqual(classified_entry["subcategory_key"], "mortgage_principal")

    def test_quick_entry_personal_loan_payment_requires_consumption_subcategory(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo coche",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("5000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo prestamo",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-20",
                "value_date": "2026-04-20",
                "description": "Pago prestamo",
                "amount": "400.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "principal_amount": "400.00",
                "interest_amount": "0.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("subcategory_key", response.data["error"]["details"])

    def test_quick_entry_rejects_realized_metadata_outside_investment(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-04-21",
                "value_date": "2026-04-21",
                "description": "Compra semanal",
                "amount": "55.00",
                "account_id": self.cash_account.id,
                "category_key": "consumption_expenses",
                "subcategory_key": "living_expenses",
                "realized_gain_loss": "5.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("realized_gain_loss", response.data["error"]["details"])

    def test_quick_entry_debt_payment_creates_principal_and_interest_breakdown(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo coche",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("8000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo prestamo coche",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        interest_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos financieros",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-18",
                "value_date": "2026-04-18",
                "description": "Cuota prestamo abril",
                "amount": "330.00",
                "principal_amount": "300.00",
                "interest_amount": "30.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "interest_account_id": interest_account.id,
                "category_key": "consumption_expenses",
                "subcategory_key": "financial_commitments",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data["entries"]), 3)
        principal_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == liability_account.id
        )
        interest_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == interest_account.id
        )
        self.assertEqual(principal_entry["side"], "debit")
        self.assertEqual(principal_entry["liability_id"], liability.id)
        self.assertEqual(interest_entry["side"], "debit")
        self.assertNotIn("annual_expense_entry_id", interest_entry)
        self.assertEqual(interest_entry["flow_family"], "expense")
        self.assertEqual(interest_entry["category_key"], "consumption_expenses")
        self.assertEqual(interest_entry["subcategory_key"], "financial_commitments")

    def test_quick_entry_debt_payment_rejects_mismatched_total_breakdown(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo personal",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("2000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo prestamo personal",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        interest_account = LedgerAccount.objects.create(
            user=self.user,
            name="Intereses tarjeta",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-22",
                "value_date": "2026-04-22",
                "description": "Cuota invalida",
                "amount": "250.00",
                "principal_amount": "200.00",
                "interest_amount": "30.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "interest_account_id": interest_account.id,
                "category_key": "consumption_expenses",
                "subcategory_key": "financial_commitments",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("amount", response.data["error"]["details"])

    def test_quick_entry_debt_payment_keeps_non_consumption_category_for_principal(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo movil",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("2000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo prestamo movil",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-23",
                "value_date": "2026-04-23",
                "description": "Cuota movil",
                "amount": "120.00",
                "principal_amount": "120.00",
                "interest_amount": "0.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "category_key": "tangible_assets",
                "subcategory_key": "technology_devices",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        principal_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == liability_account.id
        )
        self.assertEqual(principal_entry["flow_family"], "expense")
        self.assertEqual(principal_entry["category_key"], "tangible_assets")
        self.assertEqual(principal_entry["subcategory_key"], "technology_devices")

    def test_quick_entry_debt_payment_requires_category_for_interest_when_no_annual_link(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo personal",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("2000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo prestamo personal",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        interest_account = LedgerAccount.objects.create(
            user=self.user,
            name="Intereses tarjeta",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-22",
                "value_date": "2026-04-22",
                "description": "Cuota sin clasificar",
                "amount": "250.00",
                "principal_amount": "200.00",
                "interest_amount": "50.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "interest_account_id": interest_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("subcategory_key", response.data["error"]["details"])

    def test_account_balances_endpoint_returns_period_aggregates_for_liquidity_accounts(self):
        second_cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ahorro",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-01",
                "value_date": "2026-04-01",
                "description": "Nomina abril",
                "amount": "1000.00",
                "account_id": self.cash_account.id,
                "category_key": "salary",
                "subcategory_key": "employee_salary",
            },
            format="json",
        )
        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-04-05",
                "value_date": "2026-04-05",
                "description": "Compra abril",
                "amount": "200.00",
                "account_id": self.cash_account.id,
                "category_key": "consumption_expenses",
                "subcategory_key": "living_expenses",
            },
            format="json",
        )
        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-10",
                "value_date": "2026-04-10",
                "description": "Mover ahorro",
                "amount": "300.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": second_cash_account.id,
            },
            format="json",
        )

        response = self.client.get(
            "/api/accounting/accounts/balances/?year=2026&month=4&account_type=asset"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["totals_by_account_type"]["asset"], "800.00")
        self.assertEqual(len(response.data["accounts"]), 2)

        first_account = next(
            row for row in response.data["accounts"] if row["account_id"] == self.cash_account.id
        )
        second_account = next(
            row for row in response.data["accounts"] if row["account_id"] == second_cash_account.id
        )

        self.assertEqual(first_account["current_balance"], "500.00000000")
        self.assertEqual(first_account["period_debit_total"], "1000.00")
        self.assertEqual(first_account["period_credit_total"], "500.00")
        self.assertEqual(first_account["period_net_change"], "500.00")

        self.assertEqual(second_account["current_balance"], "300.00000000")
        self.assertEqual(second_account["period_debit_total"], "300.00")
        self.assertEqual(second_account["period_credit_total"], "0.00")
        self.assertEqual(second_account["period_net_change"], "300.00")

    def test_account_balances_endpoint_requires_year_when_month_is_present(self):
        response = self.client.get("/api/accounting/accounts/balances/?month=4")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("year", response.data["error"]["details"])

    def test_daily_balance_series_endpoint_returns_consolidated_daily_rows(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo coche",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("3000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo prestamo coche",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos movilidad",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            description="Saldo inicial pasivo",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=liability_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )

        payment_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 2),
            value_date=date(2026, 1, 2),
            description="Cuota",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=payment_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("200.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=payment_tx,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("150.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=payment_tx,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("50.00"),
            currency="EUR",
        )

        response = self.client.get(
            "/api/accounting/transactions/daily-balance-series/?date_from=2026-01-01&date_to=2026-01-03"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["filters"]["status"], LedgerTransaction.Status.POSTED)
        self.assertEqual(len(response.data["rows"]), 3)

        first_row = response.data["rows"][0]
        second_row = response.data["rows"][1]
        third_row = response.data["rows"][2]

        self.assertEqual(first_row["date"], "2026-01-01")
        self.assertEqual(first_row["assets_total"], "1000.00")
        self.assertEqual(first_row["liabilities_total"], "1000.00")
        self.assertEqual(first_row["net_balance"], "0.00")

        self.assertEqual(second_row["date"], "2026-01-02")
        self.assertEqual(second_row["assets_total"], "800.00")
        self.assertEqual(second_row["liabilities_total"], "850.00")
        self.assertEqual(second_row["net_balance"], "-50.00")

        self.assertEqual(third_row["date"], "2026-01-03")
        self.assertEqual(third_row["assets_total"], "800.00")
        self.assertEqual(third_row["liabilities_total"], "850.00")
        self.assertEqual(third_row["net_balance"], "-50.00")

    def test_daily_balance_series_endpoint_validates_query_params(self):
        invalid_date = self.client.get(
            "/api/accounting/transactions/daily-balance-series/?date_from=2026-13-01"
        )
        self.assertEqual(invalid_date.status_code, status.HTTP_400_BAD_REQUEST, invalid_date.data)
        self.assertIn("date_from", invalid_date.data["error"]["details"])

        invalid_status = self.client.get(
            "/api/accounting/transactions/daily-balance-series/?status=archived"
        )
        self.assertEqual(
            invalid_status.status_code,
            status.HTTP_400_BAD_REQUEST,
            invalid_status.data,
        )
        self.assertIn("status", invalid_status.data["error"]["details"])

    def test_daily_balance_series_without_date_from_uses_earliest_registered_movement(self):
        tx_old = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2024, 9, 10),
            value_date=date(2024, 9, 10),
            description="Movimiento antiguo",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_old,
            account=self.cash_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_old,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("100.00"),
            currency="EUR",
        )

        response = self.client.get("/api/accounting/transactions/daily-balance-series/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["filters"]["date_from"], "2024-09-10")
        self.assertGreaterEqual(len(response.data["rows"]), 1)
        self.assertEqual(response.data["rows"][0]["date"], "2024-09-10")

    def test_daily_balance_series_converts_foreign_currency_to_user_base(self):
        usd_cash = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )
        usd_income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingreso USD",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="USD",
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.80000000"),
            rate_date=date(2026, 1, 1),
            source="test",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            description="Ingreso en USD",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=usd_cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100.00"),
            currency="USD",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=usd_income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("100.00"),
            currency="USD",
        )

        response = self.client.get(
            "/api/accounting/transactions/daily-balance-series/?date_from=2026-01-01&date_to=2026-01-01"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["base_currency"], "EUR")
        self.assertEqual(response.data["rows"][0]["assets_total"], "80.00")
        self.assertEqual(response.data["rows"][0]["net_balance"], "80.00")

    def test_daily_balance_series_revalues_running_balance_with_latest_fx_per_day(self):
        usd_cash = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )
        usd_income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingreso USD",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="USD",
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.80000000"),
            rate_date=date(2026, 1, 1),
            source="test",
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.90000000"),
            rate_date=date(2026, 1, 2),
            source="test",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            description="Ingreso en USD",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=usd_cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100.00"),
            currency="USD",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=usd_income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("100.00"),
            currency="USD",
        )

        response = self.client.get(
            "/api/accounting/transactions/daily-balance-series/?date_from=2026-01-01&date_to=2026-01-02"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["base_currency"], "EUR")
        self.assertEqual(response.data["rows"][0]["assets_total"], "80.00")
        self.assertEqual(response.data["rows"][0]["net_balance"], "80.00")
        self.assertEqual(response.data["rows"][1]["assets_total"], "90.00")
        self.assertEqual(response.data["rows"][1]["net_balance"], "90.00")

    def test_daily_balance_series_uses_earliest_fx_when_request_date_is_older_than_fx_history(self):
        usd_cash = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )
        usd_income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingreso USD",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="USD",
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.85000000"),
            rate_date=date(2020, 1, 1),
            source="test",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2016, 2, 21),
            value_date=date(2016, 2, 21),
            description="Ingreso USD antiguo",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=usd_cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100.00"),
            currency="USD",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=usd_income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("100.00"),
            currency="USD",
        )

        response = self.client.get(
            "/api/accounting/transactions/daily-balance-series/?date_from=2016-02-21&date_to=2016-02-21"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["rows"][0]["assets_total"], "85.00")
        self.assertEqual(response.data["rows"][0]["net_balance"], "85.00")

    def test_daily_balance_series_filters_by_ownership_id(self):
        member = FamilyMember.objects.create(user=self.user, name="Pablo")
        member_ana = FamilyMember.objects.create(user=self.user, name="Ana")
        ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=member,
        )
        ownership_shared = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.SHARED,
        )
        OwnershipSplit.objects.create(
            ownership=ownership_shared,
            member=member,
            percent=Decimal("50.00"),
        )
        OwnershipSplit.objects.create(
            ownership=ownership_shared,
            member=member_ana,
            percent=Decimal("50.00"),
        )
        owned_asset = Asset.objects.create(
            user=self.user,
            name="Cuenta Pablo",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("0.00"),
        )
        unowned_asset = Asset.objects.create(
            user=self.user,
            name="Cuenta sin titularidad",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("0.00"),
        )
        shared_asset = Asset.objects.create(
            user=self.user,
            name="Cuenta compartida",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("0.00"),
        )
        owned_asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Activo Pablo",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=owned_asset,
        )
        shared_asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Activo compartido",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=shared_asset,
        )
        unowned_asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Activo sin titularidad",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=unowned_asset,
        )
        OwnershipLink.objects.create(
            user=self.user,
            ownership=ownership,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=owned_asset.id,
        )
        OwnershipLink.objects.create(
            user=self.user,
            ownership=ownership_shared,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=shared_asset.id,
        )
        tx_owned = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            description="Ingreso cuenta Pablo",
            status=LedgerTransaction.Status.POSTED,
        )
        tx_shared = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            description="Ingreso cuenta compartida",
            status=LedgerTransaction.Status.POSTED,
        )
        tx_unowned = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            description="Ingreso cuenta sin titularidad",
            status=LedgerTransaction.Status.POSTED,
        )
        for tx, account, amount in (
            (tx_owned, owned_asset_account, Decimal("100.00")),
            (tx_shared, shared_asset_account, Decimal("80.00")),
            (tx_unowned, unowned_asset_account, Decimal("60.00")),
        ):
            LedgerEntry.objects.create(
                transaction=tx,
                account=account,
                side=LedgerEntry.Side.DEBIT,
                amount=amount,
                currency="EUR",
            )
            LedgerEntry.objects.create(
                transaction=tx,
                account=self.income_account,
                side=LedgerEntry.Side.CREDIT,
                amount=amount,
                currency="EUR",
            )

        response = self.client.get(
            f"/api/accounting/transactions/daily-balance-series/?date_from=2026-01-01&date_to=2026-01-01&ownership_id={ownership.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["rows"][0]["assets_total"], "140.00")
        self.assertEqual(response.data["rows"][0]["net_balance"], "140.00")

    def test_daily_balance_series_filters_by_missing_ownership(self):
        member = FamilyMember.objects.create(user=self.user, name="Ana")
        ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=member,
        )
        owned_asset = Asset.objects.create(
            user=self.user,
            name="Cuenta Ana",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("0.00"),
        )
        unowned_asset = Asset.objects.create(
            user=self.user,
            name="Cuenta sin titularidad",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("0.00"),
        )
        owned_asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Activo Ana",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=owned_asset,
        )
        unowned_asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Activo sin titularidad",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=unowned_asset,
        )
        OwnershipLink.objects.create(
            user=self.user,
            ownership=ownership,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=owned_asset.id,
        )
        tx_owned = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            description="Ingreso cuenta Ana",
            status=LedgerTransaction.Status.POSTED,
        )
        tx_unowned = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            description="Ingreso cuenta sin titularidad",
            status=LedgerTransaction.Status.POSTED,
        )
        for tx, account, amount in (
            (tx_owned, owned_asset_account, Decimal("140.00")),
            (tx_unowned, unowned_asset_account, Decimal("70.00")),
        ):
            LedgerEntry.objects.create(
                transaction=tx,
                account=account,
                side=LedgerEntry.Side.DEBIT,
                amount=amount,
                currency="EUR",
            )
            LedgerEntry.objects.create(
                transaction=tx,
                account=self.income_account,
                side=LedgerEntry.Side.CREDIT,
                amount=amount,
                currency="EUR",
            )

        response = self.client.get(
            "/api/accounting/transactions/daily-balance-series/?date_from=2026-01-01&date_to=2026-01-01&ownership_id=null"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["rows"][0]["assets_total"], "70.00")
        self.assertEqual(response.data["rows"][0]["net_balance"], "70.00")

    def test_budget_suggestions_endpoint_returns_historical_series(self):
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Alimentacion",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            amount_annual=Decimal("4800.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos hogar",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        tx_income = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 10),
            value_date=date(2026, 1, 10),
            description="Nomina enero",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_income,
            account=self.cash_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_income,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="salary",
            subcategory_key="employee_salary",
        )

        tx_expense = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Compra mensual",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("350.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="living_expenses",
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("350.00"),
            currency="EUR",
        )

        response = self.client.get("/api/accounting/transactions/budget-suggestions/?year=2026")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["fiscal_year"], 2026)
        self.assertEqual(response.data["lookback_years"], 2)
        self.assertEqual(response.data["window_months"], 24)
        self.assertEqual(len(response.data["income"]["series"]), 24)
        self.assertEqual(len(response.data["expense"]["series"]), 24)
        self.assertEqual(response.data["income"]["subcategories"][0]["category"], "salary")
        self.assertEqual(
            response.data["expense"]["subcategories"][0]["subcategory"],
            "living_expenses",
        )
