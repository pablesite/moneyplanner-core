import os
from decimal import Decimal
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from broker_integrations.models import (
    BotNetResult,
    BrokerCredential,
    BrokerSyncRun,
    BrokerTrade,
    IncomeEvent,
)
from broker_integrations.services.broker_sync import sync_binance, sync_credential, sync_pionex
from broker_integrations.services.binance_client import BinanceApiError
from broker_integrations.services.encryption import encrypt
from broker_integrations.services.pionex_client import PionexApiError
from memberships.models import FamilyMember, Ownership


class _FakePionexClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_balances(self):
        return []

    def get_fills(self, **kwargs):
        return []

    def get_dual_invest_records(self, **kwargs):
        return []

    def get_bot_orders(self, *, status: str = "running", page_token=None, limit: int = 100):
        if status == "running":
            return (
                [
                    {"buOrderId": "bot-running-1", "buOrderType": "spot_grid"},
                    {"buOrderId": "future-ignored", "buOrderType": "futures_grid"},
                ],
                None,
            )
        if status == "finished":
            return ([{"buOrderId": "bot-finished-1", "buOrderType": "spot_grid"}], None)
        return ([], None)

    def get_bot_summary(self, *, bot_id: str):
        return {
            "symbol": "ETH_USDT",
            "botType": "spot_grid",
            "name": f"Bot {bot_id}",
            "realizedProfit": "12.34",
            "totalFeeBase": "0.01",
            "totalFeeQuote": "0.02",
            "startTime": 1735689600000,
            "endTime": 1767225599000,
        }

    def get_bot_spot_grid_orders(self, bot_id: str, **kwargs):
        return []


class _FakePionexClientNoDiscovery(_FakePionexClient):
    def get_bot_orders(self, *, status: str = "running", page_token=None, limit: int = 100):
        return ([], None)


class _FakePionexClientGridProfit:
    def __init__(self, *args, **kwargs):
        pass

    def get_balances(self):
        return []

    def get_fills(self, **kwargs):
        return []

    def get_dual_invest_records(self, **kwargs):
        return []

    def get_bot_orders(self, *, status: str = "running", page_token=None, limit: int = 100):
        if status == "running":
            return (
                [
                    {
                        "buOrderId": "bot-grid-profit-1",
                        "buOrderType": "spot_grid",
                        "base": "ETH",
                        "quote": "USDT",
                        "buOrderData": {
                            "realizedProfit": "0",
                            "gridProfit": "4.2",
                        },
                    }
                ],
                None,
            )
        return ([], None)

    def get_bot_summary(self, *, bot_id: str):
        return {}

    def get_bot_spot_grid_orders(self, bot_id: str, **kwargs):
        return []


class _FakePionexClientBotFills(_FakePionexClient):
    def get_balances(self):
        return [
            {"coin": "BTC", "amount": "2"},
            {"coin": "USDT", "amount": "0"},
        ]

    def get_bot_orders(self, *, status: str = "running", page_token=None, limit: int = 100):
        if status == "running":
            return ([{"buOrderId": "bot-running-1", "buOrderType": "spot_grid"}], None)
        return ([], None)

    def get_bot_spot_grid_orders(self, bot_id: str, **kwargs):
        return [
            {
                "id": f"{bot_id}-fill-1",
                "symbol": "BTC_USDT",
                "side": "BUY",
                "price": "50000",
                "size": "1",
                "fee": "0.001",
                "feeCoin": "BTC",
                "timestamp": 1735689600000,
            }
        ]


class _FakePionexClientBotSymbolsFromHistory(_FakePionexClient):
    def get_balances(self):
        return []

    def get_bot_orders(self, *, status: str = "running", page_token=None, limit: int = 100):
        if status == "finished":
            return (
                [
                    {
                        "buOrderId": "bot-history-1",
                        "buOrderType": "spot_grid",
                        "symbol": "ADA_USDT",
                    }
                ],
                None,
            )
        return ([], None)

    def get_fills(self, **kwargs):
        if kwargs.get("symbol") != "ADA_USDT":
            return []
        return [
            {
                "id": "ada-fill-1",
                "symbol": "ADA_USDT",
                "side": "BUY",
                "price": "0.5",
                "size": "100",
                "fee": "0.1",
                "feeCoin": "ADA",
                "timestamp": 1706745600000,  # 2024-02-01 UTC
            }
        ]

    def get_bot_spot_grid_orders(self, bot_id: str, **kwargs):
        return []


class _FakePionexClientBot404Independence(_FakePionexClient):
    """bot-first raises HTTP 404; bot-second should still receive its fills."""

    def get_bot_orders(self, *, status: str = "running", page_token=None, limit: int = 100):
        if status == "running":
            return (
                [
                    {"buOrderId": "bot-first", "buOrderType": "spot_grid"},
                    {"buOrderId": "bot-second", "buOrderType": "spot_grid"},
                ],
                None,
            )
        return ([], None)

    def get_bot_spot_grid_orders(self, bot_id: str, **kwargs):
        if bot_id == "bot-first":
            raise PionexApiError("Pionex HTTP 404")
        return [
            {
                "id": f"{bot_id}-fill-1",
                "symbol": "ETH_USDT",
                "side": "BUY",
                "price": "2000",
                "size": "1",
                "fee": "0.001",
                "feeCoin": "ETH",
                "timestamp": 1735689600000,
            }
        ]


class _FakePionexClientDualFromDB(_FakePionexClient):
    """Empty balances but returns a SOL dual record when base=SOL is requested."""

    def get_balances(self):
        return []

    def get_dual_invest_records(self, **kwargs):
        if kwargs.get("base") == "SOL":
            return [
                {
                    "recordId": "sol-dual-1",
                    "settleTime": 1735689600000,
                    "yieldAmount": "0.5",
                    "asset": "SOL",
                }
            ]
        return []


class _FakeBinanceClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_convert_history(self, *, start_ms: int, end_ms: int):
        return [
            {
                "orderId": "convert-1",
                "fromAsset": "USDC",
                "fromAmount": "20",
                "toAsset": "ETH",
                "toAmount": "0.006",
                "createTime": 1735689600000,
                "symbol": "ETHUSDC",
            }
        ]

    def get_earn_flexible_rewards(self, *, asset: str, start_ms: int, end_ms: int):
        if asset != "USDC":
            return []
        return [
            {
                "asset": "USDC",
                "rewards": "1.5",
                "time": 1735689600000,
            }
        ]

    def get_pay_transactions(self, *, start_ms: int, end_ms: int):
        return [
            {
                "transactionId": "pay-1",
                "transactionTime": 1735689600000,
                "currency": "USDC",
                "amount": "50",
                "targetAsset": "BTC",
                "targetAmount": "0.0005",
                "fee": "0.000001",
            }
        ]

    def get_referral_rebates(self, *, start_ms: int, end_ms: int):
        raise BinanceApiError("Verification failed", code="100001003")


class BrokerSyncTests(TestCase):
    def setUp(self):
        os.environ["BROKER_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        User = get_user_model()
        self.user = User.objects.create_user(username="sync_user", password="pass1234")
        member = FamilyMember.objects.create(
            user=self.user,
            name="Primary",
            role=FamilyMember.Role.ADULT,
        )
        ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=member,
        )
        self.credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=ownership,
            broker=BrokerCredential.Broker.PIONEX,
            label="sync-cred",
            api_key="key",
            api_secret_encrypted=encrypt("secret"),
        )
        self.fx_patcher = patch(
            "broker_integrations.services.broker_sync.get_rate_at",
            return_value=(Decimal("1"), "test_fx"),
        )
        self.fx_patcher.start()

    def tearDown(self):
        self.fx_patcher.stop()
        super().tearDown()

    @patch("broker_integrations.services.broker_sync.PionexClient", _FakePionexClient)
    def test_sync_pionex_discovers_bot_ids_automatically(self):
        os.environ.pop("PIONEX_BOT_IDS", None)
        stats = sync_pionex(credential=self.credential, year=2025)
        self.assertEqual(stats["new_bot_results"], 2)
        self.assertEqual(stats["updated_bot_results"], 0)
        sync_run = BrokerSyncRun.objects.filter(credential=self.credential).latest("id")
        self.assertEqual(sync_run.status, BrokerSyncRun.Status.OK)
        self.assertEqual(sync_run.year, 2025)
        self.assertEqual(len(sync_run.new_bot_result_ids), 2)
        self.assertEqual(BotNetResult.objects.filter(credential=self.credential).count(), 2)
        self.assertSetEqual(
            set(
                BotNetResult.objects.filter(credential=self.credential).values_list(
                    "bot_id", flat=True
                )
            ),
            {"bot-running-1", "bot-finished-1"},
        )

    @patch("broker_integrations.services.broker_sync.PionexClient", _FakePionexClientNoDiscovery)
    def test_sync_pionex_uses_env_bot_ids_as_fallback(self):
        os.environ["PIONEX_BOT_IDS"] = "env-bot-1"
        stats = sync_pionex(credential=self.credential, year=2025)
        self.assertEqual(stats["new_bot_results"], 1)
        self.assertEqual(
            BotNetResult.objects.filter(credential=self.credential)
            .values_list("bot_id", flat=True)
            .first(),
            "env-bot-1",
        )

    @patch("broker_integrations.services.broker_sync.PionexClient", _FakePionexClientGridProfit)
    def test_sync_pionex_prefers_grid_profit_when_realized_profit_is_zero(self):
        stats = sync_pionex(credential=self.credential, year=2025)
        self.assertEqual(stats["new_bot_results"], 1)
        bot = BotNetResult.objects.get(credential=self.credential, bot_id="bot-grid-profit-1")
        self.assertEqual(str(bot.realized_profit), "4.2000000000")

    @patch("broker_integrations.services.broker_sync.PionexClient", _FakePionexClientBotFills)
    def test_sync_pionex_persists_bot_fills_and_balance_reconciliation_gaps(self):
        stats = sync_pionex(credential=self.credential, year=2025)
        bot = BotNetResult.objects.get(credential=self.credential, bot_id="bot-running-1")
        trade = BrokerTrade.objects.get(
            credential=self.credential,
            source=BrokerTrade.Source.PIONEX_BOT_API,
            trade_id="bot-running-1-fill-1",
        )
        self.assertEqual(trade.bot_id, bot.id)
        self.assertTrue(
            any(
                gap.get("source") == "balance_reconciliation"
                and gap.get("reason") == "balance_mismatch"
                and gap.get("asset") == "BTC"
                for gap in stats["gaps"]
            )
        )
        sync_run = BrokerSyncRun.objects.filter(credential=self.credential).latest("id")
        self.assertEqual(sync_run.status, BrokerSyncRun.Status.PARTIAL)
        self.assertGreaterEqual(len(sync_run.new_trade_ids), 1)

    @patch(
        "broker_integrations.services.broker_sync.PionexClient",
        _FakePionexClientBotSymbolsFromHistory,
    )
    def test_sync_pionex_uses_finished_bot_symbols_for_spot_fills(self):
        stats = sync_pionex(credential=self.credential, year=2024)
        self.assertEqual(stats["new_trades"], 1)
        self.assertTrue(
            BrokerTrade.objects.filter(
                credential=self.credential,
                source=BrokerTrade.Source.PIONEX_API,
                trade_id="ada-fill-1",
                symbol="ADA_USDT",
            ).exists()
        )

    @patch("broker_integrations.services.broker_sync.BinanceClient", _FakeBinanceClient)
    def test_sync_binance_collects_trades_income_and_gap(self):
        credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.credential.ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="sync-binance",
            api_key="binance-key",
            api_secret_encrypted=encrypt("binance-secret"),
        )
        os.environ["BINANCE_EARN_ASSETS"] = "USDC,BTC"
        stats = sync_binance(credential=credential, year=2025)
        self.assertEqual(stats["new_trades"], 2)
        self.assertEqual(stats["new_income_events"], 1)
        self.assertTrue(any(gap["source"] == "rebate_tax_query" for gap in stats["gaps"]))

    @patch("broker_integrations.services.broker_sync.BinanceClient", _FakeBinanceClient)
    def test_sync_credential_routes_to_binance(self):
        credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.credential.ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="sync-router-binance",
            api_key="binance-key-2",
            api_secret_encrypted=encrypt("binance-secret-2"),
        )
        stats = sync_credential(credential=credential, year=2025)
        self.assertEqual(stats["new_trades"], 2)

    @patch(
        "broker_integrations.services.broker_sync.PionexClient",
        _FakePionexClientBot404Independence,
    )
    def test_sync_pionex_bot_404_does_not_block_other_bots(self):
        """A 404 on bot-first's fills must not prevent bot-second from being processed."""
        stats = sync_pionex(credential=self.credential, year=2025)
        # bot-second's fill is recorded despite bot-first's 404
        self.assertTrue(
            BrokerTrade.objects.filter(
                credential=self.credential,
                source=BrokerTrade.Source.PIONEX_BOT_API,
                trade_id="bot-second-fill-1",
            ).exists()
        )
        # The gap for bot-first is recorded with the right reason
        self.assertTrue(
            any(
                gap.get("source") == "bot_fills:bot-first"
                and gap.get("reason") == "endpoint_unavailable"
                for gap in stats["gaps"]
            )
        )

    @patch(
        "broker_integrations.services.broker_sync.PionexClient",
        _FakePionexClientDualFromDB,
    )
    def test_sync_pionex_discovers_dual_bases_from_db_history(self):
        """A SOL IncomeEvent already in DB should cause SOL to be queried even with no balance."""
        IncomeEvent.objects.create(
            credential=self.credential,
            source=IncomeEvent.Source.PIONEX_DUAL_INVEST_API,
            income_type=IncomeEvent.IncomeType.DUAL_INVEST_YIELD,
            asset="SOL",
            amount=Decimal("0.1"),
            timestamp=timezone.now(),
        )
        stats = sync_pionex(credential=self.credential, year=2025)
        self.assertEqual(stats["new_income_events"], 1)
        self.assertTrue(
            IncomeEvent.objects.filter(
                credential=self.credential,
                source=IncomeEvent.Source.PIONEX_DUAL_INVEST_API,
                asset="SOL",
                amount=Decimal("0.5"),
            ).exists()
        )
