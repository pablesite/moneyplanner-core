from datetime import date
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerTransaction
from accounting.services_ledger import get_account_balance
from accounting.services_quick_entry import create_quick_transaction
from budget.models import (
    MonthlyClose,
    SettlementAccount,
    SettlementProfile,
    SettlementSnapshot,
    SettlementTransferRecommendation,
)
from budget.services_monthly_close import reopen_monthly_close
from budget.services_settlement_execution import (
    apply_all_settlement_recommendations,
    apply_settlement_recommendation,
    cancel_settlement_recommendation,
    reconcile_settlement_recommendation,
    reverse_settlement_recommendation,
    settlement_reconciliation_candidates,
)
from memberships.models import FamilyMember, Ownership, OwnershipLink
from net_worth.models import Asset


class SettlementExecutionFixture:
    def build_fixture(self, *, username="execution"):
        self.user = get_user_model().objects.create_user(username=username, password="pass")
        self.member = FamilyMember.objects.create(user=self.user, name="Pablo")
        self.ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=self.member,
        )
        self.source, self.source_ledger = self._account("Compartida")
        self.destination, self.destination_ledger = self._account("Personal")
        self.profile = SettlementProfile.objects.create(
            user=self.user,
            is_enabled=True,
            activation_date=date(2026, 3, 1),
            base_currency="EUR",
        )
        self.source_config = SettlementAccount.objects.create(
            profile=self.profile,
            asset=self.source,
            role=SettlementAccount.Role.OPERATING,
            currency="EUR",
        )
        self.destination_config = SettlementAccount.objects.create(
            profile=self.profile,
            asset=self.destination,
            role=SettlementAccount.Role.PERSONAL_DESTINATION,
            member=self.member,
            currency="EUR",
            is_primary=True,
        )
        self.close = MonthlyClose.objects.create(
            user=self.user,
            fiscal_year=2026,
            month=3,
            status=MonthlyClose.Status.FINALIZED,
        )
        self.snapshot = SettlementSnapshot.objects.create(
            monthly_close=self.close,
            profile=self.profile,
            status=SettlementSnapshot.Status.READY,
            base_currency="EUR",
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            target_year=2026,
            target_month=4,
            opening_source="activation",
            source_hash="a" * 64,
        )
        self.recommendation = SettlementTransferRecommendation.objects.create(
            snapshot=self.snapshot,
            from_account=self.source_config,
            to_account=self.destination_config,
            member=self.member,
            ownership=self.ownership,
            amount=Decimal("100.00"),
            currency="EUR",
            reason="member_residual",
        )

    def _account(self, name):
        asset = Asset.objects.create(
            user=self.user,
            name=name,
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=Decimal("0"),
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
            ownership=self.ownership,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=asset.id,
        )
        return asset, ledger

    def manual_transfer(self, *, amount=Decimal("100.00"), description="Transferencia manual"):
        return create_quick_transaction(
            user=self.user,
            movement_type=LedgerTransaction.QuickEntryKind.TRANSFER,
            booking_date=date(2026, 4, 2),
            value_date=date(2026, 4, 2),
            description=description,
            amount=amount,
            account=self.source_ledger,
            counterparty_account=self.destination_ledger,
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.MANUAL,
            ownership=self.ownership,
        )


class SettlementExecutionServiceTests(SettlementExecutionFixture, TestCase):
    def setUp(self):
        self.build_fixture()

    def apply(self, **overrides):
        return apply_settlement_recommendation(
            user=self.user,
            close_id=self.close.id,
            recommendation_id=self.recommendation.id,
            execution_date=date(2026, 4, 2),
            **overrides,
        )

    def test_retry_creates_exactly_one_neutral_ledger_transfer(self):
        before_total = get_account_balance(account=self.source_ledger) + get_account_balance(
            account=self.destination_ledger
        )

        first = self.apply(idempotency_key="retry-key")
        second = self.apply(idempotency_key="retry-key")

        self.assertEqual(first["status"], "applied")
        self.assertEqual(second["transactions"], first["transactions"])
        transactions = LedgerTransaction.objects.filter(
            settlement_recommendation=self.recommendation
        )
        self.assertEqual(transactions.count(), 1)
        transaction_row = transactions.get()
        self.assertEqual(transaction_row.origin, LedgerTransaction.Origin.SYSTEM)
        self.assertEqual(
            transaction_row.quick_entry_kind, LedgerTransaction.QuickEntryKind.TRANSFER
        )
        self.assertEqual(transaction_row.ownership_id, self.ownership.id)
        self.assertFalse(transaction_row.entries.exclude(flow_family="").exists())
        after_total = get_account_balance(account=self.source_ledger) + get_account_balance(
            account=self.destination_ledger
        )
        self.assertEqual(after_total, before_total)

    def test_partial_execution_exposes_exact_remainder(self):
        partial = self.apply(amount=Decimal("40.00"), idempotency_key="partial-40")
        completed = self.apply()

        self.assertEqual(partial["status"], "partially_applied")
        self.assertEqual(partial["remaining_amount"], "60.00")
        self.assertEqual(completed["status"], "applied")
        self.assertEqual(completed["remaining_amount"], "0.00")
        self.assertEqual(len(completed["transactions"]), 2)

    def test_full_application_and_reversal_are_idempotent_without_client_key(self):
        first = self.apply()
        retry = self.apply()
        self.assertEqual(first["transactions"], retry["transactions"])

        reversed_once = reverse_settlement_recommendation(
            user=self.user,
            close_id=self.close.id,
            recommendation_id=self.recommendation.id,
            execution_date=date(2026, 4, 3),
        )
        reversed_retry = reverse_settlement_recommendation(
            user=self.user,
            close_id=self.close.id,
            recommendation_id=self.recommendation.id,
            execution_date=date(2026, 4, 3),
        )

        self.assertEqual(reversed_once["transactions"], reversed_retry["transactions"])
        self.assertEqual(LedgerTransaction.objects.count(), 2)

    def test_manual_transfer_can_be_linked_without_creating_another(self):
        transaction_row = self.manual_transfer()
        candidates = settlement_reconciliation_candidates(
            user=self.user,
            close_id=self.close.id,
            recommendation_id=self.recommendation.id,
        )

        self.assertEqual([row["transaction_id"] for row in candidates], [transaction_row.id])
        result = reconcile_settlement_recommendation(
            user=self.user,
            close_id=self.close.id,
            recommendation_id=self.recommendation.id,
            transaction_id=transaction_row.id,
        )

        self.assertEqual(result["status"], "applied")
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        transaction_row.refresh_from_db()
        self.assertEqual(transaction_row.settlement_action, "reconciliation")

    def test_ambiguous_manual_candidates_are_returned_without_linking(self):
        first = self.manual_transfer(amount=Decimal("40"), description="Primera")
        second = self.manual_transfer(amount=Decimal("60"), description="Segunda")

        candidates = settlement_reconciliation_candidates(
            user=self.user,
            close_id=self.close.id,
            recommendation_id=self.recommendation.id,
        )

        self.assertEqual({row["transaction_id"] for row in candidates}, {first.id, second.id})
        self.assertFalse(
            LedgerTransaction.objects.filter(settlement_recommendation=self.recommendation).exists()
        )

    def test_cancelled_and_locked_recommendations_cannot_be_applied(self):
        cancelled = cancel_settlement_recommendation(
            user=self.user,
            close_id=self.close.id,
            recommendation_id=self.recommendation.id,
        )
        self.assertEqual(cancelled["status"], "cancelled")
        with self.assertRaises(ValidationError):
            self.apply()

        self.recommendation.status = SettlementTransferRecommendation.Status.RECOMMENDED
        self.recommendation.cancelled_at = None
        self.recommendation.save(update_fields=["status", "cancelled_at"])
        self.close.status = MonthlyClose.Status.LOCKED
        self.close.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            self.apply()

    def test_reopen_remains_blocked_after_auditable_reversal(self):
        self.apply()
        self.close.refresh_from_db()
        with self.assertRaisesRegex(ValueError, "histórico"):
            reopen_monthly_close(monthly_close=self.close)

        reversed_result = reverse_settlement_recommendation(
            user=self.user,
            close_id=self.close.id,
            recommendation_id=self.recommendation.id,
            execution_date=date(2026, 4, 3),
        )
        self.assertEqual(reversed_result["applied_amount"], "0.00")
        self.assertEqual(LedgerTransaction.objects.count(), 2)

        self.close.refresh_from_db()
        with self.assertRaisesRegex(ValueError, "histórico"):
            reopen_monthly_close(monthly_close=self.close)
        self.assertEqual(LedgerTransaction.objects.count(), 2)

    def test_apply_all_rolls_back_if_one_route_is_invalid(self):
        invalid_destination, invalid_ledger = self._account("Destino inactivo")
        invalid_config = SettlementAccount.objects.create(
            profile=self.profile,
            asset=invalid_destination,
            role=SettlementAccount.Role.PERSONAL_DESTINATION,
            member=self.member,
            currency="EUR",
        )
        invalid_ledger.is_active = False
        invalid_ledger.save(update_fields=["is_active"])
        SettlementTransferRecommendation.objects.create(
            snapshot=self.snapshot,
            from_account=self.source_config,
            to_account=invalid_config,
            member=self.member,
            ownership=self.ownership,
            amount=Decimal("50"),
            currency="EUR",
            sort_order=1,
        )

        with self.assertRaises(ValidationError):
            apply_all_settlement_recommendations(
                user=self.user, close_id=self.close.id, execution_date=date(2026, 4, 2)
            )

        self.recommendation.refresh_from_db()
        self.assertEqual(self.recommendation.status, "recommended")
        self.assertFalse(
            LedgerTransaction.objects.filter(settlement_recommendation__isnull=False).exists()
        )

    def test_other_user_cannot_apply_recommendation(self):
        other = get_user_model().objects.create_user(username="other", password="pass")
        with self.assertRaises(ValidationError):
            apply_settlement_recommendation(
                user=other,
                close_id=self.close.id,
                recommendation_id=self.recommendation.id,
                execution_date=date(2026, 4, 2),
            )


class SettlementExecutionApiTests(SettlementExecutionFixture, APITestCase):
    def setUp(self):
        self.build_fixture(username="execution-api")
        self.client.force_authenticate(self.user)

    def test_apply_endpoint_is_idempotent_and_exposes_state_in_close(self):
        url = (
            f"/api/budget/monthly-closes/{self.close.id}/settlement/recommendations/"
            f"{self.recommendation.id}/apply/"
        )
        payload = {"execution_date": "2026-04-02", "idempotency_key": "api-retry"}

        first = self.client.post(url, payload, format="json")
        second = self.client.post(url, payload, format="json")

        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(first.data["transactions"], second.data["transactions"])
        close = self.client.get("/api/budget/monthly-close/2026/3/")
        recommendation = close.data["ownership_settlement"]["recommendations"][0]
        self.assertEqual(recommendation["status"], "applied")
        self.assertEqual(recommendation["remaining_amount"], "0.00")

    def test_candidates_and_unknown_action_contract(self):
        transaction_row = self.manual_transfer()
        base = (
            f"/api/budget/monthly-closes/{self.close.id}/settlement/recommendations/"
            f"{self.recommendation.id}"
        )

        candidates = self.client.get(f"{base}/candidates/")
        missing = self.client.post(f"{base}/unknown/", {}, format="json")

        self.assertEqual(candidates.status_code, 200)
        self.assertEqual(candidates.data["candidates"][0]["transaction_id"], transaction_row.id)
        self.assertEqual(missing.status_code, 404)


class SettlementExecutionConcurrencyTests(SettlementExecutionFixture, TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.build_fixture(username="execution-concurrent")

    def test_concurrent_retry_creates_exactly_one_transaction(self):
        barrier = Barrier(2)

        def apply_from_independent_connection():
            close_old_connections()
            user = get_user_model().objects.get(id=self.user.id)
            barrier.wait(timeout=5)
            try:
                return apply_settlement_recommendation(
                    user=user,
                    close_id=self.close.id,
                    recommendation_id=self.recommendation.id,
                    execution_date=date(2026, 4, 2),
                    idempotency_key="concurrent-key",
                )["status"]
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda _: apply_from_independent_connection(), range(2)))

        self.assertEqual(statuses, ["applied", "applied"])
        self.assertEqual(
            LedgerTransaction.objects.filter(
                settlement_recommendation=self.recommendation,
                settlement_action=LedgerTransaction.SettlementAction.APPLICATION,
            ).count(),
            1,
        )
