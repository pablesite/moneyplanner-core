from django.conf import settings
from django.db import models

from memberships.models import Ownership


class BrokerCredential(models.Model):
    class Broker(models.TextChoices):
        PIONEX = "pionex", "Pionex"
        BINANCE = "binance", "Binance"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="broker_credentials",
    )
    ownership = models.ForeignKey(
        Ownership, on_delete=models.CASCADE, related_name="broker_credentials"
    )
    broker = models.CharField(max_length=20, choices=Broker.choices)
    label = models.CharField(max_length=100)
    api_key = models.CharField(max_length=200)
    api_secret_encrypted = models.BinaryField()
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_stats = models.JSONField(default=dict, blank=True)
    last_sync_gaps = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "broker"]),
            models.Index(fields=["ownership"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "broker", "label"],
                name="uniq_broker_credential_label_per_user",
            )
        ]
        ordering = ["-created_at", "-id"]


class BrokerTrade(models.Model):
    class Source(models.TextChoices):
        PIONEX_API = "pionex_api", "Pionex API"
        PIONEX_BOT_API = "pionex_bot_api", "Pionex Bot API"
        PIONEX_CSV = "pionex_csv", "Pionex CSV"
        BINANCE_API = "binance_api", "Binance API"
        BINANCE_CSV = "binance_csv", "Binance CSV"

    class Side(models.TextChoices):
        BUY = "BUY", "BUY"
        SELL = "SELL", "SELL"

    credential = models.ForeignKey(
        BrokerCredential,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trades",
    )
    bot = models.ForeignKey(
        "BotNetResult",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fills",
    )
    source = models.CharField(max_length=20, choices=Source.choices)
    trade_id = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20)
    base_asset = models.CharField(max_length=10)
    quote_asset = models.CharField(max_length=10)
    side = models.CharField(max_length=4, choices=Side.choices)
    price = models.DecimalField(max_digits=24, decimal_places=10)
    quantity = models.DecimalField(max_digits=24, decimal_places=10)
    fee = models.DecimalField(max_digits=24, decimal_places=10, default=0)
    fee_asset = models.CharField(max_length=10, blank=True, default="")
    timestamp = models.DateTimeField(db_index=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["source", "timestamp"])]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "trade_id"],
                name="uniq_broker_trade_source_trade_id",
            )
        ]
        ordering = ["timestamp", "id"]


class BotNetResult(models.Model):
    credential = models.ForeignKey(
        BrokerCredential,
        on_delete=models.CASCADE,
        related_name="bot_results",
    )
    bot_id = models.CharField(max_length=100)
    bot_type = models.CharField(max_length=50)
    label = models.CharField(max_length=200)
    base_asset = models.CharField(max_length=10)
    quote_asset = models.CharField(max_length=10)
    realized_profit = models.DecimalField(max_digits=24, decimal_places=10)
    total_fee_base = models.DecimalField(max_digits=24, decimal_places=10, default=0)
    total_fee_quote = models.DecimalField(max_digits=24, decimal_places=10, default=0)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    synced_at = models.DateTimeField(auto_now=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["credential", "bot_id"],
                name="uniq_bot_result_credential_bot_id",
            )
        ]
        ordering = ["-period_end", "-id"]


class FuturesPosition(models.Model):
    class Source(models.TextChoices):
        PIONEX_API = "pionex_api", "Pionex API"
        PIONEX_CSV = "pionex_csv", "Pionex CSV"

    class Side(models.TextChoices):
        LONG = "long", "Long"
        SHORT = "short", "Short"

    credential = models.ForeignKey(
        BrokerCredential,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="futures_positions",
    )
    source = models.CharField(max_length=20, choices=Source.choices)
    position_id = models.CharField(max_length=200)
    symbol = models.CharField(max_length=30)
    base_asset = models.CharField(max_length=10)
    side = models.CharField(max_length=10, choices=Side.choices)
    open_time = models.DateTimeField()
    close_time = models.DateTimeField()
    pnl = models.DecimalField(max_digits=24, decimal_places=10)
    fee = models.DecimalField(max_digits=24, decimal_places=10, default=0)
    funding_fee = models.DecimalField(max_digits=24, decimal_places=10, default=0)
    net_pnl = models.DecimalField(max_digits=24, decimal_places=10)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["source", "close_time"])]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "position_id"],
                name="uniq_futures_position_source_position_id",
            )
        ]
        ordering = ["close_time", "id"]


class IncomeEvent(models.Model):
    class Source(models.TextChoices):
        PIONEX_STAKING_API = "pionex_staking_api", "Pionex Staking API"
        PIONEX_STAKING_CSV = "pionex_staking_csv", "Pionex Staking CSV"
        PIONEX_DUAL_INVEST_API = "pionex_dual_invest_api", "Pionex Dual Invest API"
        PIONEX_COMMISSION_CSV = "pionex_commission_csv", "Pionex Commission CSV"
        BINANCE_EARN_API = "binance_earn_api", "Binance Earn API"
        BINANCE_EARN_CSV = "binance_earn_csv", "Binance Earn CSV"
        BINANCE_REFERRAL_CSV = "binance_referral_csv", "Binance Referral CSV"
        MANUAL = "manual", "Manual"

    class IncomeType(models.TextChoices):
        EARN_ISSUED = "earn_issued", "Earn Issued"
        EARN_CLAIMED = "earn_claimed", "Earn Claimed"
        DUAL_INVEST_YIELD = "dual_invest_yield", "Dual Invest Yield"
        COMMISSION = "commission", "Commission"
        BINANCE_EARN = "binance_earn", "Binance Earn"

    credential = models.ForeignKey(
        BrokerCredential,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="income_events",
    )
    source = models.CharField(max_length=30, choices=Source.choices)
    income_type = models.CharField(max_length=30, choices=IncomeType.choices)
    asset = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=24, decimal_places=10)
    timestamp = models.DateTimeField(db_index=True)
    description = models.CharField(max_length=300, blank=True, default="")
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["source", "timestamp"])]
        ordering = ["timestamp", "id"]


# Create your models here.
