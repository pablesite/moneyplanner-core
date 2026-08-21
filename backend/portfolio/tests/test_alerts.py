from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from portfolio.alerts import build_portfolio_alerts
from portfolio.models import ContributionBasket, Instrument, PositionExposure

from .test_allocation import AllocationFixture

TODAY = date(2024, 12, 31)


class PortfolioAlertTests(AllocationFixture, TestCase):
    def codes(self, result: dict) -> set[str]:
        return {row["code"] for row in result["alerts"]}

    def test_missing_policy_and_declared_exposure_are_actionable(self):
        position = self.create_position("Fondo global", Decimal("1000"))
        PositionExposure.objects.create(
            position=position,
            dimension=PositionExposure.Dimension.GEOGRAPHY,
            bucket="north_america",
            percent=Decimal("50"),
            observed_on=TODAY,
        )

        result = build_portfolio_alerts(portfolio=self.portfolio, on_date=TODAY)
        alerts = {row["code"]: row for row in result["alerts"]}

        self.assertIn(f"strategy_missing:{self.mine.id}", alerts)
        self.assertEqual(
            alerts[f"strategy_missing:{self.mine.id}"]["action"],
            {"kind": "open_allocation", "ownership_id": self.mine.id},
        )
        self.assertIn("exposure_coverage:geography", alerts)
        self.assertEqual(alerts["exposure_coverage:geography"]["action"]["kind"], "open_exposure")

    def test_out_of_band_class_and_pending_basket_are_reported_once(self):
        self.create_position("Fondo global", Decimal("900"))
        self.create_position("Bitcoin", Decimal("100"), asset_class=Instrument.AssetClass.CRYPTO)
        self.strategy(
            self.mine,
            date(2024, 1, 1),
            {"equity": ("50", "45", "55"), "crypto": ("50", "45", "55")},
        )
        strategy = self.portfolio.allocation_strategies.get(ownership=self.mine)
        ContributionBasket.objects.create(
            portfolio=self.portfolio,
            ownership=self.mine,
            strategy=strategy,
            booking_date=TODAY,
            amount=Decimal("100"),
        )

        result = build_portfolio_alerts(portfolio=self.portfolio, on_date=TODAY)
        alerts = {row["code"]: row for row in result["alerts"]}

        self.assertIn(f"allocation_band:{self.mine.id}:equity", alerts)
        self.assertIn(f"allocation_band:{self.mine.id}:crypto", alerts)
        self.assertEqual(alerts["pending_baskets"]["action"], {"kind": "open_baskets"})


class PortfolioAlertsApiTests(AllocationFixture, APITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.user)

    def test_alerts_are_private_and_have_a_stable_summary(self):
        self.create_position("Fondo global", Decimal("1000"))

        response = self.client.get("/api/portfolio/alerts/?on_date=2024-12-31")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["on_date"], "2024-12-31")
        self.assertEqual(sum(response.data["summary"].values()), len(response.data["alerts"]))
