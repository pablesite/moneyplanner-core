from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from budget.models import (
    AnnualExpenseEntry,
    AnnualIncomeEntry,
    SettlementAccount,
    SettlementOpeningAdjustment,
    SettlementOpeningBalance,
    SettlementProfile,
)
from memberships.models import FamilyMember, Ownership, OwnershipLink
from net_worth.models import Asset, InvestmentContributionInterval
from net_worth.services_assets_budget import sync_generated_budget_commitments_for_asset


class SettlementApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="settlement", password="pass")
        self.member_a = FamilyMember.objects.create(user=self.user, name="Pablo")
        self.member_b = FamilyMember.objects.create(user=self.user, name="Ana")
        self.individual_a = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.member_a
        )
        self.individual_b = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.member_b
        )
        self.shared = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED)
        self.shared.splits.create(member=self.member_a, percent=Decimal("50.00"))
        self.shared.splits.create(member=self.member_b, percent=Decimal("50.00"))
        self.operating = self._asset("Compartida", Decimal("1000.00"), self.shared)
        self.personal_a = self._asset("Personal Pablo", Decimal("100.00"), self.individual_a)
        self.personal_b = self._asset("Personal Ana", Decimal("200.00"), self.individual_b)
        self.client.force_authenticate(user=self.user)

    def _asset(
        self,
        name: str,
        amount: Decimal,
        ownership: Ownership,
        *,
        subcategory: str = Asset.Subcategory.BANK_ACCOUNT,
    ) -> Asset:
        asset = Asset.objects.create(
            user=self.user,
            name=name,
            category=Asset.Category.CASH,
            subcategory=subcategory,
            amount=amount,
            currency="EUR",
            start_date=date(2025, 1, 1),
        )
        OwnershipLink.objects.create(
            user=self.user,
            ownership=ownership,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=asset.id,
        )
        return asset

    def _configuration_payload(self, *, extra_accounts=None, adjustments=None):
        return {
            "base_currency": "EUR",
            "accounts": [
                {
                    "asset_id": self.operating.id,
                    "role": SettlementAccount.Role.OPERATING,
                },
                {
                    "asset_id": self.personal_a.id,
                    "role": SettlementAccount.Role.PERSONAL_DESTINATION,
                    "member_id": self.member_a.id,
                    "is_primary": True,
                },
                {
                    "asset_id": self.personal_b.id,
                    "role": SettlementAccount.Role.PERSONAL_DESTINATION,
                    "member_id": self.member_b.id,
                    "is_primary": True,
                },
                *(extra_accounts or []),
            ],
            "opening_adjustments": adjustments or [],
        }

    def _configure(self, **kwargs):
        response = self.client.put(
            "/api/budget/settlement/configuration/",
            self._configuration_payload(**kwargs),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response

    def _shared_expense(self, *, destination_asset=None):
        destination_asset = destination_asset or self.operating
        profile = SettlementProfile.objects.get(user=self.user)
        destination = SettlementAccount.objects.get(profile=profile, asset=destination_asset)
        return AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Casa",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            time_profile=AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT,
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            ownership=self.shared,
            settlement_account=destination,
        )

    def test_profile_is_disabled_by_default_and_configuration_is_idempotent(self):
        initial = self.client.get("/api/budget/settlement/configuration/")
        self.assertEqual(initial.status_code, status.HTTP_200_OK)
        self.assertFalse(initial.data["is_enabled"])

        first = self._configure()
        second = self._configure()
        self.assertEqual(first.data["accounts"], second.data["accounts"])
        self.assertEqual(SettlementAccount.objects.filter(profile__user=self.user).count(), 3)

    def test_readiness_and_activation_create_an_idempotent_member_account_baseline(self):
        self._configure()
        self._shared_expense()

        readiness = self.client.get("/api/budget/settlement/readiness/?year=2026&month=3")
        self.assertEqual(readiness.status_code, status.HTTP_200_OK, readiness.data)
        self.assertEqual(readiness.data["status"], SettlementProfile.ReadinessStatus.READY)
        self.assertEqual(readiness.data["blockers"], [])

        first = self.client.post(
            "/api/budget/settlement/activate/",
            {"activation_date": "2026-03-01"},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        self.assertTrue(first.data["is_enabled"])
        self.assertEqual(SettlementOpeningBalance.objects.count(), 4)
        shared_balances = SettlementOpeningBalance.objects.filter(
            account__asset=self.operating
        ).order_by("member_id")
        self.assertEqual(
            [row.amount for row in shared_balances],
            [Decimal("500.00000000"), Decimal("500.00000000")],
        )

        second = self.client.post(
            "/api/budget/settlement/activate/",
            {"activation_date": "2026-03-01"},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(SettlementOpeningBalance.objects.count(), 4)

        self.client.post("/api/budget/settlement/disable/", format="json")
        self.operating.amount = Decimal("2000.00")
        self.operating.save(update_fields=["amount"])
        reactivated = self.client.post(
            "/api/budget/settlement/activate/",
            {"activation_date": "2026-04-01"},
            format="json",
        )
        self.assertEqual(reactivated.status_code, status.HTTP_200_OK)
        self.assertEqual(
            list(shared_balances.values_list("amount", flat=True)),
            [Decimal("500.00000000"), Decimal("500.00000000")],
        )

    def test_readiness_does_not_require_ownership_on_aggregate_income_budget(self):
        self._configure()
        self._shared_expense()
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Dividendos agregados",
            category=AnnualIncomeEntry.Category.PASSIVE_INCOME,
            subcategory="dividends",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
        )

        response = self.client.get("/api/budget/settlement/readiness/?year=2026&month=3")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], SettlementProfile.ReadinessStatus.READY)
        self.assertEqual(response.data["blockers"], [])

    def test_wallet_records_physical_cash_and_zero_sum_compensation_without_history_edit(self):
        wallet = self._asset(
            "Monedero mixto",
            Decimal("100.00"),
            self.shared,
            subcategory=Asset.Subcategory.WALLET,
        )
        self._configure(
            extra_accounts=[
                {
                    "asset_id": wallet.id,
                    "role": SettlementAccount.Role.PHYSICAL_CASH,
                    "accepted_physical_balance": "20.00",
                }
            ],
            adjustments=[
                {
                    "asset_id": wallet.id,
                    "member_id": self.member_a.id,
                    "amount": "80.00",
                    "kind": SettlementOpeningAdjustment.Kind.WALLET_NORMALIZATION,
                },
                {
                    "asset_id": wallet.id,
                    "member_id": self.member_b.id,
                    "amount": "-80.00",
                    "kind": SettlementOpeningAdjustment.Kind.WALLET_NORMALIZATION,
                },
            ],
        )
        self._shared_expense()

        response = self.client.post(
            "/api/budget/settlement/activate/",
            {"activation_date": "2026-03-01"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        wallet_row = next(row for row in response.data["accounts"] if row["asset_id"] == wallet.id)
        self.assertEqual(wallet_row["modeled_balance_at_activation"], Decimal("100.00000000"))
        self.assertEqual(wallet_row["accepted_physical_balance"], Decimal("20.00000000"))
        self.assertEqual(wallet_row["wallet_difference"], Decimal("80.00000000"))
        self.assertEqual(
            sum(
                row.amount
                for row in SettlementOpeningAdjustment.objects.filter(account__asset=wallet)
            ),
            Decimal("0"),
        )
        self.assertEqual(
            sum(
                row.amount for row in SettlementOpeningBalance.objects.filter(account__asset=wallet)
            ),
            Decimal("20.00000000"),
        )
        wallet.refresh_from_db()
        self.assertEqual(wallet.amount, Decimal("100.00000000"))

    def test_readiness_marks_a_mixed_wallet_without_compensation_as_pending(self):
        wallet = self._asset(
            "Monedero pendiente",
            Decimal("100.00"),
            self.shared,
            subcategory=Asset.Subcategory.WALLET,
        )
        self._configure(
            extra_accounts=[
                {
                    "asset_id": wallet.id,
                    "role": SettlementAccount.Role.PHYSICAL_CASH,
                    "accepted_physical_balance": "20.00",
                }
            ]
        )
        self._shared_expense()

        response = self.client.get("/api/budget/settlement/readiness/?year=2026&month=3")
        blocker = next(
            row for row in response.data["blockers"] if row["code"] == "wallet_adjustment_required"
        )
        self.assertEqual(blocker["difference"], "80.00")

    def test_readiness_ignores_subcent_wallet_difference(self):
        wallet = self._asset(
            "Monedero sin residuo monetario",
            Decimal("100.00"),
            self.shared,
            subcategory=Asset.Subcategory.WALLET,
        )
        self._configure(
            extra_accounts=[
                {
                    "asset_id": wallet.id,
                    "role": SettlementAccount.Role.PHYSICAL_CASH,
                    "accepted_physical_balance": "100.004",
                }
            ]
        )
        self._shared_expense()

        response = self.client.get("/api/budget/settlement/readiness/?year=2026&month=3")
        self.assertFalse(
            any(row["code"] == "wallet_adjustment_required" for row in response.data["blockers"])
        )

    @patch("budget.services_settlement.get_effective_asset_amount")
    def test_readiness_reconciles_wallets_on_the_requested_balance_date(self, effective_amount):
        wallet = self._asset(
            "Monedero fechado",
            Decimal("100.00"),
            self.shared,
            subcategory=Asset.Subcategory.WALLET,
        )
        self._configure(
            extra_accounts=[
                {
                    "asset_id": wallet.id,
                    "role": SettlementAccount.Role.PHYSICAL_CASH,
                    "accepted_physical_balance": "20.00",
                }
            ]
        )
        self._shared_expense()
        effective_amount.side_effect = lambda *, asset, as_of_date: (
            Decimal("100.00") if as_of_date == date(2026, 3, 1) else Decimal("20.00")
        )

        monthly = self.client.get("/api/budget/settlement/readiness/?year=2026&month=3")
        exact = self.client.get(
            "/api/budget/settlement/readiness/?year=2026&month=3&balance_date=2026-03-15"
        )

        self.assertEqual(monthly.data["status"], SettlementProfile.ReadinessStatus.BLOCKED)
        self.assertEqual(exact.data["status"], SettlementProfile.ReadinessStatus.READY)
        self.assertEqual(
            exact.data["wallet_reconciliations"],
            [
                {
                    "account_id": SettlementAccount.objects.get(asset=wallet).id,
                    "asset_id": wallet.id,
                    "asset_name": "Monedero fechado",
                    "currency": "EUR",
                    "balance_date": "2026-03-15",
                    "modeled_balance": "20.00",
                    "accepted_physical_balance": "20.00000000",
                    "difference": "0.00",
                    "normalization_recorded": False,
                }
            ],
        )

    def test_readiness_rejects_an_invalid_balance_date(self):
        response = self.client.get("/api/budget/settlement/readiness/?balance_date=15-03-2026")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_readiness_requires_a_route_only_when_operating_accounts_are_ambiguous(self):
        second_operating = self._asset("Segunda compartida", Decimal("50.00"), self.shared)
        self._configure(
            extra_accounts=[
                {
                    "asset_id": second_operating.id,
                    "role": SettlementAccount.Role.OPERATING,
                }
            ]
        )
        profile = SettlementProfile.objects.get(user=self.user)
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Reserva agregada",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
        )

        response = self.client.get("/api/budget/settlement/readiness/?year=2026&month=3")
        codes = {blocker["code"] for blocker in response.data["blockers"]}
        self.assertIn("expense_missing_settlement_account", codes)
        self.assertEqual(SettlementAccount.objects.filter(profile=profile).count(), 4)

    def test_readiness_warns_but_does_not_block_an_unrouted_allocation(self):
        self._configure()
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Ahorro e inversión agregado",
            category=AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
            subcategory="other_financial_investments",
            cashflow_role=AnnualExpenseEntry.CashflowRole.INVESTMENT,
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
        )

        response = self.client.get("/api/budget/settlement/readiness/?year=2026&month=3")

        self.assertEqual(response.data["status"], SettlementProfile.ReadinessStatus.READY)
        self.assertEqual(response.data["blockers"], [])
        self.assertIn(
            "allocation_missing_destination",
            {warning["code"] for warning in response.data["warnings"]},
        )

    def test_configuration_and_budget_reject_cross_user_references(self):
        other = get_user_model().objects.create_user(username="other_settlement", password="pass")
        other_member = FamilyMember.objects.create(user=other, name="Other")
        other_ownership = Ownership.objects.create(
            user=other, kind=Ownership.Kind.INDIVIDUAL, member=other_member
        )
        other_asset = Asset.objects.create(
            user=other,
            name="Foreign",
            category=Asset.Category.CASH,
            amount=Decimal("1.00"),
        )
        config = self.client.put(
            "/api/budget/settlement/configuration/",
            {
                "base_currency": "EUR",
                "accounts": [
                    {"asset_id": other_asset.id, "role": SettlementAccount.Role.OPERATING}
                ],
            },
            format="json",
        )
        self.assertEqual(config.status_code, status.HTTP_400_BAD_REQUEST)

        entry = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Own expense",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            amount_annual=Decimal("120.00"),
            fiscal_year=2026,
        )
        update = self.client.patch(
            f"/api/budget/annual-expense/{entry.id}/",
            {"ownership_id": other_ownership.id},
            format="json",
        )
        self.assertEqual(update.status_code, status.HTTP_400_BAD_REQUEST)


class GeneratedSettlementFieldsTests(APITestCase):
    def test_investment_budget_line_derives_ownership_and_destination(self):
        user = get_user_model().objects.create_user(
            username="generated_settlement", password="pass"
        )
        member_a = FamilyMember.objects.create(user=user, name="A")
        member_b = FamilyMember.objects.create(user=user, name="B")
        ownership = Ownership.objects.create(user=user, kind=Ownership.Kind.SHARED)
        ownership.splits.create(member=member_a, percent=Decimal("50"))
        ownership.splits.create(member=member_b, percent=Decimal("50"))
        investment = Asset.objects.create(
            user=user,
            name="MyInvestor compartida",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            amount=Decimal("1000"),
            currency="EUR",
            start_date=date(2025, 1, 1),
        )
        OwnershipLink.objects.create(
            user=user,
            ownership=ownership,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=investment.id,
        )
        profile = SettlementProfile.objects.create(user=user, base_currency="EUR")
        destination = SettlementAccount.objects.create(
            profile=profile,
            asset=investment,
            role=SettlementAccount.Role.ALLOCATION_DESTINATION,
            currency="EUR",
        )
        InvestmentContributionInterval.objects.create(
            asset=investment,
            start_date=date(2026, 1, 1),
            amount=Decimal("100"),
            frequency=Asset.InvestmentContributionFrequency.MONTHLY,
            currency="EUR",
        )

        sync_generated_budget_commitments_for_asset(asset=investment)

        entry = AnnualExpenseEntry.objects.filter(source_asset=investment).first()
        self.assertEqual(entry.ownership_id, ownership.id)
        self.assertEqual(entry.settlement_account_id, destination.id)
