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
from core.models import FxRate
from net_worth.models import Asset, Liability
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
        )

    def _post_expense_entry(
        self,
        *,
        amount: str,
        month: int,
        category_key: str = "",
        subcategory_key: str = "",
        asset: Asset | None = None,
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
            asset=asset,
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
        self.assertTrue(expense_entry_applies_to_fiscal_year(entry=term, fiscal_year=2026))
        self.assertFalse(expense_entry_applies_to_fiscal_year(entry=term, fiscal_year=2028))
        self.assertTrue(expense_entry_applies_to_fiscal_year(entry=term, fiscal_year=2027))

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
        self.assertTrue(income_entry_applies_to_fiscal_year(entry=term, fiscal_year=2026))
        self.assertFalse(income_entry_applies_to_fiscal_year(entry=term, fiscal_year=2028))
        self.assertTrue(income_entry_applies_to_fiscal_year(entry=term, fiscal_year=2027))

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
        self.assertEqual(distribution[1], Decimal("200.00"))
        self.assertEqual(sum(distribution.values()), Decimal("1200.00"))

    def test_planned_expense_distribution_uses_term_end_month_when_end_year_missing(self):
        term = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Compromiso temporal sin fin anual",
            category="real_estate_assets",
            subcategory="mortgage_principal",
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            term_end_month=10,
            term_end_year=None,
            amount_annual=Decimal("2810.39"),
            fiscal_year=2026,
            currency="EUR",
        )

        distribution = planned_expense_monthly_distribution(entry=term, fiscal_year=2026)
        self.assertEqual(len(distribution), 10)
        self.assertEqual(distribution[1], Decimal("281.04"))
        self.assertEqual(distribution[10], Decimal("281.03"))
        self.assertEqual(sum(distribution.values()), Decimal("2810.39"))

    def test_planned_expense_distribution_scales_monthly_term_rows_to_active_months(self):
        term = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Cuota mensual temporal",
            category="real_estate_assets",
            subcategory="mortgage_principal",
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            term_end_month=9,
            term_end_year=2026,
            amount_input_period=AnnualExpenseEntry.AmountInputPeriod.MONTHLY,
            amount_annual=Decimal("16488.00"),
            fiscal_year=2026,
            currency="EUR",
        )

        distribution = planned_expense_monthly_distribution(entry=term, fiscal_year=2026)
        self.assertEqual(len(distribution), 9)
        self.assertEqual(distribution[1], Decimal("1374.00"))
        self.assertEqual(distribution[9], Decimal("1374.00"))
        self.assertEqual(sum(distribution.values()), Decimal("12366.00"))

    def test_planned_expense_distribution_uses_term_start_month(self):
        term = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Cuota coche desde marzo",
            category="consumption_expenses",
            subcategory="personal_loan_repayment",
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            term_start_month=3,
            term_end_month=6,
            term_end_year=2026,
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
        )

        distribution = planned_expense_monthly_distribution(entry=term, fiscal_year=2026)
        self.assertEqual(set(distribution), {3, 4, 5, 6})
        self.assertEqual(distribution[3], Decimal("300.00"))
        self.assertEqual(sum(distribution.values()), Decimal("1200.00"))

    def test_planned_expense_distribution_uses_expense_type_for_legacy_one_off_rows(self):
        legacy_one_off = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Cancelacion anticipada",
            category="real_estate_assets",
            subcategory="mortgage_principal",
            expense_type=AnnualExpenseEntry.ExpenseType.ONE_OFF,
            time_profile=AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT,
            target_month=11,
            amount_annual=Decimal("15453.77"),
            fiscal_year=2026,
            currency="EUR",
        )
        self.assertEqual(
            planned_expense_monthly_distribution(entry=legacy_one_off, fiscal_year=2026),
            {11: Decimal("15453.77")},
        )

    def test_expense_summary_ignores_historical_rows_from_other_fiscal_years(self):
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Compromiso antiguo",
            category="real_estate_assets",
            subcategory="mortgage_principal",
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            amount_annual=Decimal("964.46"),
            fiscal_year=2025,
            term_end_year=2025,
            term_end_month=11,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Compromiso actual",
            category="real_estate_assets",
            subcategory="mortgage_principal",
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            amount_annual=Decimal("2810.39"),
            fiscal_year=2026,
            term_end_year=2026,
            term_end_month=11,
            currency="EUR",
        )

        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        categories = {
            row["category"]: row for row in summary["expense_execution_breakdown"]["categories"]
        }
        subcategories = {
            row["subcategory"]: row for row in categories["real_estate_assets"]["subcategories"]
        }
        mortgage = subcategories["mortgage_principal"]
        self.assertEqual(mortgage["planned_total"], "2810.39")
        self.assertEqual(mortgage["months"][0]["planned"], "255.49")
        self.assertEqual(mortgage["months"][1]["planned"], "255.49")
        self.assertEqual(mortgage["months"][2]["planned"], "255.49")

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

        recurrent_single_month = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Paga extra",
            category="salary",
            subcategory="bonus_commission",
            time_profile=AnnualIncomeEntry.TimeProfile.STRUCTURAL_RECURRENT,
            target_month=7,
            amount_annual=Decimal("3000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        self.assertEqual(
            planned_income_monthly_distribution(entry=recurrent_single_month, fiscal_year=2026),
            {7: Decimal("3000.00")},
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

    def test_planned_income_distribution_uses_term_start_month(self):
        term = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Contrato desde marzo",
            category="business",
            subcategory="self_employed_services",
            time_profile=AnnualIncomeEntry.TimeProfile.TERM_RECURRENT,
            term_start_month=3,
            term_end_month=4,
            term_end_year=2026,
            amount_annual=Decimal("2000.00"),
            fiscal_year=2026,
            currency="EUR",
        )

        distribution = planned_income_monthly_distribution(entry=term, fiscal_year=2026)
        self.assertEqual(distribution, {3: Decimal("1000.00"), 4: Decimal("1000.00")})

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

    def test_income_summary_ignores_unclassified_ledger_entry(self):
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        self._post_income_entry(amount="1000.00", month=3)

        summary = build_income_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        month = next(row for row in summary["months"] if row["month"] == 3)
        self.assertEqual(summary["has_ledger_data"], False)
        self.assertEqual(summary["coverage_mode"], "none")
        self.assertEqual(month["executed"], "0.00")
        self.assertEqual(month["pending"], "1000.00")
        self.assertEqual(month["fallback_confirmed"], 0)

    def test_income_summary_includes_unbudgeted_subcategory_within_budgeted_category(self):
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        self._post_income_entry(
            amount="120.00",
            month=3,
            category_key="salary",
            subcategory_key="employee_salary",
        )
        self._post_income_entry(
            amount="45.00",
            month=3,
            category_key="salary",
            subcategory_key="social_benefits",
        )

        summary = build_income_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        self.assertEqual(summary["executed_budgeted_total"], "120.00")
        self.assertEqual(summary["executed_unbudgeted_total"], "45.00")
        month = next(row for row in summary["months"] if row["month"] == 3)
        self.assertEqual(month["executed_budgeted"], "120.00")
        self.assertEqual(month["executed_unbudgeted"], "45.00")
        self.assertEqual(month["executed_total"], "165.00")

        categories = {
            row["category"]: row for row in summary["income_execution_breakdown"]["categories"]
        }
        salary = categories["salary"]
        subcategories = {row["subcategory"]: row for row in salary["subcategories"]}
        self.assertEqual(subcategories["employee_salary"]["has_budgeted_line"], True)
        self.assertEqual(subcategories["social_benefits"]["has_budgeted_line"], False)
        self.assertEqual(subcategories["social_benefits"]["executed_unbudgeted_total"], "45.00")

    def test_income_summary_groups_multiple_budget_lines_in_same_subcategory_slot(self):
        for name in ("Nomina", "Complemento"):
            AnnualIncomeEntry.objects.create(
                user=self.user,
                name=name,
                category="salary",
                subcategory="employee_salary",
                amount_annual=Decimal("1200.00"),
                fiscal_year=2026,
                currency="EUR",
                is_active=True,
            )
        self._post_income_entry(
            amount="1800.00",
            month=1,
            category_key="salary",
            subcategory_key="employee_salary",
        )

        summary = build_income_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        month = next(row for row in summary["months"] if row["month"] == 1)
        self.assertEqual(summary["planned_total"], "2400.00")
        self.assertEqual(summary["executed_total"], "1800.00")
        self.assertEqual(summary["executed_budgeted_total"], "1800.00")
        self.assertEqual(summary["executed_unbudgeted_total"], "0.00")
        self.assertEqual(month["planned"], "200.00")
        self.assertEqual(month["executed_total"], "1800.00")
        self.assertEqual(month["ledger_confirmed"], 2)
        self.assertEqual(month["checkins_expected"], 2)

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

    def test_expense_summary_ignores_estimated_checkin_when_ledger_exists(self):
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
        AnnualExpenseMonthlyCheckin.objects.create(
            user=self.user,
            annual_expense_entry=expense,
            fiscal_year=2026,
            month=1,
            status=AnnualExpenseMonthlyCheckin.Status.ESTIMATED,
            executed_amount=Decimal("999.00"),
        )
        self._post_expense_entry(
            amount="110.00",
            month=1,
            category_key="consumption_expenses",
            subcategory_key="living_expenses",
        )

        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        month = next(row for row in summary["months"] if row["month"] == 1)
        self.assertEqual(summary["coverage_mode"], "ledger")
        self.assertEqual(month["executed_total"], "110.00")
        self.assertEqual(month["ledger_confirmed"], 1)
        self.assertEqual(month["fallback_confirmed"], 0)

    def test_expense_summary_manual_checkin_is_fallback_when_slot_has_no_ledger(self):
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
        AnnualExpenseMonthlyCheckin.objects.create(
            user=self.user,
            annual_expense_entry=expense,
            fiscal_year=2026,
            month=1,
            status=AnnualExpenseMonthlyCheckin.Status.ADJUSTED,
            executed_amount=Decimal("90.00"),
        )

        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        month = next(row for row in summary["months"] if row["month"] == 1)
        self.assertEqual(summary["coverage_mode"], "checkin")
        self.assertEqual(month["executed_total"], "90.00")
        self.assertEqual(month["ledger_confirmed"], 0)
        self.assertEqual(month["fallback_confirmed"], 1)

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

    def test_expense_summary_groups_mortgage_interest_into_mortgage_principal_budget_line(self):
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Hipoteca",
            category="real_estate_assets",
            subcategory="mortgage_principal",
            amount_annual=Decimal("3000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca vivienda",
            category=Liability.Category.MORTGAGE,
            currency="EUR",
            amount=Decimal("120000.00"),
            is_active=True,
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo hipoteca",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 15),
            value_date=date(2026, 3, 15),
            description="Cuota hipoteca marzo",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("200.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="real_estate_assets",
            subcategory_key="mortgage_principal",
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("50.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="financial_commitments",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("250.00"),
            currency="EUR",
        )

        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)

        self.assertEqual(summary["executed_total"], "250.00")
        self.assertEqual(summary["executed_budgeted_total"], "250.00")
        self.assertEqual(summary["executed_unbudgeted_total"], "0.00")

        categories = {
            row["category"]: row for row in summary["expense_execution_breakdown"]["categories"]
        }
        mortgage = categories["real_estate_assets"]
        subcategories = {row["subcategory"]: row for row in mortgage["subcategories"]}
        self.assertEqual(subcategories["mortgage_principal"]["executed_total"], "250.00")
        self.assertEqual(subcategories["mortgage_principal"]["executed_unbudgeted_total"], "0.00")

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

    def test_expense_summary_normalizes_legacy_investment_subcategory_aliases(self):
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="ETF budget legacy",
            category="financial_investments",
            subcategory="index_funds_etf",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        self._post_expense_entry(
            amount="100.00",
            month=1,
            category_key="financial_investments",
            subcategory_key="etf_indexed",
        )

        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        self.assertEqual(summary["executed_budgeted_total"], "100.00")
        self.assertEqual(summary["executed_unbudgeted_total"], "0.00")

        categories = {
            row["category"]: row for row in summary["expense_execution_breakdown"]["categories"]
        }
        investments = categories["financial_investments"]
        subcategories = {row["subcategory"]: row for row in investments["subcategories"]}
        self.assertIn("etf_indexed", subcategories)
        self.assertNotIn("index_funds_etf", subcategories)
        self.assertEqual(subcategories["etf_indexed"]["planned_total"], "1200.00")
        self.assertEqual(subcategories["etf_indexed"]["executed_budgeted_total"], "100.00")
        self.assertEqual(subcategories["etf_indexed"]["executed_unbudgeted_total"], "0.00")

    def test_expense_summary_accepts_deposit_fixed_income_subcategory(self):
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Depositos",
            category="financial_investments",
            subcategory="deposits_fixed_income",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        self._post_expense_entry(
            amount="100.00",
            month=1,
            category_key="financial_investments",
            subcategory_key="deposits_fixed_income",
        )

        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        self.assertEqual(summary["executed_budgeted_total"], "100.00")
        self.assertEqual(summary["executed_unbudgeted_total"], "0.00")

        categories = {
            row["category"]: row for row in summary["expense_execution_breakdown"]["categories"]
        }
        investments = categories["financial_investments"]
        subcategories = {row["subcategory"]: row for row in investments["subcategories"]}
        self.assertIn("deposits_fixed_income", subcategories)
        self.assertEqual(subcategories["deposits_fixed_income"]["planned_total"], "1200.00")
        self.assertEqual(
            subcategories["deposits_fixed_income"]["executed_budgeted_total"], "100.00"
        )

    def test_expense_summary_reclassifies_deposit_asset_history_from_other_investments(self):
        deposit_asset = Asset.objects.create(
            user=self.user,
            name="Deposito 1M",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.SHORT_TERM_DEPOSIT,
            currency="EUR",
            amount=Decimal("1000.00"),
            deposit_term_months=1,
            is_active=True,
        )
        self._post_expense_entry(
            amount="250.00",
            month=1,
            category_key="financial_investments",
            subcategory_key="other_financial_investments",
            asset=deposit_asset,
        )

        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        categories = {
            row["category"]: row for row in summary["expense_execution_breakdown"]["categories"]
        }
        investments = categories["financial_investments"]
        subcategories = {row["subcategory"]: row for row in investments["subcategories"]}
        self.assertEqual(
            subcategories["deposits_fixed_income"]["executed_unbudgeted_total"], "250.00"
        )
        self.assertNotIn("other_financial_investments", subcategories)

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

    def test_expense_summary_converts_foreign_currency_investment_to_base_currency(self):
        """Investment purchased in USD shows EUR-converted executed amount in budget."""
        usd_account = LedgerAccount.objects.create(
            user=self.user,
            name="Spot Binance / USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )
        btc_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            currency="BTC",
            amount=Decimal("0"),
            is_active=True,
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cripto - Bitcoin",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=btc_asset,
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Criptomonedas",
            category="financial_investments",
            subcategory="crypto",
            amount_annual=Decimal("600.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate_date=date(2026, 4, 1),
            rate=Decimal("0.95"),
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 21),
            value_date=date(2026, 4, 21),
            description="Inversión en BTC",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=btc_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("0.00032784"),
            currency="BTC",
            asset=btc_asset,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=usd_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("25.00"),
            currency="USD",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="financial_investments",
            subcategory_key="crypto",
        )
        summary = build_expense_monthly_plan_vs_executed_summary(user=self.user, fiscal_year=2026)
        breakdown = summary["expense_execution_breakdown"]
        fi_cat = next(
            c for c in breakdown["categories"] if c["category"] == "financial_investments"
        )
        crypto_sub = next(s for s in fi_cat["subcategories"] if s["subcategory"] == "crypto")
        april = next(m for m in crypto_sub["months"] if m["month"] == 4)
        self.assertEqual(Decimal(april["executed_budgeted"]), Decimal("23.75"))  # 25 USD * 0.95
