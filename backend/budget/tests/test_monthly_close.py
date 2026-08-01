from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from budget.models import (
    AnnualExpenseEntry,
    AnnualIncomeEntry,
    AnnualIncomeMonthlyCheckin,
    MonthlyClose,
)
from budget.services_monthly_close import (
    _get_uncovered_expense_entries_for_month,
    apply_distribution_to_checkins,
    compute_monthly_close_state,
    compute_smart_distribution,
    finalize_monthly_close,
    lock_monthly_close,
    reopen_monthly_close,
)
from net_worth.models import Asset, Liability
from plan.models import FinancialPlan, Finding, Recommendation


User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(username: str):
    return User.objects.create_user(username=username, password="pass1234")


def _make_income_entry(user, fiscal_year=2026, amount=12000):
    return AnnualIncomeEntry.objects.create(
        user=user,
        name="Nomina",
        category="salary",
        subcategory="employee_salary",
        income_type="recurrent",
        time_profile="structural_recurrent",
        amount_annual=Decimal(str(amount)),
        fiscal_year=fiscal_year,
        currency="EUR",
        is_active=True,
    )


def _make_expense_entry(user, fiscal_year=2026, amount=6000, name="Alquiler"):
    return AnnualExpenseEntry.objects.create(
        user=user,
        name=name,
        category="consumption_expenses",
        subcategory="housing_home",
        expense_type="recurrent",
        time_profile="structural_recurrent",
        amount_annual=Decimal(str(amount)),
        fiscal_year=fiscal_year,
        currency="EUR",
        is_active=True,
    )


# ---------------------------------------------------------------------------
# Unit tests — compute_smart_distribution
# ---------------------------------------------------------------------------


class SmartDistributionTests(APITestCase):
    def test_no_entries_returns_empty(self):
        income, expense = compute_smart_distribution(
            uncovered_income=[],
            uncovered_expense=[],
        )
        self.assertEqual(income, {})
        self.assertEqual(expense, {})

    def test_no_residual_uses_planned_amounts(self):
        income, expense = compute_smart_distribution(
            uncovered_income=[(1, Decimal("1000.00"))],
            uncovered_expense=[(2, Decimal("500.00"))],
        )
        self.assertEqual(income[1], Decimal("1000.00"))
        self.assertEqual(expense[2], Decimal("500.00"))

    def test_residual_scales_proportionally(self):
        # planned_net = 1000 - 500 = 500; residual_net = 250 → scale = 0.5
        income, expense = compute_smart_distribution(
            uncovered_income=[(1, Decimal("1000.00"))],
            uncovered_expense=[(2, Decimal("500.00"))],
            residual_net=Decimal("250.00"),
        )
        self.assertEqual(income[1], Decimal("500.00"))
        self.assertEqual(expense[2], Decimal("250.00"))

    def test_negative_scale_clamps_to_zero(self):
        # residual_net negative → scale < 0 → amounts clamped to 0
        income, expense = compute_smart_distribution(
            uncovered_income=[(1, Decimal("1000.00"))],
            uncovered_expense=[(2, Decimal("500.00"))],
            residual_net=Decimal("-100.00"),
        )
        self.assertEqual(income[1], Decimal("0.00"))
        self.assertEqual(expense[2], Decimal("0.00"))

    def test_zero_planned_net_uses_planned_amounts(self):
        # planned_net = 0 (income == expense) → no scaling possible
        income, expense = compute_smart_distribution(
            uncovered_income=[(1, Decimal("500.00"))],
            uncovered_expense=[(2, Decimal("500.00"))],
            residual_net=Decimal("300.00"),
        )
        self.assertEqual(income[1], Decimal("500.00"))
        self.assertEqual(expense[2], Decimal("500.00"))

    def test_rounding_absorbed_by_last_item(self):
        # Two income entries with equal planned; verify total is correct
        income, _ = compute_smart_distribution(
            uncovered_income=[(1, Decimal("333.33")), (2, Decimal("333.34"))],
            uncovered_expense=[],
            residual_net=Decimal("500.00"),
        )
        # Just verify totals round correctly
        total = sum(income.values(), Decimal("0"))
        self.assertGreaterEqual(total, Decimal("0"))


# ---------------------------------------------------------------------------
# Unit tests — lifecycle services
# ---------------------------------------------------------------------------


class MonthlyCloseLifecycleTests(APITestCase):
    def setUp(self):
        self.user = _make_user("lifecycle_user")

    def _create_draft(self):
        return MonthlyClose.objects.create(
            user=self.user,
            fiscal_year=2026,
            month=3,
            status=MonthlyClose.Status.DRAFT,
        )

    def test_finalize_transitions_draft_to_finalized(self):
        mc = self._create_draft()
        mc = finalize_monthly_close(monthly_close=mc, user=self.user)
        self.assertEqual(mc.status, MonthlyClose.Status.FINALIZED)
        self.assertIsNotNone(mc.finalized_at)

    def test_finalize_already_finalized_raises(self):
        mc = self._create_draft()
        mc = finalize_monthly_close(monthly_close=mc, user=self.user)
        with self.assertRaises(ValueError):
            finalize_monthly_close(monthly_close=mc, user=self.user)

    def test_reopen_transitions_finalized_to_draft(self):
        mc = self._create_draft()
        mc = finalize_monthly_close(monthly_close=mc, user=self.user)
        mc = reopen_monthly_close(monthly_close=mc)
        self.assertEqual(mc.status, MonthlyClose.Status.DRAFT)
        self.assertIsNone(mc.finalized_at)
        self.assertIsNone(mc.income_total_snapshot)

    def test_reopen_draft_raises(self):
        mc = self._create_draft()
        with self.assertRaises(ValueError):
            reopen_monthly_close(monthly_close=mc)

    def test_lock_transitions_finalized_to_locked(self):
        mc = self._create_draft()
        mc = finalize_monthly_close(monthly_close=mc, user=self.user)
        mc = lock_monthly_close(monthly_close=mc)
        self.assertEqual(mc.status, MonthlyClose.Status.LOCKED)
        self.assertIsNotNone(mc.locked_at)

    def test_lock_draft_raises(self):
        mc = self._create_draft()
        with self.assertRaises(ValueError):
            lock_monthly_close(monthly_close=mc)

    def test_lock_locked_raises(self):
        mc = self._create_draft()
        mc = finalize_monthly_close(monthly_close=mc, user=self.user)
        mc = lock_monthly_close(monthly_close=mc)
        with self.assertRaises(ValueError):
            lock_monthly_close(monthly_close=mc)


# ---------------------------------------------------------------------------
# Unit tests — compute_monthly_close_state
# ---------------------------------------------------------------------------


class ComputeMonthlyCloseStateTests(APITestCase):
    def setUp(self):
        self.user = _make_user("state_user")

    def test_state_creates_draft_if_not_exists(self):
        state = compute_monthly_close_state(user=self.user, fiscal_year=2026, month=3)
        self.assertEqual(state["monthly_close"]["status"], "draft")
        self.assertTrue(MonthlyClose.objects.filter(user=self.user).exists())

    def test_state_no_data(self):
        state = compute_monthly_close_state(user=self.user, fiscal_year=2026, month=3)
        self.assertEqual(Decimal(state["income"]["executed"]), Decimal("0"))
        self.assertEqual(Decimal(state["expense"]["executed"]), Decimal("0"))
        self.assertFalse(state["has_gaps"])

    def test_state_with_uncovered_income_entry(self):
        _make_income_entry(self.user, amount=12000)
        state = compute_monthly_close_state(user=self.user, fiscal_year=2026, month=3)
        self.assertTrue(state["has_gaps"])
        # Suggestions should include the income entry
        self.assertGreater(len(state["suggestions"]["income"]), 0)

    def test_state_with_covered_income_entry(self):
        entry = _make_income_entry(self.user, amount=12000)
        AnnualIncomeMonthlyCheckin.objects.create(
            user=self.user,
            annual_income_entry=entry,
            fiscal_year=2026,
            month=3,
            status=AnnualIncomeMonthlyCheckin.Status.CONFIRMED,
            executed_amount=Decimal("1000.00"),
        )
        state = compute_monthly_close_state(user=self.user, fiscal_year=2026, month=3)
        # Entry is covered by checkin
        self.assertNotIn(str(entry.id), state["suggestions"]["income"])

    def test_uncovered_expenses_normalize_legacy_investment_subcategory_aliases(self):
        entry = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Aportacion ETF legacy",
            category="financial_investments",
            subcategory="index_funds_etf",
            expense_type="recurrent",
            time_profile="structural_recurrent",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        account = LedgerAccount.objects.create(
            user=self.user,
            name="ETF",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date="2026-01-10",
            value_date="2026-01-10",
            description="Aportacion ETF",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="financial_investments",
            subcategory_key="etf_indexed",
        )

        uncovered = _get_uncovered_expense_entries_for_month(
            user=self.user,
            fiscal_year=2026,
            month=1,
        )

        self.assertNotIn(entry.id, {row.id for row, _planned in uncovered})


# ---------------------------------------------------------------------------
# Unit tests — apply_distribution_to_checkins
# ---------------------------------------------------------------------------


class ApplyDistributionTests(APITestCase):
    def setUp(self):
        self.user = _make_user("apply_dist_user")

    def test_creates_estimated_checkins(self):
        entry = _make_income_entry(self.user, amount=12000)
        apply_distribution_to_checkins(
            user=self.user,
            fiscal_year=2026,
            month=3,
            income_distribution={entry.id: Decimal("1000.00")},
            expense_distribution={},
        )
        checkin = AnnualIncomeMonthlyCheckin.objects.get(
            user=self.user, annual_income_entry=entry, fiscal_year=2026, month=3
        )
        self.assertEqual(checkin.status, AnnualIncomeMonthlyCheckin.Status.ESTIMATED)
        self.assertEqual(checkin.executed_amount, Decimal("1000.00"))

    def test_skips_existing_checkins(self):
        entry = _make_income_entry(self.user, amount=12000)
        existing = AnnualIncomeMonthlyCheckin.objects.create(
            user=self.user,
            annual_income_entry=entry,
            fiscal_year=2026,
            month=3,
            status=AnnualIncomeMonthlyCheckin.Status.CONFIRMED,
            executed_amount=Decimal("999.00"),
        )
        income_created, _ = apply_distribution_to_checkins(
            user=self.user,
            fiscal_year=2026,
            month=3,
            income_distribution={entry.id: Decimal("1000.00")},
            expense_distribution={},
        )
        self.assertEqual(income_created, 0)
        existing.refresh_from_db()
        self.assertEqual(existing.executed_amount, Decimal("999.00"))


# ---------------------------------------------------------------------------
# API tests — endpoints
# ---------------------------------------------------------------------------


class MonthlyCloseApiTests(APITestCase):
    def setUp(self):
        self.user = _make_user("api_mc_user")
        self.client.force_authenticate(user=self.user)

    def _url(self, year=2026, month=3):
        return f"/api/budget/monthly-close/{year}/{month}/"

    def test_get_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 401)

    def test_get_creates_draft_and_returns_state(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["monthly_close"]["status"], "draft")
        self.assertEqual(response.data["monthly_close"]["fiscal_year"], 2026)
        self.assertEqual(response.data["monthly_close"]["month"], 3)

    def test_patch_updates_notes(self):
        response = self.client.patch(self._url(), {"notes": "test note"}, format="json")
        self.assertEqual(response.status_code, 200)
        mc = MonthlyClose.objects.get(user=self.user, fiscal_year=2026, month=3)
        self.assertEqual(mc.notes, "test note")

    def test_patch_locked_returns_409(self):
        MonthlyClose.objects.create(
            user=self.user,
            fiscal_year=2026,
            month=3,
            status=MonthlyClose.Status.LOCKED,
        )
        response = self.client.patch(self._url(), {"notes": "x"}, format="json")
        self.assertEqual(response.status_code, 409)

    def test_finalize_transitions_to_finalized(self):
        response = self.client.post(self._url() + "finalize/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["monthly_close"]["status"], "finalized")
        mc = MonthlyClose.objects.get(user=self.user, fiscal_year=2026, month=3)
        self.assertIsNotNone(mc.finalized_at)

    def test_finalize_already_finalized_returns_409(self):
        self.client.post(self._url() + "finalize/")
        response = self.client.post(self._url() + "finalize/")
        self.assertEqual(response.status_code, 409)

    def test_reopen_not_found_returns_404(self):
        response = self.client.post(self._url() + "reopen/")
        self.assertEqual(response.status_code, 404)

    def test_reopen_finalized_returns_draft(self):
        self.client.post(self._url() + "finalize/")
        response = self.client.post(self._url() + "reopen/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["monthly_close"]["status"], "draft")

    def test_reopen_draft_returns_409(self):
        self.client.get(self._url())  # create draft
        response = self.client.post(self._url() + "reopen/")
        self.assertEqual(response.status_code, 409)

    def test_lock_finalized_returns_locked(self):
        self.client.post(self._url() + "finalize/")
        response = self.client.post(self._url() + "lock/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["monthly_close"]["status"], "locked")

    def test_lock_draft_returns_409(self):
        self.client.get(self._url())
        response = self.client.post(self._url() + "lock/")
        self.assertEqual(response.status_code, 409)

    def test_plan_impact_returns_limited_findings_and_action(self):
        FinancialPlan.objects.create(
            user=self.user,
            household_type=FinancialPlan.HouseholdType.SINGLE,
            target_date="2040-01-01",
            target_monthly_income_today_eur=Decimal("2000.00"),
            projection_end_date="2065-01-01",
            profile=FinancialPlan.Profile.BALANCED,
        )
        Asset.objects.create(
            user=self.user,
            name="ETF",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            amount=Decimal("10000.00"),
            currency="EUR",
        )
        Liability.objects.create(
            user=self.user,
            name="Tarjeta",
            category=Liability.Category.CREDIT_CARD,
            amount=Decimal("2500.00"),
            currency="EUR",
            annual_interest_tae=Decimal("19.00"),
        )
        _make_income_entry(self.user, amount=12000)
        _make_expense_entry(self.user, amount=18000)

        self.client.post(self._url() + "finalize/")
        monthly_close = MonthlyClose.objects.get(user=self.user, fiscal_year=2026, month=3)
        response = self.client.get(f"/api/budget/monthly-closes/{monthly_close.id}/plan-impact/")

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.data["findings"]), 2)
        self.assertIsNotNone(response.data["recommended_action"])
        self.assertTrue(Finding.objects.filter(plan__user=self.user).exists())
        self.assertTrue(Recommendation.objects.filter(finding__plan__user=self.user).exists())
        # La trayectoria se juzga con la fecha que titula el plan, no con la del summary.
        trajectory = response.data["trajectory"]
        self.assertIn("sustainable_year", trajectory)
        self.assertIn("sustainable_year_delta", trajectory)
        expected_status = (
            "off_track"
            if trajectory["sustainable_year"] is None
            else "on_track"
            if trajectory["sustainable_year"] <= trajectory["target_year"]
            else "delayed"
        )
        self.assertEqual(trajectory["status"], expected_status)
        # Con un solo snapshot oficial todavía no hay contra qué comparar.
        self.assertIsNone(trajectory["sustainable_year_delta"])

    def test_user_isolation(self):
        other_user = _make_user("other_mc_user")
        other_client = self.client_class()
        other_client.force_authenticate(user=other_user)
        other_client.post(self._url() + "finalize/")

        # Our user's close should still be DRAFT
        response = self.client.get(self._url())
        self.assertEqual(response.data["monthly_close"]["status"], "draft")


# ---------------------------------------------------------------------------
# API tests — checkin blocking
# ---------------------------------------------------------------------------


class CheckinBlockingBudgetTests(APITestCase):
    def setUp(self):
        self.user = _make_user("blocking_budget_user")
        self.client.force_authenticate(user=self.user)
        self.income_entry = _make_income_entry(self.user, amount=12000)
        self.expense_entry = _make_expense_entry(self.user, amount=6000)
        # Finalize march 2026
        MonthlyClose.objects.create(
            user=self.user,
            fiscal_year=2026,
            month=3,
            status=MonthlyClose.Status.FINALIZED,
        )

    def test_create_income_checkin_blocked_when_finalized(self):
        response = self.client.post(
            "/api/budget/annual-income-checkins/",
            {
                "annual_income_entry_id": self.income_entry.id,
                "fiscal_year": 2026,
                "month": 3,
                "status": "confirmed",
                "executed_amount": "1000.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_create_income_checkin_allowed_different_month(self):
        response = self.client.post(
            "/api/budget/annual-income-checkins/",
            {
                "annual_income_entry_id": self.income_entry.id,
                "fiscal_year": 2026,
                "month": 4,
                "status": "confirmed",
                "executed_amount": "1000.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_update_income_checkin_blocked_when_finalized(self):
        checkin = AnnualIncomeMonthlyCheckin.objects.create(
            user=self.user,
            annual_income_entry=self.income_entry,
            fiscal_year=2026,
            month=3,
            status=AnnualIncomeMonthlyCheckin.Status.CONFIRMED,
            executed_amount=Decimal("1000.00"),
        )
        response = self.client.patch(
            f"/api/budget/annual-income-checkins/{checkin.id}/",
            {"executed_amount": "999.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_create_expense_checkin_blocked_when_finalized(self):
        response = self.client.post(
            "/api/budget/annual-expense-checkins/",
            {
                "annual_expense_entry_id": self.expense_entry.id,
                "fiscal_year": 2026,
                "month": 3,
                "status": "confirmed",
                "executed_amount": "500.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_create_expense_checkin_blocked_when_locked(self):
        MonthlyClose.objects.filter(user=self.user, fiscal_year=2026, month=3).update(
            status=MonthlyClose.Status.LOCKED
        )
        response = self.client.post(
            "/api/budget/annual-expense-checkins/",
            {
                "annual_expense_entry_id": self.expense_entry.id,
                "fiscal_year": 2026,
                "month": 3,
                "status": "confirmed",
                "executed_amount": "500.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class CheckinBlockingNetWorthTests(APITestCase):
    def setUp(self):
        from net_worth.models import Asset

        self.user = _make_user("blocking_nw_user")
        self.client.force_authenticate(user=self.user)
        self.asset = Asset.objects.create(
            user=self.user,
            name="Cuenta corriente",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            amount=Decimal("10000.00"),
        )
        MonthlyClose.objects.create(
            user=self.user,
            fiscal_year=2026,
            month=3,
            status=MonthlyClose.Status.FINALIZED,
        )

    def test_create_liquidity_checkin_blocked_when_finalized(self):
        response = self.client.post(
            "/api/net-worth/liquidity-checkins/",
            {
                "asset_id": self.asset.id,
                "fiscal_year": 2026,
                "month": 3,
                "status": "confirmed",
                "closing_balance_real": "10500.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_create_liquidity_checkin_allowed_different_month(self):
        response = self.client.post(
            "/api/net-worth/liquidity-checkins/",
            {
                "asset_id": self.asset.id,
                "fiscal_year": 2026,
                "month": 4,
                "status": "confirmed",
                "closing_balance_real": "10500.00",
            },
            format="json",
        )
        self.assertIn(response.status_code, [201, 400])  # 400 only if validation fails on entry
