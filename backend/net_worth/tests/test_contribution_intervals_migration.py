from datetime import date
from importlib import import_module
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Asset, InvestmentContributionInterval


class ContributionIntervalsMigrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="migration_user",
            password="pass1234",
        )

    def test_migrate_legacy_intervals_creates_one_interval_per_legacy_asset(self):
        periodic = Asset.objects.create(
            user=self.user,
            name="Legacy periodic",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            initial_purchase_value=Decimal("1000.00"),
            investment_contribution_mode=Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION,
            monthly_contribution_amount=Decimal("300.00"),
            investment_contribution_frequency=Asset.InvestmentContributionFrequency.WEEKLY,
            investment_contribution_currency="USD",
            start_date=date(2026, 1, 15),
            expected_end_date=date(2026, 12, 15),
            is_active=True,
        )
        Asset.objects.create(
            user=self.user,
            name="Legacy non-periodic",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            initial_purchase_value=Decimal("1000.00"),
            investment_contribution_mode=Asset.InvestmentContributionMode.ONE_TIME,
            monthly_contribution_amount=Decimal("300.00"),
            start_date=date(2026, 1, 15),
            is_active=True,
        )

        module = import_module("net_worth.migrations.0039_migrate_legacy_contribution_intervals")

        class _Apps:
            @staticmethod
            def get_model(app_label, model_name):
                if (app_label, model_name) == ("net_worth", "Asset"):
                    return Asset
                if (app_label, model_name) == ("net_worth", "InvestmentContributionInterval"):
                    return InvestmentContributionInterval
                raise LookupError(f"Unexpected model: {app_label}.{model_name}")

        module.migrate_legacy_intervals(_Apps(), None)

        rows = list(
            InvestmentContributionInterval.objects.filter(asset=periodic).order_by("start_date")
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].start_date.isoformat(), "2026-01-15")
        self.assertEqual(rows[0].end_date.isoformat(), "2026-12-15")
        self.assertEqual(rows[0].amount, Decimal("300.00"))
        self.assertEqual(rows[0].frequency, Asset.InvestmentContributionFrequency.WEEKLY)
        self.assertEqual(rows[0].currency, "USD")
