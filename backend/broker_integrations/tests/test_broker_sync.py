import os
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase

from broker_integrations.models import BotNetResult, BrokerCredential
from broker_integrations.services.broker_sync import sync_pionex
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


class _FakePionexClientNoDiscovery(_FakePionexClient):
    def get_bot_orders(self, *, status: str = "running", page_token=None, limit: int = 100):
        return ([], None)


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
        self.assertEqual(BotNetResult.objects.filter(credential=self.credential).count(), 2)
        self.assertSetEqual(
            set(
                BotNetResult.objects.filter(credential=self.credential).values_list("bot_id", flat=True)
            ),
            {"bot-running-1", "bot-finished-1"},
        )

    @patch("broker_integrations.services.broker_sync.PionexClient", _FakePionexClientNoDiscovery)
    def test_sync_pionex_uses_env_bot_ids_as_fallback(self):
        os.environ["PIONEX_BOT_IDS"] = "env-bot-1"
        stats = sync_pionex(credential=self.credential, year=2025)
        self.assertEqual(stats["new_bot_results"], 1)
        self.assertEqual(
            BotNetResult.objects.filter(credential=self.credential).values_list("bot_id", flat=True).first(),
            "env-bot-1",
        )
