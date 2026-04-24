import os
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase

from broker_integrations.models import BotNetResult, BrokerCredential, BrokerSyncRun, BrokerTrade
from broker_integrations.services.broker_sync import sync_binance, sync_credential, sync_pionex
from broker_integrations.services.binance_client import BinanceApiError
from broker_integrations.services.encryption import encrypt
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
