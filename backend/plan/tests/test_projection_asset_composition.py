from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from plan.services_projection import ProjectionInputs, calculate_projection


class ProjectionAssetCompositionTests(SimpleTestCase):
    def assumptions(self) -> dict[str, str]:
        return {
            "inflation_rate": "0.0000",
            "productive_return_rate": "0.0500",
            "non_productive_appreciation_rate": "0.0150",
            "furnishings_depreciation_rate": "0.1200",
            "income_growth_rate": "0.0000",
            "contribution_growth_rate": "0.0000",
            "security_contribution_rate": "0.2500",
            "security_target_expense_years": "2.00",
            "withdrawal_rate": "0.0350",
            "default_liability_rate": "0.0000",
        }

    def inputs(
        self,
        *,
        end_year_offset: int = 0,
        events: tuple[dict[str, str], ...] = (),
    ) -> ProjectionInputs:
        current_year = date.today().year
        return ProjectionInputs(
            plan_id=1,
            target_date=date(current_year + 2, 1, 1),
            target_monthly_income_today_eur=Decimal("0"),
            projection_end_date=date(current_year + end_year_offset, 12, 31),
            preservation_target_eur=None,
            productive_capital=Decimal("10"),
            security_capital=Decimal("20"),
            family_use_capital=Decimal("130"),
            short_term_goal_capital=Decimal("0"),
            unknown_capital=Decimal("0"),
            total_liabilities=Decimal("40"),
            associated_liabilities=Decimal("40"),
            net_worth=Decimal("120"),
            annual_income=Decimal("0"),
            annual_planned_contributions=Decimal("0"),
            annual_pension_income_today=Decimal("0"),
            annual_other_future_income_today=Decimal("0"),
            earliest_pension_start_date=None,
            employment_income_end_date=date(current_year + 2, 1, 1),
            liability_principal=Decimal("40"),
            liability_weighted_rate=Decimal("0"),
            liability_max_term_years=10,
            plan_events=events,
            liquidity_assets=Decimal("20"),
            investment_assets=Decimal("10"),
            real_estate_assets=Decimal("100"),
            furnishings_assets=Decimal("30"),
        )

    def test_asset_categories_reconcile_with_liabilities_and_net_worth(self):
        row = calculate_projection(
            inputs=self.inputs(),
            assumptions=self.assumptions(),
        )["trajectory"][0]

        self.assertEqual(row["total_assets"], "160.00")
        self.assertEqual(row["liabilities"], "40.00")
        self.assertEqual(row["net_worth"], "120.00")

    def test_real_estate_appreciates_while_furnishings_depreciate(self):
        rows = calculate_projection(
            inputs=self.inputs(end_year_offset=1),
            assumptions=self.assumptions(),
        )["trajectory"]
        row = rows[1]

        self.assertEqual(row["investment_assets"], "10.50")
        self.assertEqual(row["real_estate_assets"], "101.50")
        self.assertEqual(row["furnishings_assets"], "26.40")

    def test_housing_decision_moves_the_real_estate_category(self):
        current_year = date.today().year
        event = {
            "start_year": str(current_year),
            "start_month": "11",
            "event_type": "housing",
            "new_asset_value": "50",
            "new_asset_type": "family_use",
            "disposed_asset_value": "100",
            "disposed_asset_type": "family_use",
        }
        row = calculate_projection(
            inputs=self.inputs(events=(event,)),
            assumptions=self.assumptions(),
        )["trajectory"][0]

        self.assertEqual(row["real_estate_assets"], "50.00")
        self.assertEqual(row["furnishings_assets"], "30.00")
