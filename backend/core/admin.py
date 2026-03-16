from django.contrib import admin

from .models import FxRate, InflationIndex, MarketDataSyncState


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    list_display = (
        "from_currency",
        "to_currency",
        "rate",
        "rate_date",
        "updated_at",
    )
    list_filter = (
        "from_currency",
        "to_currency",
        "rate_date",
    )
    search_fields = (
        "from_currency",
        "to_currency",
    )
    ordering = (
        "-rate_date",
        "from_currency",
        "to_currency",
    )
    date_hierarchy = "rate_date"


@admin.register(InflationIndex)
class InflationIndexAdmin(admin.ModelAdmin):
    list_display = (
        "region",
        "period",
        "index",
        "updated_at",
    )
    list_filter = (
        "region",
        "period",
    )
    ordering = ("-period",)
    date_hierarchy = "period"


@admin.register(MarketDataSyncState)
class MarketDataSyncStateAdmin(admin.ModelAdmin):
    list_display = (
        "dataset",
        "scope",
        "required_start_date",
        "covered_until",
        "last_success_at",
    )
    list_filter = ("dataset",)
    search_fields = ("scope",)
    ordering = ("dataset", "scope")
