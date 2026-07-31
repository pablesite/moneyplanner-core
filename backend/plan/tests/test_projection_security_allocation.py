from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from plan.services_projection import ProjectionInputs, calculate_projection


class ProjectionSecurityAllocationTests(SimpleTestCase):
    def assumptions(self, **overrides: str) -> dict[str, str]:
        values = {
            "inflation_rate": "0.0000",
            "productive_return_rate": "0.0000",
            "non_productive_appreciation_rate": "0.0000",
            "furnishings_depreciation_rate": "0.1200",
            "income_growth_rate": "0.0000",
            "contribution_growth_rate": "0.0000",
            "security_contribution_rate": "0.2500",
            "security_target_expense_years": "2.00",
            "withdrawal_rate": "0.0350",
            "default_liability_rate": "0.0000",
        }
        values.update(overrides)
        return values

    def inputs(
        self,
        *,
        productive: str = "0",
        security: str = "0",
        free_cash: str = "40000",
        annual_operating_expense: str = "20000",
    ) -> ProjectionInputs:
        current_year = date.today().year
        return ProjectionInputs(
            plan_id=1,
            target_date=date(current_year + 1, 1, 1),
            target_monthly_income_today_eur=Decimal("0"),
            projection_end_date=date(current_year, 12, 31),
            preservation_target_eur=None,
            productive_capital=Decimal(productive),
            security_capital=Decimal(security),
            family_use_capital=Decimal("0"),
            short_term_goal_capital=Decimal("0"),
            unknown_capital=Decimal("0"),
            total_liabilities=Decimal("0"),
            associated_liabilities=Decimal("0"),
            net_worth=Decimal(productive) + Decimal(security),
            annual_income=Decimal(free_cash),
            annual_planned_contributions=Decimal("0"),
            annual_pension_income_today=Decimal("0"),
            annual_other_future_income_today=Decimal("0"),
            earliest_pension_start_date=None,
            employment_income_end_date=date(current_year + 1, 1, 1),
            liability_principal=Decimal("0"),
            liability_weighted_rate=Decimal("0"),
            liability_max_term_years=0,
            annual_operating_expense=Decimal(annual_operating_expense),
            current_year_remaining_income=Decimal(free_cash),
        )

    def current_row(self, inputs: ProjectionInputs, **assumption_overrides: str):
        result = calculate_projection(
            inputs=inputs,
            assumptions=self.assumptions(**assumption_overrides),
        )
        return result["trajectory"][0]

    def test_allocates_quarter_to_security_and_remainder_to_productive(self):
        row = self.current_row(self.inputs())

        self.assertEqual(row["security_capital"], "10000.00")
        self.assertEqual(row["productive_capital"], "30000.00")
        self.assertEqual(row["security_target"], "40000.00")
        self.assertEqual(row["net_worth"], "40000.00")

    def test_security_allocation_is_capped_at_two_year_expense_target(self):
        row = self.current_row(self.inputs(security="39000"))

        self.assertEqual(row["security_capital"], "40000.00")
        self.assertEqual(row["productive_capital"], "39000.00")
        self.assertEqual(row["net_worth"], "79000.00")

    def test_all_free_cash_goes_to_productive_after_security_target(self):
        row = self.current_row(self.inputs(security="40000"))

        self.assertEqual(row["security_capital"], "40000.00")
        self.assertEqual(row["productive_capital"], "40000.00")

    def test_allocation_rate_is_an_explicit_projection_assumption(self):
        row = self.current_row(
            self.inputs(),
            security_contribution_rate="0.4000",
        )

        self.assertEqual(row["security_capital"], "16000.00")
        self.assertEqual(row["productive_capital"], "24000.00")
