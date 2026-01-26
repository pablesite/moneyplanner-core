from django.contrib import admin

from .models import FxRate


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
