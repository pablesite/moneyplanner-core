from django.contrib import admin

from .models import AnnualIncomeEntry


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
