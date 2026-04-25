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
    ManualCostBasis,
)
from broker_integrations.services.fifo_calculator import _dedup_trades_by_fiscal_key
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
            price_eur=Decimal("45000"),
            quantity=Decimal("0.01"),
            fee=Decimal("0"),
            fee_eur=Decimal("0"),
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
            price_eur=Decimal("55200"),
            quantity=Decimal("0.005"),
            fee=Decimal("0"),
            fee_eur=Decimal("0"),
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
        self.assertEqual(len(result["sales"]), 1)
        sale = result["sales"][0]
        self.assertEqual(sale["sell_exchange"], "pionex")
        self.assertEqual(sale["quantity_sold"], Decimal("0.005"))
        self.assertEqual(sale["proceeds_eur"], Decimal("276.0000"))
        self.assertEqual(len(sale["matched_lots"]), 1)
        lot = sale["matched_lots"][0]
        self.assertEqual(lot["buy_exchange"], "binance")
        self.assertEqual(lot["quantity_consumed"], Decimal("0.005"))
        self.assertEqual(lot["cost_eur"], Decimal("225.000"))

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
            price_eur=Decimal("1840"),
            quantity=Decimal("1"),
            fee=Decimal("0"),
            fee_eur=Decimal("0"),
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
        sale = result["sales"][0]
        self.assertEqual(sale["gap_quantity"], Decimal("1"))
        self.assertEqual(sale["gap_reason"], "balance_transfer_in")

    def test_fifo_allocates_sell_fee_proportionally(self):
        BrokerTrade.objects.create(
            credential=self.binance_credential,
            source=BrokerTrade.Source.BINANCE_API,
            trade_id="buy-fee-a",
            symbol="SOLUSDT",
            base_asset="SOL",
            quote_asset="USDT",
            side=BrokerTrade.Side.BUY,
            price=Decimal("100"),
            price_eur=Decimal("90"),
            quantity=Decimal("2"),
            fee=Decimal("0"),
            fee_eur=Decimal("0"),
            fee_asset="",
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            raw={},
        )
        BrokerTrade.objects.create(
            credential=self.binance_credential,
            source=BrokerTrade.Source.BINANCE_API,
            trade_id="buy-fee-b",
            symbol="SOLUSDT",
            base_asset="SOL",
            quote_asset="USDT",
            side=BrokerTrade.Side.BUY,
            price=Decimal("120"),
            price_eur=Decimal("108"),
            quantity=Decimal("2"),
            fee=Decimal("0"),
            fee_eur=Decimal("0"),
            fee_asset="",
            timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc),
            raw={},
        )
        BrokerTrade.objects.create(
            credential=self.pionex_credential,
            source=BrokerTrade.Source.PIONEX_API,
            trade_id="sell-fee",
            symbol="SOLUSDT",
            base_asset="SOL",
            quote_asset="USDT",
            side=BrokerTrade.Side.SELL,
            price=Decimal("130"),
            price_eur=Decimal("117"),
            quantity=Decimal("3"),
            fee=Decimal("0.3"),
            fee_eur=Decimal("9"),
            fee_asset="USDT",
            timestamp=datetime(2025, 2, 1, tzinfo=timezone.utc),
            raw={},
        )
        result = calculate_fifo_for_asset(
            ownership=self.ownership,
            base_asset="SOL",
            year=2025,
            eur_converter=EurConverter(),
        )
        sale = result["sales"][0]
        self.assertEqual(len(sale["matched_lots"]), 2)
        self.assertEqual(sale["matched_lots"][0]["fee_eur_allocated"], Decimal("6"))
        self.assertEqual(sale["matched_lots"][1]["fee_eur_allocated"], Decimal("3"))

    def test_manual_cost_basis_is_consumed_before_trade_lots_when_older(self):
        ManualCostBasis.objects.create(
            ownership=self.ownership,
            asset="ETH",
            quantity=Decimal("0.50"),
            quantity_remaining=Decimal("0.50"),
            acquired_at=datetime(2024, 12, 20, tzinfo=timezone.utc),
            cost_eur=Decimal("500"),
            exchange_origin="external",
            notes="legacy wallet",
        )
        BrokerTrade.objects.create(
            credential=self.binance_credential,
            source=BrokerTrade.Source.BINANCE_API,
            trade_id="buy-eth",
            symbol="ETHUSDT",
            base_asset="ETH",
            quote_asset="USDT",
            side=BrokerTrade.Side.BUY,
            price=Decimal("2000"),
            price_eur=Decimal("1800"),
            quantity=Decimal("1.0"),
            fee=Decimal("0"),
            fee_eur=Decimal("0"),
            fee_asset="",
            timestamp=datetime(2025, 1, 10, tzinfo=timezone.utc),
            raw={},
        )
        BrokerTrade.objects.create(
            credential=self.pionex_credential,
            source=BrokerTrade.Source.PIONEX_API,
            trade_id="sell-eth",
            symbol="ETHUSDT",
            base_asset="ETH",
            quote_asset="USDT",
            side=BrokerTrade.Side.SELL,
            price=Decimal("2200"),
            price_eur=Decimal("1980"),
            quantity=Decimal("0.6"),
            fee=Decimal("0"),
            fee_eur=Decimal("0"),
            fee_asset="",
            timestamp=datetime(2025, 2, 5, tzinfo=timezone.utc),
            raw={},
        )
        result = calculate_fifo_for_asset(
            ownership=self.ownership,
            base_asset="ETH",
            year=2025,
            eur_converter=EurConverter(),
        )
        sale = result["sales"][0]
        self.assertIsNotNone(sale["matched_lots"][0]["manual_cost_basis_id"])

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
        self.assertEqual(payload["schema_version"], 3)
        self.assertEqual(payload["fiscal_year"], 2025)
        self.assertIn("capital_mobiliario", payload)
        self.assertIn("ganancias_perdidas_bots", payload)
        self.assertIn("ganancias_perdidas_futuros", payload)
        self.assertIn("ganancias_perdidas_trades", payload)
        self.assertIn("resumen", payload)
        self.assertIn("resumen_diagnostico", payload)
        self.assertIn("reliability", payload)
        self.assertTrue(payload["data_sources"]["binance_csv_fallback"])
        self.assertEqual(payload["ganancias_perdidas_bots"][0]["incluido_en_resumen_fiscal"], False)
        self.assertEqual(payload["resumen"]["total_ganancias_eur"], 0.72)
        self.assertIsInstance(payload["ganancias_perdidas_trades"], list)

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


class Phase5GReliabilityTests(TestCase):
    """Tests for Phase 5G: API-first reliability gates."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="5g_user", password="pass1234")
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
        self.credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.PIONEX,
            label="pionex-5g",
            api_key="k",
            api_secret_encrypted=b"s",
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
            rate_date=datetime(2025, 6, 1, tzinfo=timezone.utc).date(),
        )

    def _make_trade(
        self,
        *,
        trade_id,
        source,
        side,
        symbol="BTC_USDT",
        base_asset="BTC",
        quantity="0.1",
        price="50000",
        timestamp=None,
        fiscal_provenance="",
        fiscal_identity_key="",
    ):
        if timestamp is None:
            timestamp = datetime(2025, 1, 10, tzinfo=timezone.utc)
        return BrokerTrade.objects.create(
            credential=self.credential,
            source=source,
            trade_id=trade_id,
            symbol=symbol,
            base_asset=base_asset,
            quote_asset="USDT",
            side=side,
            price=Decimal(price),
            price_eur=Decimal(price) * Decimal("0.90"),
            quantity=Decimal(quantity),
            fee=Decimal("0"),
            fee_eur=Decimal("0"),
            fee_asset="",
            timestamp=timestamp,
            fiscal_provenance=fiscal_provenance,
            fiscal_identity_key=fiscal_identity_key,
            raw={},
        )

    def test_schema_version_is_3(self):
        payload = generate_fiscal_report(ownership=self.ownership, year=2025)
        self.assertEqual(payload["schema_version"], 3)

    def test_reliability_block_present(self):
        payload = generate_fiscal_report(ownership=self.ownership, year=2025)
        self.assertIn("reliability", payload)
        rel = payload["reliability"]
        self.assertIn("status", rel)
        self.assertIn("blocking_gaps", rel)
        self.assertIn("input_coverage", rel)
        self.assertIn("source_comparison", rel)

    def test_reliability_declarable_when_no_gaps(self):
        self._make_trade(
            trade_id="buy-1",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.BUY,
            fiscal_provenance=BrokerTrade.FiscalProvenance.API,
            timestamp=datetime(2025, 1, 5, tzinfo=timezone.utc),
        )
        self._make_trade(
            trade_id="sell-1",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.SELL,
            fiscal_provenance=BrokerTrade.FiscalProvenance.API,
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        payload = generate_fiscal_report(ownership=self.ownership, year=2025)
        self.assertEqual(payload["reliability"]["status"], "declarable")
        self.assertIsNotNone(payload["resumen_declarable"])

    def test_usdc_sale_without_cost_basis_blocks_declarable(self):
        # SELL USDC with no BUY → gap_reason=balance_transfer_in → blocked
        self._make_trade(
            trade_id="sell-usdc",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.SELL,
            symbol="USDC_USDT",
            base_asset="USDC",
            quantity="1000",
            price="1",
            fiscal_provenance=BrokerTrade.FiscalProvenance.API,
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        payload = generate_fiscal_report(ownership=self.ownership, year=2025)
        self.assertEqual(payload["reliability"]["status"], "blocked_missing_cost_basis")
        self.assertIsNone(payload["resumen_declarable"])
        self.assertTrue(len(payload["reliability"]["blocking_gaps"]) > 0)

    def test_manual_cost_basis_unblocks_declarable(self):
        # Same scenario: SELL USDC, but user provided ManualCostBasis
        ManualCostBasis.objects.create(
            ownership=self.ownership,
            asset="USDC",
            quantity=Decimal("1000"),
            quantity_remaining=Decimal("1000"),
            acquired_at=datetime(2024, 12, 1, tzinfo=timezone.utc),
            cost_eur=Decimal("900"),
            exchange_origin="external",
        )
        self._make_trade(
            trade_id="sell-usdc-2",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.SELL,
            symbol="USDC_USDT",
            base_asset="USDC",
            quantity="1000",
            price="1",
            fiscal_provenance=BrokerTrade.FiscalProvenance.API,
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        payload = generate_fiscal_report(ownership=self.ownership, year=2025)
        self.assertEqual(payload["reliability"]["status"], "declarable")
        self.assertIsNotNone(payload["resumen_declarable"])

    def test_api_csv_dedup_does_not_double_count_in_fifo(self):
        # Same economic event as API trade and CSV trade: should count only once in pool
        key = "abc123dedup01"
        self._make_trade(
            trade_id="api-buy",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.BUY,
            fiscal_provenance=BrokerTrade.FiscalProvenance.API,
            fiscal_identity_key=key,
            quantity="0.1",
            timestamp=datetime(2025, 1, 5, tzinfo=timezone.utc),
        )
        self._make_trade(
            trade_id="csv-buy",
            source=BrokerTrade.Source.PIONEX_CSV,
            side=BrokerTrade.Side.BUY,
            fiscal_provenance=BrokerTrade.FiscalProvenance.CSV_FALLBACK,
            fiscal_identity_key=key,
            quantity="0.1",
            timestamp=datetime(2025, 1, 5, tzinfo=timezone.utc),
        )
        self._make_trade(
            trade_id="sell-1",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.SELL,
            fiscal_provenance=BrokerTrade.FiscalProvenance.API,
            fiscal_identity_key="",
            quantity="0.1",
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        result = calculate_fifo_for_asset(
            ownership=self.ownership,
            base_asset="BTC",
            year=2025,
            eur_converter=EurConverter(),
        )
        # Only one BUY in pool (deduped), so sell of 0.1 should be fully matched
        self.assertEqual(len(result["warnings"]), 0)
        self.assertEqual(len(result["sales"]), 1)
        self.assertEqual(result["sales"][0]["gap_quantity"], Decimal("0"))

    def test_dedup_prefers_api_over_csv(self):
        key = "dedup_pref_key1"
        api_trade = self._make_trade(
            trade_id="api-t",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.BUY,
            fiscal_provenance=BrokerTrade.FiscalProvenance.API,
            fiscal_identity_key=key,
        )
        csv_trade = self._make_trade(
            trade_id="csv-t",
            source=BrokerTrade.Source.PIONEX_CSV,
            side=BrokerTrade.Side.BUY,
            fiscal_provenance=BrokerTrade.FiscalProvenance.CSV_FALLBACK,
            fiscal_identity_key=key,
        )
        trades = list(
            BrokerTrade.objects.filter(id__in=[api_trade.id, csv_trade.id]).order_by("id")
        )
        deduped = _dedup_trades_by_fiscal_key(trades)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].fiscal_provenance, BrokerTrade.FiscalProvenance.API)

    def test_source_comparison_counts_matched_and_unmatched(self):
        shared_key = "shared1234567890"
        api_only_key = "apionly12345678"
        csv_only_key = "csvonly12345678"
        self._make_trade(
            trade_id="api-shared",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.BUY,
            fiscal_identity_key=shared_key,
        )
        self._make_trade(
            trade_id="csv-shared",
            source=BrokerTrade.Source.PIONEX_CSV,
            side=BrokerTrade.Side.BUY,
            fiscal_identity_key=shared_key,
        )
        self._make_trade(
            trade_id="api-only",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.BUY,
            fiscal_identity_key=api_only_key,
        )
        self._make_trade(
            trade_id="csv-only",
            source=BrokerTrade.Source.PIONEX_CSV,
            side=BrokerTrade.Side.BUY,
            fiscal_identity_key=csv_only_key,
        )
        payload = generate_fiscal_report(ownership=self.ownership, year=2025)
        sc = payload["reliability"]["source_comparison"]
        self.assertEqual(sc["matched"], 1)
        self.assertEqual(sc["api_only"], 1)
        self.assertEqual(sc["csv_only"], 1)

    def test_resumen_declarable_excludes_gap_sales(self):
        # One clean sell (matched) and one gap sell (unmatched) in the same report
        self._make_trade(
            trade_id="buy-eth",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.BUY,
            symbol="ETH_USDT",
            base_asset="ETH",
            quantity="1",
            price="2000",
            fiscal_provenance=BrokerTrade.FiscalProvenance.API,
            timestamp=datetime(2025, 1, 5, tzinfo=timezone.utc),
        )
        self._make_trade(
            trade_id="sell-eth",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.SELL,
            symbol="ETH_USDT",
            base_asset="ETH",
            quantity="1",
            price="2200",
            fiscal_provenance=BrokerTrade.FiscalProvenance.API,
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        # USDC gap sell (no buy → balance_transfer_in → blocks declarable)
        self._make_trade(
            trade_id="sell-usdc-gap",
            source=BrokerTrade.Source.PIONEX_API,
            side=BrokerTrade.Side.SELL,
            symbol="USDC_USDT",
            base_asset="USDC",
            quantity="500",
            price="1",
            fiscal_provenance=BrokerTrade.FiscalProvenance.API,
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        payload = generate_fiscal_report(ownership=self.ownership, year=2025)
        # blocked_missing_cost_basis → declarable is null
        self.assertEqual(payload["reliability"]["status"], "blocked_missing_cost_basis")
        self.assertIsNone(payload["resumen_declarable"])
        # diagnostico still shows all numbers
        self.assertIsNotNone(payload["resumen_diagnostico"])
        self.assertGreater(payload["resumen_diagnostico"]["total_ganancias_eur"], 0)
