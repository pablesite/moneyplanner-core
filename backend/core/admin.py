from django.contrib import admin

from .models import FxRate


@admin.register(FxRate)
class FxRateAdmin(admin.ModelAdmin):
    list_display = ("from_currency", "to_currency", "rate", "updated_at")
    list_filter = ("from_currency", "to_currency")
    search_fields = ("from_currency", "to_currency")
    ordering = ("from_currency", "to_currency")
