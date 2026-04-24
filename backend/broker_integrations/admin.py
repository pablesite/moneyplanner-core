from django.contrib import admin

from .models import (
    BotNetResult,
    BrokerCredential,
    MarketRateSnapshot,
    BrokerSyncRun,
    BrokerTrade,
    FuturesPosition,
    IncomeEvent,
)


@admin.register(BrokerCredential)
class BrokerCredentialAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "broker", "label", "ownership", "last_sync_at", "created_at")
    list_filter = ("broker",)
    search_fields = ("label", "user__username", "api_key")


@admin.register(BrokerTrade)
class BrokerTradeAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "trade_id", "symbol", "side", "quantity", "timestamp")
    list_filter = ("source", "side")
    search_fields = ("trade_id", "symbol")


@admin.register(BrokerSyncRun)
class BrokerSyncRunAdmin(admin.ModelAdmin):
    list_display = ("id", "credential", "year", "status", "started_at", "finished_at")
    list_filter = ("status", "year")
    search_fields = ("credential__label", "credential__user__username")


@admin.register(MarketRateSnapshot)
class MarketRateSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "pair", "interval", "open_time", "close", "source")
    list_filter = ("interval", "source")
    search_fields = ("pair",)


@admin.register(BotNetResult)
class BotNetResultAdmin(admin.ModelAdmin):
    list_display = ("id", "credential", "bot_id", "realized_profit", "period_end")
    search_fields = ("bot_id", "label")


@admin.register(FuturesPosition)
class FuturesPositionAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "position_id", "symbol", "side", "net_pnl", "close_time")
    list_filter = ("source", "side")
    search_fields = ("position_id", "symbol")


@admin.register(IncomeEvent)
class IncomeEventAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "income_type", "asset", "amount", "timestamp")
    list_filter = ("source", "income_type")
    search_fields = ("asset", "description")


# Register your models here.
