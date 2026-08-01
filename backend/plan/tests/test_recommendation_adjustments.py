from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from plan.models import FinancialPlan, Finding, Recommendation, Scenario, ScenarioEvent
from plan.services_recommendations import RecommendationService


class RecommendationAdjustmentTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="recommendation_adjustments",
            password="pass1234",
        )
        self.client.force_authenticate(self.user)
        self.plan = FinancialPlan.objects.create(
            user=self.user,
            household_type=FinancialPlan.HouseholdType.SINGLE,
            target_date=date(2040, 1, 1),
            target_monthly_income_today_eur=Decimal("2000.00"),
            projection_end_date=date(2065, 1, 1),
            profile=FinancialPlan.Profile.BALANCED,
        )
        self.finding = Finding.objects.create(
            plan=self.plan,
            code=Finding.Code.RETIREMENT_TARGET_OFF_TRACK,
            severity=Finding.Severity.WARNING,
            period="2026",
        )
        self.recommendation = Recommendation.objects.create(
            finding=self.finding,
            code=Recommendation.Code.INCREASE_CONTRIBUTION,
            action_json={
                "title": "Aumentar aportación planificada",
                "scenario_template": Scenario.TemplateType.GENERIC,
                "scenario_event": {
                    "start_date": "2027-01-01",
                    "monthly_contribution_delta": "100.00",
                    "monthly_contribution_destination": (
                        ScenarioEvent.ContributionDestination.PRODUCTIVE
                    ),
                },
            },
            impact_json={
                "monthly_action": "100.00",
                "available_monthly_margin": "450.00",
                "funding_source": "Del margen futuro.",
            },
        )

    def test_preview_uses_adjusted_amount_and_date_without_side_effects(self):
        response = self.client.get(
            reverse(
                "financial-plan-recommendation-preview",
                kwargs={"pk": self.recommendation.id},
            ),
            {
                "monthly_contribution_delta": "175.50",
                "start_date": "2028-03-01",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["monthly_commitment"], "175.50")
        self.assertEqual(response.data["start_date"], "2028-03-01")
        self.assertEqual(response.data["available_monthly_margin"], "450.00")
        self.assertEqual(Scenario.objects.count(), 0)

    def test_simulate_persists_adjusted_amount_and_date_in_draft(self):
        response = self.client.post(
            reverse(
                "financial-plan-recommendation-simulate",
                kwargs={"pk": self.recommendation.id},
            ),
            {
                "monthly_contribution_delta": "80.00",
                "start_date": "2029-04-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        event = ScenarioEvent.objects.get(scenario_id=response.data["id"])
        self.assertEqual(event.monthly_contribution_delta, Decimal("80.00"))
        self.assertEqual(event.start_date, date(2029, 4, 1))

    def test_preview_marks_an_amount_above_the_margin_as_unaffordable(self):
        response = self.client.get(
            reverse(
                "financial-plan-recommendation-preview",
                kwargs={"pk": self.recommendation.id},
            ),
            {
                "monthly_contribution_delta": "500.00",
                "start_date": "2028-03-01",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_affordable"])

    def test_simulate_rejects_an_amount_above_the_available_margin(self):
        response = self.client.post(
            reverse(
                "financial-plan-recommendation-simulate",
                kwargs={"pk": self.recommendation.id},
            ),
            {
                "monthly_contribution_delta": "500.00",
                "start_date": "2028-03-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("monthly_contribution_delta", response.data["error"]["details"])

    def test_contribution_is_deferred_until_transient_squeeze_recovers(self):
        spec = RecommendationService()._recommendation_spec(
            plan=self.plan,
            finding=self.finding,
            foundations={
                "cash_flow": {
                    "committed_status": "transient",
                    "committed_recovery_year": 2028,
                    "committed_surplus": "-2400.00",
                    "operating_surplus": "12000.00",
                    "temporary_commitments": [
                        {"amount": "9600.00", "end_year": 2027, "end_month": 12}
                    ],
                }
            },
        )

        assert spec is not None
        self.assertEqual(spec["action"]["scenario_event"]["start_date"], "2028-01-01")
        self.assertEqual(spec["action"]["scenario_event"]["monthly_contribution_delta"], "100.00")
        self.assertEqual(spec["impact"]["available_monthly_margin"], "1000.00")
        self.assertIn("no se descuenta del presupuesto actual", spec["impact"]["funding_source"])

    def test_contribution_is_not_recommended_during_structural_deficit(self):
        spec = RecommendationService()._recommendation_spec(
            plan=self.plan,
            finding=self.finding,
            foundations={
                "cash_flow": {
                    "committed_status": "structural",
                    "committed_recovery_year": None,
                    "committed_surplus": "-2400.00",
                    "operating_surplus": "-1200.00",
                    "temporary_commitments": [],
                }
            },
        )

        self.assertIsNone(spec)

    @patch("plan.services_recommendations.scenario_event_changes_projection", return_value=False)
    @patch("plan.services_recommendations.FoundationService.calculate")
    @patch("plan.services_recommendations.FindingService.evaluate")
    def test_refresh_omits_a_contribution_with_no_projected_effect(
        self,
        evaluate_findings,
        calculate_foundations,
        _changes_projection,
    ):
        evaluate_findings.return_value = [self.finding]
        calculate_foundations.return_value = {
            "cash_flow": {
                "committed_status": "healthy",
                "committed_recovery_year": None,
                "committed_surplus": "12000.00",
                "operating_surplus": "12000.00",
                "temporary_commitments": [],
            }
        }

        recommendations = RecommendationService().refresh(plan=self.plan)

        self.assertEqual(recommendations, [])

    def test_adjustment_rejects_zero_amount(self):
        response = self.client.get(
            reverse(
                "financial-plan-recommendation-preview",
                kwargs={"pk": self.recommendation.id},
            ),
            {"monthly_contribution_delta": "0"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
