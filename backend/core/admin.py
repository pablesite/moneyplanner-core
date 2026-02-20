from django.contrib import admin

from .models import AnnualIncomeEntry, FxRate, InflationIndex


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


@admin.register(AnnualIncomeEntry)
class AnnualIncomeEntryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "name",
        "category",
        "subcategory",
        "amount_annual",
        "currency",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "category",
        "subcategory",
        "income_type",
        "currency",
        "is_active",
    )
    search_fields = (
        "name",
        "owner_name",
        "notes",
        "user__username",
    )
    ordering = ("-created_at",)
