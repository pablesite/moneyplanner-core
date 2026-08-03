from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from core.models import FxRate
from memberships.models import (
    FamilyMember,
    Ownership,
    OwnershipAllocationSnapshot,
    OwnershipIncomeRule,
    OwnershipLink,
)
from memberships.services_allocations import allocation_window, resolve_ownership_allocation


class AllocationFixtureMixin:
    def build_ownerships(self, *, user):
        member_a = FamilyMember.objects.create(user=user, name="Pablo")
        member_b = FamilyMember.objects.create(user=user, name="Ana")
        individual_a = Ownership.objects.create(
            user=user, kind=Ownership.Kind.INDIVIDUAL, member=member_a
        )
        individual_b = Ownership.objects.create(
            user=user, kind=Ownership.Kind.INDIVIDUAL, member=member_b
        )
        shared = Ownership.objects.create(
            user=user,
            kind=Ownership.Kind.SHARED,
            allocation_basis=Ownership.AllocationBasis.RECURRING_INCOME_12M,
        )
        shared.splits.create(member=member_a, percent=Decimal("50.00"))
        shared.splits.create(member=member_b, percent=Decimal("50.00"))
        OwnershipIncomeRule.objects.create(ownership=shared, category_key="salary")
        account = LedgerAccount.objects.create(
            user=user,
            name="Income",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        return member_a, member_b, individual_a, individual_b, shared, account

    def add_income(
        self,
        *,
        user,
        ownership,
        account,
        booking_date,
        amount,
        currency="EUR",
        category_key="salary",
        status=LedgerTransaction.Status.POSTED,
    ):
        transaction = LedgerTransaction.objects.create(
            user=user,
            booking_date=booking_date,
            value_date=booking_date,
            description="Income",
            status=status,
            ownership=ownership,
        )
        entry = LedgerEntry.objects.create(
            transaction=transaction,
            account=account,
            side=LedgerEntry.Side.CREDIT,
            amount=amount,
            currency=currency,
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key=category_key,
            subcategory_key="employee_salary",
        )
        return transaction, entry


class OwnershipAllocationTests(AllocationFixtureMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="allocation", password="pass")
        (
            self.member_a,
            self.member_b,
            self.individual_a,
            self.individual_b,
            self.shared,
            self.account,
        ) = self.build_ownerships(user=self.user)

    def test_window_uses_previous_twelve_complete_months_across_year_boundary(self):
        self.assertEqual(
            allocation_window(fiscal_year=2026, month=1),
            (date(2025, 1, 1), date(2025, 12, 31)),
        )
        self.assertEqual(
            allocation_window(fiscal_year=2026, month=7),
            (date(2025, 7, 1), date(2026, 6, 30)),
        )

    def test_dynamic_allocation_reconciles_to_exactly_one_hundred_percent(self):
        for month in range(1, 13):
            booking_date = date(2025, month, 15)
            self.add_income(
                user=self.user,
                ownership=self.individual_a,
                account=self.account,
                booking_date=booking_date,
                amount=Decimal("610.00"),
            )
            self.add_income(
                user=self.user,
                ownership=self.individual_b,
                account=self.account,
                booking_date=booking_date,
                amount=Decimal("390.00"),
            )

        result = resolve_ownership_allocation(ownership=self.shared, fiscal_year=2026, month=1)

        self.assertEqual(result["status"], OwnershipAllocationSnapshot.Status.READY)
        self.assertEqual(result["observed_months"], 12)
        self.assertEqual(result["total_qualifying_income"], "12000.00000000")
        self.assertEqual([share["percent"] for share in result["shares"]], ["61.00", "39.00"])
        self.assertEqual(
            sum(Decimal(share["percent"]) for share in result["shares"]), Decimal("100.00")
        )

    def test_preview_excludes_drafts_and_non_matching_taxonomy(self):
        for month in range(1, 4):
            booking_date = date(2025, month, 1)
            self.add_income(
                user=self.user,
                ownership=self.individual_a,
                account=self.account,
                booking_date=booking_date,
                amount=Decimal("100.00"),
            )
        self.add_income(
            user=self.user,
            ownership=self.individual_b,
            account=self.account,
            booking_date=date(2025, 2, 1),
            amount=Decimal("900.00"),
            category_key="investment_income",
        )
        self.add_income(
            user=self.user,
            ownership=self.individual_b,
            account=self.account,
            booking_date=date(2025, 2, 1),
            amount=Decimal("900.00"),
            status=LedgerTransaction.Status.DRAFT,
        )

        result = resolve_ownership_allocation(
            ownership=self.shared, fiscal_year=2026, month=1, persist=False
        )

        self.assertEqual(result["status"], OwnershipAllocationSnapshot.Status.PROVISIONAL)
        self.assertEqual(result["quality_reasons"], ["partial_history"])
        self.assertEqual(result["eligible_transaction_count"], 3)
        self.assertEqual(result["excluded_transaction_count"], 1)

    def test_fx_uses_rate_available_on_movement_date(self):
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate_date=date(2025, 1, 1),
            rate=Decimal("2.00"),
        )
        for month in range(1, 4):
            self.add_income(
                user=self.user,
                ownership=self.individual_a,
                account=self.account,
                booking_date=date(2025, month, 1),
                amount=Decimal("100.00"),
                currency="USD",
            )
            self.add_income(
                user=self.user,
                ownership=self.individual_b,
                account=self.account,
                booking_date=date(2025, month, 1),
                amount=Decimal("200.00"),
            )

        result = resolve_ownership_allocation(
            ownership=self.shared, fiscal_year=2026, month=1, persist=False
        )
        self.assertEqual([row["percent"] for row in result["shares"]], ["50.00", "50.00"])

    def test_frozen_snapshot_is_not_recalculated_after_source_edit(self):
        for month in range(1, 4):
            _, entry = self.add_income(
                user=self.user,
                ownership=self.individual_a,
                account=self.account,
                booking_date=date(2025, month, 1),
                amount=Decimal("100.00"),
            )
            self.add_income(
                user=self.user,
                ownership=self.individual_b,
                account=self.account,
                booking_date=date(2025, month, 1),
                amount=Decimal("100.00"),
            )
        first = resolve_ownership_allocation(
            ownership=self.shared, fiscal_year=2026, month=1, freeze=True
        )
        entry.amount = Decimal("9999.00")
        entry.save()

        second = resolve_ownership_allocation(ownership=self.shared, fiscal_year=2026, month=1)
        self.assertTrue(second["is_frozen"])
        self.assertEqual(second["source_hash"], first["source_hash"])
        self.assertEqual(second["shares"], first["shares"])

    def test_readiness_command_does_not_persist_snapshots(self):
        output = StringIO()
        call_command(
            "audit_ownership_allocation",
            user_id=self.user.id,
            year=2026,
            month=1,
            stdout=output,
        )
        self.assertIn('"status": "blocked"', output.getvalue())
        self.assertFalse(OwnershipAllocationSnapshot.objects.exists())


class OwnershipAllocationApiTests(AllocationFixtureMixin, APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="api_allocation", password="pass")
        *_, self.shared, self.account = self.build_ownerships(user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_in_use_ownership_allows_only_allocation_configuration_updates(self):
        OwnershipLink.objects.create(
            user=self.user,
            ownership=self.shared,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=1,
        )
        response = self.client.patch(
            f"/api/ownerships/{self.shared.id}/",
            {
                "allocation_basis": Ownership.AllocationBasis.RECURRING_INCOME_12M,
                "income_rules": [{"category_key": "salary", "subcategory_key": ""}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        split_response = self.client.patch(
            f"/api/ownerships/{self.shared.id}/",
            {"splits": [{"member_id": self.shared.splits.first().member_id, "percent": "100"}]},
            format="json",
        )
        self.assertEqual(split_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_individual_ownership_rejects_dynamic_allocation(self):
        individual = Ownership.objects.filter(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL
        ).first()
        response = self.client.patch(
            f"/api/ownerships/{individual.id}/",
            {"allocation_basis": Ownership.AllocationBasis.RECURRING_INCOME_12M},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("allocation_basis", response.data["error"]["details"])

    def test_preview_is_tenant_scoped(self):
        other_user = get_user_model().objects.create_user(username="other", password="pass")
        *_, other_shared, _ = self.build_ownerships(user=other_user)
        response = self.client.get(
            f"/api/ownerships/{other_shared.id}/allocation-preview/?year=2026&month=1"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
