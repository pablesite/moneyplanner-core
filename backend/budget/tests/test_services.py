from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from budget.models import (
    AnnualExpenseEntry,
    AnnualExpenseMonthlyCheckin,
    AnnualIncomeEntry,
    AnnualIncomeMonthlyCheckin,
)
from budget.services import (
    EXPENSE_TAXONOMY,
    INCOME_TAXONOMY,
    build_expense_monthly_plan_vs_executed_summary,
    build_income_monthly_plan_vs_executed_summary,
    expense_entry_applies_to_fiscal_year,
    income_entry_applies_to_fiscal_year,
    planned_expense_monthly_distribution,
    planned_income_monthly_distribution,
    validate_annual_expense_taxonomy,
    validate_annual_income_taxonomy,
)


class BudgetServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="budget_services", password="pass"
        )
        self.cash = LedgerAccount.objects.create(
            user=self.user,
            name="Cash",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        self.income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Income",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        self.expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Expense",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

    def _post_income_entry(
        self,
        *,
        amount: str,
        month: int,
        category_key: str = "",
        subcategory_key: str = "",
        legacy: AnnualIncomeEntry | None = None,
    ) -> None:
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, month, 15),
            value_date=date(2026, month, 15),
            description=f"income-{month}",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal(amount),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal(amount),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME if category_key else "",
            category_key=category_key,
            subcategory_key=subcategory_key,
            annual_income_entry=legacy,
        )

    def _post_expense_entry(
        self,
        *,
        amount: str,
        month: int,
        category_key: str = "",
        subcategory_key: str = "",
        legacy: AnnualExpenseEntry | None = None,
    ) -> None:
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, month, 15),
            value_date=date(2026, month, 15),
            description=f"expense-{month}",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal(amount),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE if category_key else "",
            category_key=category_key,
            subcategory_key=subcategory_key,
            annual_expense_entry=legacy,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal(amount),
            currency="EUR",
        )

    def test_validate_annual_income_taxonomy(self):
        validate_annual_income_taxonomy(category="salary", subcategory="employee_salary")
        with self.assertRaises(ValidationError):
            validate_annual_income_taxonomy(category="salary", subcategory="inheritance")
        with self.assertRaises(ValidationError):
            validate_annual_income_taxonomy(category="unknown", subcategory="other")

    def test_income_taxonomy_has_fallback_subcategories(self):
        for category, options in INCOME_TAXONOMY.items():
            self.assertTrue(options, msg=f"{category} must define subcategories")
            has_fallback = any(opt.startswith("other") or opt == "other" for opt in options)
            self.assertTrue(has_fallback, msg=f"{category} must define fallback subcategory")

    def test_validate_annual_expense_taxonomy(self):
        validate_annual_expense_taxonomy(
            category="consumption_expenses",
            subcategory="living_expenses",
        )
        with self.assertRaises(ValidationError):
            validate_annual_expense_taxonomy(category="consumption_expenses", subcategory="crypto")
        with self.assertRaises(ValidationError):
            validate_annual_expense_taxonomy(category="unknown", subcategory="other")

    def test_expense_taxonomy_has_fallback_subcategories(self):
        for category, options in EXPENSE_TAXONOMY.items():
            self.assertTrue(options, msg=f"{category} must define subcategories")
            has_fallback = any(opt.startswith("other") or opt == "other" for opt in options)
            self.assertTrue(has_fallback, msg=f"{category} must define fallback subcategory")

    def test_expense_entry_applies_to_fiscal_year_for_one_off_and_term(self):
        one_off = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Seguro",
            category="consumption_expenses",
            subcategory="transport_mobility",
            time_profile=AnnualExpenseEntry.TimeProfile.ONE_OFF,
            target_month=4,
            amount_annual=Decimal("240.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        self.assertTrue(expense_entry_applies_to_fiscal_year(entry=one_off, fiscal_year=2026))
        self.assertFalse(expense_entry_applies_to_fiscal_year(entry=one_off, fiscal_year=2025))

        term = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Cuota",
            category="consumption_expenses",
            subcategory="financial_commitments",
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            term_end_year=2027,
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        self.assertTrue(expense_entry_applies_to_fiscal_year(entry=term, fiscal_year=2027))
        self.assertFalse(expense_entry_applies_to_fiscal_year(entry=term, fiscal_year=2028))

    def test_income_entry_applies_to_fiscal_year_for_one_off_and_term(self):
        one_off = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Bonus",
            category="salary",
            subcategory="bonus_commission",
            time_profile=AnnualIncomeEntry.TimeProfile.ONE_OFF,
            target_month=4,
            amount_annual=Decimal("600.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        self.assertTrue(income_entry_applies_to_fiscal_year(entry=one_off, fiscal_year=2026))
        self.assertFalse(income_entry_applies_to_fiscal_year(entry=one_off, fiscal_year=2025))

        term = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Proyecto temporal",
            category="business",
            subcategory="self_employed_services",
            time_profile=AnnualIncomeEntry.TimeProfile.TERM_RECURRENT,
            term_end_year=2027,
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        self.assertTrue(income_entry_applies_to_fiscal_year(entry=term, fiscal_year=2027))
        self.assertFalse(income_entry_applies_to_fiscal_year(entry=term, fiscal_year=2028))

    def test_planned_expense_distribution_handles_one_off_and_term_end(self):
        one_off = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Seguro",
            category="consumption_expenses",
            subcategory="transport_mobility",
            time_profile=AnnualExpenseEntry.TimeProfile.ONE_OFF,
            target_month=3,
            amount_annual=Decimal("600.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        self.assertEqual(
            planned_expense_monthly_distribution(entry=one_off, fiscal_year=2026),
            {3: Decimal("600.00")},
        )

        term = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Compromiso temporal",
            category="consumption_expenses",
            subcategory="financial_commitments",
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            term_end_month=6,
            term_end_year=2026,
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        distribution = planned_expense_monthly_distribution(entry=term, fiscal_year=2026)
        self.assertEqual(len(distribution), 6)
        self.assertEqual(distribution[1], Decimal("100.00"))
        self.assertEqual(sum(distribution.values()), Decimal("1200.00"))

    def test_planned_income_distribution_handles_one_off_and_term_end(self):
        one_off = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Venta",
            category="capital_gains",
            subcategory="sale_personal_asset",
            time_profile=AnnualIncomeEntry.TimeProfile.ONE_OFF,
            target_month=8,
            amount_annual=Decimal("1500.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        self.assertEqual(
            planned_income_monthly_distribution(entry=one_off, fiscal_year=2026),
            {8: Decimal("1500.00")},
        )

        term = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Contrato",
            category="business",
            subcategory="self_employed_services",
            time_profile=AnnualIncomeEntry.TimeProfile.TERM_RECURRENT,
            term_end_month=4,
            term_end_year=2026,
            amount_annual=Decimal("4000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        distribution = planned_income_monthly_distribution(entry=term, fiscal_year=2026)
        self.assertEqual(len(distribution), 4)
        self.assertEqual(sum(distribution.values()), Decimal("4000.00"))

    def test_income_summary_returns_none_coverage_without_entries(self):
        summary = build_income_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        self.assertEqual(summary["planned_total"], "0.00")
        self.assertEqual(summary["executed_total"], "0.00")
        self.assertEqual(summary["pending_total"], "0.00")
        self.assertEqual(summary["coverage_mode"], "none")
        self.assertEqual(summary["months_with_coverage"], 0)

    def test_expense_summary_uses_checkin_fallback_when_no_ledger(self):
        entry = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Hogar",
            category="consumption_expenses",
            subcategory="living_expenses",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        AnnualExpenseMonthlyCheckin.objects.create(
            user=self.user,
            annual_expense_entry=entry,
            fiscal_year=2026,
            month=2,
            status=AnnualExpenseMonthlyCheckin.Status.CONFIRMED,
            executed_amount=Decimal("95.00"),
        )

        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        months = {row["month"]: row for row in summary["months"]}
        self.assertEqual(summary["coverage_mode"], "checkin")
        self.assertEqual(months[2]["executed"], "95.00")
        self.assertEqual(months[2]["coverage_mode"], "checkin")

    def test_income_summary_prefers_ledger_primary_classification_over_checkin(self):
        entry = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("24000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        AnnualIncomeMonthlyCheckin.objects.create(
            user=self.user,
            annual_income_entry=entry,
            fiscal_year=2026,
            month=1,
            status=AnnualIncomeMonthlyCheckin.Status.ADJUSTED,
            executed_amount=Decimal("1800.00"),
        )
        self._post_income_entry(
            amount="2000.00",
            month=1,
            category_key="salary",
            subcategory_key="employee_salary",
        )

        summary = build_income_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        month = next(row for row in summary["months"] if row["month"] == 1)
        self.assertEqual(summary["coverage_mode"], "ledger")
        self.assertEqual(month["executed"], "2000.00")
        self.assertEqual(month["ledger_confirmed"], 1)
        self.assertEqual(month["fallback_confirmed"], 0)

    def test_income_summary_uses_legacy_link_when_new_classification_missing(self):
        entry = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        self._post_income_entry(amount="1000.00", month=3, legacy=entry)

        summary = build_income_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        month = next(row for row in summary["months"] if row["month"] == 3)
        self.assertEqual(summary["has_ledger_data"], False)
        self.assertEqual(summary["coverage_mode"], "checkin")
        self.assertEqual(month["executed"], "1000.00")
        self.assertEqual(month["fallback_confirmed"], 1)

    def test_expense_summary_reports_mixed_coverage_with_ledger_and_fallback(self):
        expense = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Gastos hogar",
            category="consumption_expenses",
            subcategory="living_expenses",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        self._post_expense_entry(
            amount="120.00",
            month=1,
            category_key="consumption_expenses",
            subcategory_key="living_expenses",
        )
        AnnualExpenseMonthlyCheckin.objects.create(
            user=self.user,
            annual_expense_entry=expense,
            fiscal_year=2026,
            month=2,
            status=AnnualExpenseMonthlyCheckin.Status.ADJUSTED,
            executed_amount=Decimal("90.00"),
        )
        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        months = {row["month"]: row for row in summary["months"]}
        self.assertEqual(summary["coverage_mode"], "mixed")
        self.assertEqual(months[1]["coverage_mode"], "ledger")
        self.assertEqual(months[2]["coverage_mode"], "checkin")
        self.assertEqual(summary["months_with_ledger"], 1)
        self.assertEqual(summary["months_with_fallback"], 1)

    def test_expense_summary_includes_unbudgeted_subcategory_within_budgeted_category(self):
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Gastos hogar",
            category="consumption_expenses",
            subcategory="living_expenses",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        self._post_expense_entry(
            amount="120.00",
            month=3,
            category_key="consumption_expenses",
            subcategory_key="living_expenses",
        )
        self._post_expense_entry(
            amount="45.00",
            month=3,
            category_key="consumption_expenses",
            subcategory_key="health_wellbeing",
        )

        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        self.assertEqual(summary["executed_total"], "165.00")
        self.assertEqual(summary["executed_budgeted_total"], "120.00")
        self.assertEqual(summary["executed_unbudgeted_total"], "45.00")

        months = {row["month"]: row for row in summary["months"]}
        self.assertEqual(months[3]["executed_total"], "165.00")
        self.assertEqual(months[3]["executed_budgeted"], "120.00")
        self.assertEqual(months[3]["executed_unbudgeted"], "45.00")

        categories = {
            row["category"]: row for row in summary["expense_execution_breakdown"]["categories"]
        }
        consumption = categories["consumption_expenses"]
        self.assertEqual(consumption["executed_total"], "165.00")
        subcategories = {row["subcategory"]: row for row in consumption["subcategories"]}
        self.assertEqual(subcategories["living_expenses"]["has_budgeted_line"], True)
        self.assertEqual(subcategories["living_expenses"]["executed_unbudgeted_total"], "0.00")
        self.assertEqual(subcategories["health_wellbeing"]["has_budgeted_line"], False)
        self.assertEqual(subcategories["health_wellbeing"]["executed_unbudgeted_total"], "45.00")

    def test_expense_summary_includes_fully_unbudgeted_category_without_double_counting(self):
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Gastos hogar",
            category="consumption_expenses",
            subcategory="living_expenses",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        self._post_expense_entry(
            amount="120.00",
            month=3,
            category_key="consumption_expenses",
            subcategory_key="living_expenses",
        )
        self._post_expense_entry(
            amount="380.00",
            month=3,
            category_key="financial_investments",
            subcategory_key="crypto",
        )

        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        self.assertEqual(summary["executed_total"], "500.00")
        self.assertEqual(summary["executed_budgeted_total"], "120.00")
        self.assertEqual(summary["executed_unbudgeted_total"], "380.00")
        self.assertEqual(summary["coverage_mode"], "ledger")

        categories = {
            row["category"]: row for row in summary["expense_execution_breakdown"]["categories"]
        }
        investments = categories["financial_investments"]
        self.assertEqual(investments["planned_total"], "0.00")
        self.assertEqual(investments["executed_unbudgeted_total"], "380.00")
        self.assertEqual(investments["has_budgeted_lines"], False)
        self.assertEqual(investments["has_unbudgeted_execution"], True)

    def test_expense_summary_handles_user_without_fiscal_year_entries(self):
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Gasto 2025",
            category="consumption_expenses",
            subcategory="living_expenses",
            time_profile=AnnualExpenseEntry.TimeProfile.ONE_OFF,
            target_month=5,
            amount_annual=Decimal("1000.00"),
            fiscal_year=2025,
            currency="EUR",
            is_active=True,
        )
        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        self.assertEqual(summary["planned_total"], "0.00")
        self.assertEqual(summary["coverage_mode"], "none")

    def test_income_and_expense_summaries_with_complete_ledger_coverage(self):
        income = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        expense = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Vivienda",
            category="consumption_expenses",
            subcategory="housing_home",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        self._post_income_entry(
            amount="1000.00",
            month=1,
            category_key=income.category,
            subcategory_key=income.subcategory,
        )
        self._post_expense_entry(
            amount="1000.00",
            month=1,
            category_key=expense.category,
            subcategory_key=expense.subcategory,
        )
        income_summary = build_income_monthly_plan_vs_executed_summary(
            user=self.user, fiscal_year=2026
        )
        expense_summary = build_expense_monthly_plan_vs_executed_summary(
            user=self.user, fiscal_year=2026
        )
        self.assertEqual(income_summary["coverage_mode"], "ledger")
        self.assertEqual(expense_summary["coverage_mode"], "ledger")
