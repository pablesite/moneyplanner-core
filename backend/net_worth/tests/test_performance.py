from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import UserSettings
from accounting.models import LedgerAccount
from core.models import InflationIndex
from net_worth.models import (
    Asset,
    AssetValuation,
    InvestmentAssetEvent,
    InvestmentContributionInterval,
    Liability,
    LiabilityEvent,
    LiabilityValuation,
    LiquidityAssetEvent,
    LiquidityMonthlyCheckin,
)
from net_worth.services_summaries import build_net_worth_summary
from net_worth.services_timelines import (
    build_asset_timeline,
    build_liability_timeline,
    build_net_worth_timeline,
)


class NetWorthSummaryPerformanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="nw_perf_user",
            password="pass1234",
        )
        UserSettings.objects.update_or_create(
            user=self.user,
            defaults={"base_currency": "EUR", "inflation_region": "ES"},
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("net_worth.services.timezone.localdate", return_value=date(2026, 5, 15))
    def test_summary_uses_position_cache_with_high_position_volume(self, _date_mock):
        cash_assets = [
            Asset.objects.create(
                user=self.user,
                name=f"Cuenta {idx}",
                category=Asset.Category.CASH,
                subcategory=Asset.Subcategory.BANK_ACCOUNT,
                currency="EUR",
                amount=Decimal("1000.00"),
                start_date=date(2026, 1, 1),
                is_active=True,
            )
            for idx in range(20)
        ]
        investment_assets = [
            Asset.objects.create(
                user=self.user,
                name=f"Fondo {idx}",
                category=Asset.Category.INVESTMENTS,
                subcategory=Asset.Subcategory.FUNDS,
                currency="EUR",
                amount=Decimal("2000.00"),
                start_date=date(2026, 1, 1),
                investment_contribution_mode=Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION,
                is_active=True,
            )
            for idx in range(20)
        ]
        liabilities = [
            Liability.objects.create(
                user=self.user,
                name=f"Prestamo {idx}",
                category=Liability.Category.OTHER,
                currency="EUR",
                amount=Decimal("500.00"),
                start_date=date(2026, 1, 1),
                is_active=True,
            )
            for idx in range(10)
        ]

        AssetValuation.objects.bulk_create(
            [
                AssetValuation(
                    user=self.user,
                    asset=asset,
                    valuation_date=date(2026, 4, 30),
                    value=Decimal("1100.00"),
                )
                for asset in cash_assets
            ]
            + [
                AssetValuation(
                    user=self.user,
                    asset=asset,
                    valuation_date=date(2026, 4, 30),
                    value=Decimal("2200.00"),
                )
                for asset in investment_assets
            ]
        )
        LiquidityMonthlyCheckin.objects.bulk_create(
            [
                LiquidityMonthlyCheckin(
                    user=self.user,
                    asset=asset,
                    fiscal_year=2026,
                    month=4,
                    closing_balance_real=Decimal("1050.00"),
                )
                for asset in cash_assets
            ]
        )
        LiquidityAssetEvent.objects.bulk_create(
            [
                LiquidityAssetEvent(
                    user=self.user,
                    asset=asset,
                    event_date=date(2026, 5, 10),
                    event_type=LiquidityAssetEvent.EventType.INTEREST,
                    amount=Decimal("5.00"),
                )
                for asset in cash_assets
            ]
        )
        InvestmentAssetEvent.objects.bulk_create(
            [
                InvestmentAssetEvent(
                    user=self.user,
                    asset=asset,
                    event_date=date(2026, 5, 10),
                    event_type=InvestmentAssetEvent.EventType.CONTRIBUTION,
                    amount=Decimal("25.00"),
                )
                for asset in investment_assets
            ]
        )
        InvestmentContributionInterval.objects.bulk_create(
            [
                InvestmentContributionInterval(
                    asset=asset,
                    start_date=date(2026, 5, 1),
                    amount=Decimal("10.00"),
                    frequency=Asset.InvestmentContributionFrequency.MONTHLY,
                    currency="EUR",
                )
                for asset in investment_assets
            ]
        )
        LiabilityValuation.objects.bulk_create(
            [
                LiabilityValuation(
                    user=self.user,
                    liability=liability,
                    valuation_date=date(2026, 4, 30),
                    value=Decimal("450.00"),
                )
                for liability in liabilities
            ]
        )
        LiabilityEvent.objects.bulk_create(
            [
                LiabilityEvent(
                    user=self.user,
                    liability=liability,
                    event_date=date(2026, 5, 5),
                    event_type=LiabilityEvent.EventType.PAYMENT,
                    amount=Decimal("20.00"),
                )
                for liability in liabilities
            ]
        )

        with CaptureQueriesContext(connection) as captured_queries:
            summary = build_net_worth_summary(user=self.user)

        self.assertLessEqual(len(captured_queries), 14)
        self.assertEqual(summary["total_assets"], Decimal("66800.00"))
        self.assertEqual(summary["total_liabilities"], Decimal("4300.00"))
        self.assertEqual(summary["net_worth"], Decimal("62500.00"))

    def test_asset_timeline_uses_position_cache_across_many_months(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Fondo largo plazo",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            start_date=date(2024, 1, 1),
            investment_contribution_mode=Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION,
            is_active=True,
        )
        AssetValuation.objects.create(
            user=self.user,
            asset=asset,
            valuation_date=date(2024, 12, 31),
            value=Decimal("1500.00"),
        )
        InvestmentAssetEvent.objects.bulk_create(
            [
                InvestmentAssetEvent(
                    user=self.user,
                    asset=asset,
                    event_date=date(2025, month, 15),
                    event_type=InvestmentAssetEvent.EventType.CONTRIBUTION,
                    amount=Decimal("20.00"),
                )
                for month in range(1, 13)
            ]
        )
        InvestmentContributionInterval.objects.create(
            asset=asset,
            start_date=date(2025, 1, 1),
            amount=Decimal("10.00"),
            frequency=Asset.InvestmentContributionFrequency.MONTHLY,
            currency="EUR",
        )

        with CaptureQueriesContext(connection) as captured_queries:
            timeline = build_asset_timeline(asset=asset, end_date=date(2026, 12, 31))

        self.assertLessEqual(len(captured_queries), 10)
        self.assertEqual(len(timeline["rows"]), 36)
        self.assertEqual(timeline["rows"][-1]["value"], "1980.00")

    def test_liability_timeline_uses_position_cache_across_many_months(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Tarjeta larga",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            amount=Decimal("1000.00"),
            start_date=date(2024, 1, 1),
            is_active=True,
        )
        LiabilityValuation.objects.create(
            user=self.user,
            liability=liability,
            valuation_date=date(2024, 12, 31),
            value=Decimal("800.00"),
        )
        LiabilityEvent.objects.bulk_create(
            [
                LiabilityEvent(
                    user=self.user,
                    liability=liability,
                    event_date=date(2025, month, 10),
                    event_type=LiabilityEvent.EventType.PAYMENT,
                    amount=Decimal("10.00"),
                )
                for month in range(1, 13)
            ]
        )

        with CaptureQueriesContext(connection) as captured_queries:
            timeline = build_liability_timeline(
                liability=liability,
                end_date=date(2026, 12, 31),
            )

        self.assertLessEqual(len(captured_queries), 7)
        self.assertEqual(len(timeline["rows"]), 36)
        self.assertEqual(timeline["rows"][-1]["value"], "680.00")

    def test_net_worth_timeline_caches_accounting_accounts_and_inflation_indexes(self):
        InflationIndex.objects.bulk_create(
            [
                InflationIndex(
                    region=InflationIndex.Region.ES,
                    period=date(2025, 1, 1),
                    index=Decimal("100.00"),
                ),
                InflationIndex(
                    region=InflationIndex.Region.ES,
                    period=date(2026, 12, 1),
                    index=Decimal("104.00"),
                ),
            ]
        )
        assets = []
        for idx in range(15):
            asset = Asset.objects.create(
                user=self.user,
                name=f"Mueble contable {idx}",
                category=Asset.Category.FURNISHINGS,
                subcategory=Asset.Subcategory.HOME_FURNISHINGS,
                tracking_mode=Asset.TrackingMode.ACCOUNTING,
                currency="EUR",
                amount=Decimal("1200.00"),
                start_date=date(2025, 1, 1),
                amortization_method=Asset.AmortizationMethod.STRAIGHT_LINE,
                amortization_term_years=10,
                is_active=True,
            )
            account = LedgerAccount.objects.create(
                user=self.user,
                name=f"Cuenta mueble {idx}",
                account_type=LedgerAccount.AccountType.ASSET,
                currency="EUR",
                asset=asset,
            )
            asset.accounting_account_id = account.id
            asset.save(update_fields=["accounting_account_id"])
            assets.append(asset)

        with CaptureQueriesContext(connection) as captured_queries:
            timeline = build_net_worth_timeline(
                user=self.user,
                start_date=date(2025, 1, 1),
                end_date=date(2026, 12, 31),
            )

        self.assertLessEqual(len(captured_queries), 12)
        self.assertEqual(len(timeline["rows"]), 24)
        self.assertEqual(timeline["rows"][-1]["asset_positions"], len(assets))

    def test_asset_list_uses_cached_accounting_state(self):
        for idx in range(20):
            asset = Asset.objects.create(
                user=self.user,
                name=f"Cuenta contable {idx}",
                category=Asset.Category.CASH,
                subcategory=Asset.Subcategory.BANK_ACCOUNT,
                tracking_mode=Asset.TrackingMode.ACCOUNTING,
                currency="EUR",
                amount=Decimal("1000.00"),
                start_date=date(2026, 1, 1),
                is_active=True,
            )
            account = LedgerAccount.objects.create(
                user=self.user,
                name=f"Ledger cuenta {idx}",
                account_type=LedgerAccount.AccountType.ASSET,
                currency="EUR",
                asset=asset,
            )
            asset.accounting_account_id = account.id
            asset.save(update_fields=["accounting_account_id"])

        with CaptureQueriesContext(connection) as captured_queries:
            response = self.client.get("/api/net-worth/assets/")

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(captured_queries), 14)
        self.assertEqual(len(response.data), 20)
        self.assertEqual(
            {row["accounting_integration_state"] for row in response.data},
            {"linked"},
        )

    def test_liability_list_prefetches_financed_asset_and_cached_accounting_state(self):
        financed_asset = Asset.objects.create(
            user=self.user,
            name="Vivienda",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            amount=Decimal("200000.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        for idx in range(10):
            liability = Liability.objects.create(
                user=self.user,
                name=f"Hipoteca {idx}",
                category=Liability.Category.MORTGAGE,
                tracking_mode=Liability.TrackingMode.ACCOUNTING,
                currency="EUR",
                amount=Decimal("100000.00"),
                start_date=date(2026, 1, 1),
                financed_asset=financed_asset,
                is_active=True,
            )
            account = LedgerAccount.objects.create(
                user=self.user,
                name=f"Ledger hipoteca {idx}",
                account_type=LedgerAccount.AccountType.LIABILITY,
                currency="EUR",
                liability=liability,
            )
            liability.accounting_account_id = account.id
            liability.save(update_fields=["accounting_account_id"])

        with CaptureQueriesContext(connection) as captured_queries:
            response = self.client.get("/api/net-worth/liabilities/")

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(captured_queries), 10)
        self.assertEqual(len(response.data), 10)
        self.assertEqual(
            {row["accounting_integration_state"] for row in response.data},
            {"linked"},
        )
        self.assertEqual(
            {row["financed_asset_detail"]["id"] for row in response.data},
            {financed_asset.id},
        )
