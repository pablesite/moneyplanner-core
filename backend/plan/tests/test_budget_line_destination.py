from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from budget.models import AnnualExpenseEntry, SettlementAccount, SettlementProfile
from memberships.models import FamilyMember, Ownership, OwnershipLink
from net_worth.models import Asset
from plan.models import FinancialPlan, PlanEvent
from plan.services_events import _replace_planned_decision_financing_entries


class PlanBudgetLineDestinationTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="plan_route")
        self.other = get_user_model().objects.create_user(username="plan_route_other")
        self.client.force_authenticate(self.user)
        self.plan = FinancialPlan.objects.create(
            user=self.user,
            target_date=date(2040, 1, 1),
            projection_end_date=date(2060, 1, 1),
            target_monthly_income_today_eur=Decimal("2000"),
        )
        self.a = FamilyMember.objects.create(user=self.user, name="Pablo")
        self.b = FamilyMember.objects.create(user=self.user, name="Ana")
        self.shared = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED)
        self.shared.splits.create(member=self.a, percent=Decimal("50"))
        self.shared.splits.create(member=self.b, percent=Decimal("50"))
        self.event = PlanEvent.objects.create(
            plan=self.plan,
            name="Atrio",
            event_type="housing",
            ownership=self.shared,
            planned_date=date(2026, 11, 1),
            status=PlanEvent.Status.PLANNED,
        )
        self.profile = SettlementProfile.objects.create(user=self.user, is_enabled=True)
        self.account = self._account("MyInvestor", self.shared)
        self._account("Santander", self.shared)
        self.payload = {
            "start_year": 2026,
            "start_month": 11,
            "new_debt_principal": "12000",
            "new_debt_interest_rate": "0",
            "new_debt_term_years": 2,
        }
        _replace_planned_decision_financing_entries(event=self.event, payload=self.payload)
        self.entry = AnnualExpenseEntry.objects.get(
            user=self.user, event_group=f"plan_event:{self.event.id}", fiscal_year=2026
        )
        self.url = reverse(
            "financial-plan-event-budget-line-destination",
            kwargs={"pk": self.event.id, "entry_id": self.entry.id},
        )

    def _account(self, name, ownership):
        asset = Asset.objects.create(
            user=self.user, name=name, category="cash", subcategory="bank_account", amount=0
        )
        OwnershipLink.objects.create(
            user=self.user, ownership=ownership, target_type="asset", target_id=asset.id
        )
        return SettlementAccount.objects.create(
            profile=self.profile,
            asset=asset,
            role=SettlementAccount.Role.ALLOCATION_DESTINATION,
            currency="EUR",
        )

    def test_select_destination_without_changing_plan_line(self):
        before = (
            self.entry.amount_annual,
            self.entry.time_profile,
            self.entry.term_start_month,
            self.entry.ownership_id,
        )
        response = self.client.patch(
            self.url, {"settlement_account_id": self.account.id}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.settlement_account_id, self.account.id)
        self.assertEqual(
            before,
            (
                self.entry.amount_annual,
                self.entry.time_profile,
                self.entry.term_start_month,
                self.entry.ownership_id,
            ),
        )
        read = self.client.get(
            reverse("financial-plan-event-budget-lines", kwargs={"pk": self.event.id})
        )
        row = next(item for item in read.data["expenses"] if item["id"] == self.entry.id)
        self.assertTrue(row["settlement_editable"])
        self.assertEqual(len(row["settlement_destinations"]), 2)
        self.assertEqual(row["settlement_account_id"], self.account.id)
        self.assertEqual(
            self.client.patch(
                f"/api/budget/annual-expense/{self.entry.id}/",
                {"amount_annual": "1"},
                format="json",
            ).status_code,
            403,
        )

    def test_rejects_unrelated_fields_and_foreign_or_incompatible_account(self):
        self.assertEqual(
            self.client.patch(
                self.url,
                {"settlement_account_id": self.account.id, "amount_annual": "1"},
                format="json",
            ).status_code,
            400,
        )
        other_profile = SettlementProfile.objects.create(user=self.other, is_enabled=True)
        foreign_asset = Asset.objects.create(
            user=self.other, name="Foreign", category="cash", amount=0
        )
        foreign = SettlementAccount.objects.create(
            profile=other_profile,
            asset=foreign_asset,
            role="allocation_destination",
            currency="EUR",
        )
        self.assertEqual(
            self.client.patch(
                self.url, {"settlement_account_id": foreign.id}, format="json"
            ).status_code,
            404,
        )
        wallet = self._account(
            "Sin titularidad compatible",
            Ownership.objects.create(user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=self.a),
        )
        self.assertEqual(
            self.client.patch(
                self.url, {"settlement_account_id": wallet.id}, format="json"
            ).status_code,
            400,
        )
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.patch(self.url, {"settlement_account_id": None}, format="json").status_code,
            404,
        )

    def test_route_survives_regeneration_of_financing(self):
        self.entry.settlement_account = self.account
        self.entry.save(update_fields=["settlement_account"])
        _replace_planned_decision_financing_entries(event=self.event, payload=self.payload)
        regenerated = AnnualExpenseEntry.objects.get(
            user=self.user, event_group=f"plan_event:{self.event.id}", fiscal_year=2026
        )
        self.assertEqual(regenerated.settlement_account_id, self.account.id)

    def test_selects_once_for_all_financing_years_and_new_years(self):
        entries = AnnualExpenseEntry.objects.filter(
            user=self.user, event_group=f"plan_event:{self.event.id}"
        )
        original = list(entries.values_list("id", "fiscal_year", "amount_annual"))
        other = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Otra partida",
            category="consumption_expenses",
            subcategory="other_consumption_expenses",
            fiscal_year=2026,
            amount_annual=100,
            event_group=f"plan_event:{self.event.id}",
        )
        read = self.client.get(
            reverse("financial-plan-event-budget-lines", kwargs={"pk": self.event.id})
        )
        series_rows = [row for row in read.data["expenses"] if row["id"] != other.id]
        self.assertEqual(len({row["settlement_series_id"] for row in series_rows}), 1)
        self.assertEqual(series_rows[0]["settlement_series_id"], self.entry.id)
        response = self.client.patch(
            self.url,
            {"settlement_account_id": self.account.id, "apply_to_series": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data["updated_entry_ids"]), {row[0] for row in original})
        self.assertEqual(
            list(entries.exclude(pk=other.pk).values_list("id", "fiscal_year", "amount_annual")),
            original,
        )
        self.assertEqual(
            entries.exclude(pk=other.pk).filter(settlement_account=self.account).count(),
            len(original),
        )
        other.refresh_from_db()
        self.assertIsNone(other.settlement_account_id)

        self.payload["new_debt_term_years"] = 3
        _replace_planned_decision_financing_entries(event=self.event, payload=self.payload)
        regenerated = AnnualExpenseEntry.objects.filter(
            user=self.user, event_group=f"plan_event:{self.event.id}", is_system_generated=True
        )
        self.assertGreater(regenerated.count(), len(original))
        self.assertEqual(
            regenerated.filter(settlement_account=self.account).count(), regenerated.count()
        )

    def test_ambiguous_financing_series_is_not_bulk_updated(self):
        duplicate = AnnualExpenseEntry.objects.get(pk=self.entry.pk)
        duplicate.pk = None
        duplicate.save()
        response = self.client.patch(
            self.url,
            {"settlement_account_id": self.account.id, "apply_to_series": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            AnnualExpenseEntry.objects.filter(
                user=self.user,
                event_group=f"plan_event:{self.event.id}",
                settlement_account__isnull=False,
            ).exists()
        )

    def test_extension_does_not_infer_a_destination_from_mixed_years(self):
        rows = AnnualExpenseEntry.objects.filter(
            user=self.user, event_group=f"plan_event:{self.event.id}"
        ).order_by("fiscal_year")
        second_account = self.profile.accounts.exclude(id=self.account.id).get()
        first, second = list(rows[:2])
        first.settlement_account = self.account
        second.settlement_account = second_account
        first.save(update_fields=["settlement_account"])
        second.save(update_fields=["settlement_account"])
        self.payload["new_debt_term_years"] = 3

        _replace_planned_decision_financing_entries(event=self.event, payload=self.payload)

        regenerated = AnnualExpenseEntry.objects.filter(
            user=self.user, event_group=f"plan_event:{self.event.id}"
        )
        self.assertEqual(
            regenerated.get(fiscal_year=first.fiscal_year).settlement_account_id, self.account.id
        )
        self.assertEqual(
            regenerated.get(fiscal_year=second.fiscal_year).settlement_account_id, second_account.id
        )
        self.assertIsNone(regenerated.order_by("-fiscal_year").first().settlement_account_id)
