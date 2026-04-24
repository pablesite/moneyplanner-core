from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from broker_integrations.models import MarketRateSnapshot
from broker_integrations.services.intraday_fx import IntradayFxService
from core.models import FxRate


class IntradayFxServiceTests(TestCase):
    def setUp(self):
        self.service = IntradayFxService()
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.90"),
            rate_date=datetime(2025, 1, 1, tzinfo=timezone.utc).date(),
        )

    def test_get_rate_at_uses_existing_minute_snapshot(self):
        minute = datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc)
        MarketRateSnapshot.objects.create(
            pair="BTCEUR",
            interval="1m",
            open_time=minute,
            close=Decimal("50000"),
            high=Decimal("50100"),
            low=Decimal("49900"),
            source="binance_klines",
            raw={},
        )
        rate, source = self.service.get_rate_at(timestamp=minute, asset="BTC")
        self.assertEqual(rate, Decimal("50000"))
        self.assertEqual(source, "binance_klines_1m")

    @patch.object(IntradayFxService, "fetch_klines", autospec=True)
    def test_get_rate_at_fetches_when_minute_missing(self, fetch_mock):
        minute = datetime(2025, 1, 1, 10, 16, tzinfo=timezone.utc)
        fetch_mock.return_value = [
            {
                "open_time_ms": int(minute.timestamp() * 1000),
                "close": Decimal("3100"),
                "high": Decimal("3110"),
                "low": Decimal("3090"),
                "raw": [],
            }
        ]
        rate, source = self.service.get_rate_at(timestamp=minute, asset="ETH")
        self.assertEqual(rate, Decimal("3100"))
        self.assertEqual(source, "binance_klines_1m")
        self.assertTrue(
            MarketRateSnapshot.objects.filter(
                pair="ETHEUR", interval="1m", open_time=minute
            ).exists()
        )

    @patch.object(IntradayFxService, "fetch_klines", autospec=True)
    def test_get_rate_at_uses_usdt_chain_when_no_direct_eur_pair(self, fetch_mock):
        minute = datetime(2025, 1, 1, 10, 17, tzinfo=timezone.utc)

        def fake_fetch(_self, *, pair: str, start_ms: int, end_ms: int, interval: str):
            if pair == "SOLEUR":
                return []
            if pair == "SOLUSDT":
                return [
                    {
                        "open_time_ms": int(minute.timestamp() * 1000),
                        "close": Decimal("100"),
                        "high": Decimal("101"),
                        "low": Decimal("99"),
                        "raw": [],
                    }
                ]
            return []

        fetch_mock.side_effect = fake_fetch
        rate, source = self.service.get_rate_at(timestamp=minute, asset="SOL")
        self.assertEqual(rate, Decimal("90.0"))
        self.assertEqual(source, "binance_klines_1m_via_usdt")

    @patch.object(IntradayFxService, "fetch_klines", autospec=True)
    def test_get_rate_at_falls_back_to_daily_when_intraday_unavailable(self, fetch_mock):
        minute = datetime(2025, 1, 1, 10, 18, tzinfo=timezone.utc)
        fetch_mock.return_value = []
        rate, source = self.service.get_rate_at(timestamp=minute, asset="USDC")
        self.assertEqual(rate, Decimal("0.90"))
        self.assertEqual(source, "daily_fallback")
