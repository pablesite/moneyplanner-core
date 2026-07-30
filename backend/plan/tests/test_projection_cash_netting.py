from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from net_worth.models import Asset
from plan.models import FinancialPlan, PlanEvent, Scenario
from plan.services_projection import ProjectionService, get_assumption_set


class ProjectionCashNettingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("cash-netting-user", password="x")
        self.year = date.today().year
        self.plan = FinancialPlan.objects.create(
            user=self.user,
            household_type=FinancialPlan.HouseholdType.SINGLE,
            target_date=date(2040, 1, 1),
            target_monthly_income_today_eur=Decimal("2000.00"),
            projection_end_date=date(2065, 1, 1),
            profile=FinancialPlan.Profile.BALANCED,
        )
        Asset.objects.create(
            user=self.user,
            name="Inversión",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            amount=Decimal("100000.00"),
            currency="EUR",
        )
        Asset.objects.create(
            user=self.user,
            name="Fondo de emergencia",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=Decimal("20000.00"),
            currency="EUR",
        )

    def row(self):
        result = ProjectionService().calculate(
            plan=self.plan, assumption_set=get_assumption_set(name="expected")
        )
        return next(row for row in result["trajectory"] if row["year"] == self.year)

    def test_same_month_decisions_net_cash_before_consuming_security(self):
        PlanEvent.objects.create(
            plan=self.plan,
            name="Compra vivienda",
            event_type=Scenario.TemplateType.HOUSING,
            planned_date=date(self.year - 1, 1, 1),
            status=PlanEvent.Status.PLANNED,
            planned_impact_json={
                "events": [
                    {
                        "start_year": self.year,
                        "start_month": 11,
                        "initial_outflow": "40000.00",
                    }
                ]
            },
        )
        PlanEvent.objects.create(
            plan=self.plan,
            name="Venta vivienda",
            event_type=Scenario.TemplateType.HOUSING,
            planned_date=date(self.year, 1, 1),
            status=PlanEvent.Status.PLANNED,
            planned_impact_json={
                "events": [
                    {
                        "start_year": self.year,
                        "start_month": 11,
                        "proceeds": "60000.00",
                    }
                ]
            },
        )

        row = self.row()

        self.assertEqual(row["productive_capital"], "120000.00")
        self.assertEqual(row["security_capital"], "20000.00")

    def test_one_off_inflows_and_outflows_net_before_consuming_security(self):
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Ingreso puntual",
            category=AnnualIncomeEntry.Category.OTHER_INCOME,
            subcategory="misc",
            time_profile=AnnualIncomeEntry.TimeProfile.ONE_OFF,
            income_type=AnnualIncomeEntry.IncomeType.ONE_OFF,
            cashflow_role=AnnualIncomeEntry.CashflowRole.OTHER,
            amount_annual=Decimal("8000.00"),
            fiscal_year=self.year,
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Gasto puntual",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="misc",
            time_profile=AnnualExpenseEntry.TimeProfile.ONE_OFF,
            expense_type=AnnualExpenseEntry.ExpenseType.ONE_OFF,
            cashflow_role=AnnualExpenseEntry.CashflowRole.OTHER,
            amount_annual=Decimal("3000.00"),
            fiscal_year=self.year,
        )

        row = self.row()

        self.assertEqual(row["productive_capital"], "105000.00")
        self.assertEqual(row["security_capital"], "20000.00")
