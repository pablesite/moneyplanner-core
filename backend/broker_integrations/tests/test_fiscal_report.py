from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from broker_integrations.models import (
    BotNetResult,
    BrokerCredential,
    BrokerTrade,
    FuturesPosition,
    IncomeEvent,
)
from broker_integrations.services.eur_converter import EurConverter
from broker_integrations.services.fifo_calculator import calculate_fifo_for_asset
from broker_integrations.services.fiscal_report import generate_fiscal_report
from core.models import FxRate
from memberships.models import FamilyMember, Ownership


class FiscalReportServicesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="fiscal_user", password="pass1234")
        member = FamilyMember.objects.create(
            user=self.user,
            name="Primary",
            role=FamilyMember.Role.ADULT,
        )
        self.ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=member,
        )
        self.binance_credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="binance-main",
            api_key="binance-key",
            api_secret_encrypted=b"secret",
        )
        self.pionex_credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.PIONEX,
            label="pionex-main",
            api_key="pionex-key",
            api_secret_encrypted=b"secret",
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.90"),
            rate_date=datetime(2025, 1, 1, tzinfo=timezone.utc).date(),
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.92"),
            rate_date=datetime(2025, 2, 1, tzinfo=timezone.utc).date(),
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.91"),
            rate_date=datetime(2025, 1, 15, tzinfo=timezone.utc).date(),
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.905"),
            rate_date=datetime(2025, 1, 12, tzinfo=timezone.utc).date(),
        )

    def test_fifo_cross_exchange_uses_binance_buy_for_pionex_sell(self):
        BrokerTrade.objects.create(
            credential=self.binance_credential,
            source=BrokerTrade.Source.BINANCE_API,
            trade_id="buy-1",
            symbol="BTCUSDC",
            base_asset="BTC",
            quote_asset="USDC",
            side=BrokerTrade.Side.BUY,
            price=Decimal("50000"),
            quantity=Decimal("0.01"),
            fee=Decimal("0"),
            fee_asset="",
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            raw={},
        )
        BrokerTrade.objects.create(
            credential=self.pionex_credential,
            source=BrokerTrade.Source.PIONEX_API,
            trade_id="sell-1",
            symbol="BTCUSDC",
            base_asset="BTC",
            quote_asset="USDC",
            side=BrokerTrade.Side.SELL,
            price=Decimal("60000"),
            quantity=Decimal("0.005"),
            fee=Decimal("0"),
            fee_asset="",
            timestamp=datetime(2025, 2, 1, tzinfo=timezone.utc),
            raw={},
        )

        result = calculate_fifo_for_asset(
            ownership=self.ownership,
            base_asset="BTC",
            year=2025,
            eur_converter=EurConverter(),
        )
        self.assertEqual(len(result["warnings"]), 0)
        self.assertEqual(len(result["lots"]), 1)
        lot = result["lots"][0]
        self.assertEqual(lot["exchange_buy"], "binance")
        self.assertEqual(lot["exchange_sell"], "pionex")
        self.assertEqual(lot["quantity"], Decimal("0.005"))
        self.assertEqual(lot["cost_eur"], Decimal("225.000"))
        self.assertEqual(lot["proceeds_eur"], Decimal("276.000"))

    def test_fifo_gap_creates_warning_and_zero_cost(self):
        BrokerTrade.objects.create(
            credential=self.pionex_credential,
            source=BrokerTrade.Source.PIONEX_API,
            trade_id="sell-gap",
            symbol="ETHUSDC",
            base_asset="ETH",
            quote_asset="USDC",
            side=BrokerTrade.Side.SELL,
            price=Decimal("2000"),
            quantity=Decimal("1"),
            fee=Decimal("0"),
            fee_asset="",
            timestamp=datetime(2025, 2, 1, tzinfo=timezone.utc),
            raw={},
        )
        result = calculate_fifo_for_asset(
            ownership=self.ownership,
            base_asset="ETH",
            year=2025,
            eur_converter=EurConverter(),
        )
        self.assertEqual(len(result["warnings"]), 1)
        self.assertEqual(result["lots"][0]["cost_eur"], Decimal("0"))

    def test_generate_fiscal_report_returns_complete_payload(self):
        IncomeEvent.objects.create(
            credential=self.binance_credential,
            source=IncomeEvent.Source.BINANCE_EARN_CSV,
            income_type=IncomeEvent.IncomeType.BINANCE_EARN,
            asset="USDC",
            amount=Decimal("10"),
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            description="Earn",
            raw={},
        )
        BotNetResult.objects.create(
            credential=self.pionex_credential,
            bot_id="bot-1",
            bot_type="spot_grid",
            label="Bot Test",
            base_asset="BTC",
            quote_asset="USDT",
            realized_profit=Decimal("5"),
            total_fee_base=Decimal("0"),
            total_fee_quote=Decimal("0"),
            period_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2025, 1, 15, tzinfo=timezone.utc),
            raw={},
        )
        FuturesPosition.objects.create(
            credential=self.pionex_credential,
            source=FuturesPosition.Source.PIONEX_CSV,
            position_id="pos-1",
            symbol="BTC_USDT_PERP",
            base_asset="BTC",
            side=FuturesPosition.Side.LONG,
            open_time=datetime(2025, 1, 10, tzinfo=timezone.utc),
            close_time=datetime(2025, 1, 12, tzinfo=timezone.utc),
            pnl=Decimal("1"),
            fee=Decimal("0.1"),
            funding_fee=Decimal("0.1"),
            net_pnl=Decimal("0.8"),
            raw={},
        )

        payload = generate_fiscal_report(ownership=self.ownership, year=2025)
        self.assertEqual(payload["fiscal_year"], 2025)
        self.assertIn("capital_mobiliario", payload)
        self.assertIn("ganancias_perdidas_bots", payload)
        self.assertIn("ganancias_perdidas_futuros", payload)
        self.assertIn("ganancias_perdidas_trades", payload)
        self.assertIn("resumen", payload)
        self.assertTrue(payload["data_sources"]["binance_csv_fallback"])
        self.assertEqual(payload["ganancias_perdidas_bots"][0]["incluido_en_resumen_fiscal"], False)
        self.assertEqual(payload["resumen"]["total_ganancias_eur"], 0.72)

    @patch("core.market_data.sync_market_history", autospec=True)
    def test_eur_converter_uses_previous_available_rate_when_exact_day_missing(self, sync_mock):
        FxRate.objects.all().delete()
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate=Decimal("0.89"),
            rate_date=datetime(2024, 12, 31, tzinfo=timezone.utc).date(),
        )

        rate = EurConverter().get_eur_rate(
            trade_date=datetime(2025, 1, 1, tzinfo=timezone.utc).date(),
            asset="USDT",
        )
        self.assertEqual(rate, Decimal("0.89"))
        self.assertTrue(sync_mock.called)
