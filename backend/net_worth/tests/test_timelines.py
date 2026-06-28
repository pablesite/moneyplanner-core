from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Asset, Liability
from ..services_timelines import build_net_worth_timeline, parse_timeline_query_params


class NetWorthTimelineServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="nw_timeline_user",
            password="pass1234",
        )

    def test_parse_timeline_query_params_normalizes_empty_filters(self):
        params = parse_timeline_query_params(
            query_params={
                "group_by": "month",
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "asset_category": "",
                "liability_category": "credit_card",
            }
        )

        self.assertEqual(params["start_date"], date(2026, 1, 1))
        self.assertEqual(params["end_date"], date(2026, 3, 31))
        self.assertIsNone(params["asset_category"])
        self.assertEqual(params["liability_category"], "credit_card")

    def test_net_worth_timeline_builds_monthly_rows_for_active_positions(self):
        Asset.objects.create(
            user=self.user,
            name="Banco",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=Decimal("1000.00"),
            currency="EUR",
            start_date=date(2026, 1, 15),
            is_active=True,
        )
        Liability.objects.create(
            user=self.user,
            name="Tarjeta",
            category=Liability.Category.CREDIT_CARD,
            amount=Decimal("200.00"),
            currency="EUR",
            start_date=date(2026, 2, 1),
            is_active=True,
        )

        timeline = build_net_worth_timeline(
            user=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )

        self.assertEqual(timeline["start_date"], "2026-01-01")
        self.assertEqual(timeline["end_date"], "2026-03-31")
        self.assertEqual(
            [
                (row["date"], row["asset_positions"], row["liability_positions"])
                for row in timeline["rows"]
            ],
            [
                ("2026-01-31", 1, 0),
                ("2026-02-28", 1, 1),
                ("2026-03-31", 1, 1),
            ],
        )

    def test_net_worth_timeline_exposes_comparison_points(self):
        Asset.objects.create(
            user=self.user,
            name="Cuenta",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=Decimal("1000.00"),
            currency="EUR",
            start_date=date(2025, 1, 1),
            is_active=True,
        )
        Liability.objects.create(
            user=self.user,
            name="Tarjeta",
            category=Liability.Category.CREDIT_CARD,
            amount=Decimal("200.00"),
            currency="EUR",
            start_date=date(2026, 6, 1),
            is_active=True,
        )

        timeline = build_net_worth_timeline(
            user=self.user,
            start_date=date(2025, 1, 1),
            end_date=date(2026, 6, 28),
        )

        comparisons = timeline["comparisons"]
        self.assertEqual(comparisons["previous_month_close"]["date"], "2026-05-31")
        self.assertEqual(comparisons["previous_month_close"]["net_worth"], "1000.00")
        self.assertEqual(comparisons["same_day_previous_month"]["date"], "2026-05-28")
        self.assertEqual(comparisons["same_day_previous_month"]["net_worth"], "1000.00")
        self.assertEqual(comparisons["previous_year_close"]["date"], "2025-12-31")
        self.assertEqual(comparisons["previous_year_close"]["net_worth"], "1000.00")
        self.assertEqual(comparisons["same_day_previous_year"]["date"], "2025-06-28")
        self.assertEqual(comparisons["same_day_previous_year"]["net_worth"], "1000.00")
        self.assertEqual(timeline["prev_month_same_day"], comparisons["same_day_previous_month"])
