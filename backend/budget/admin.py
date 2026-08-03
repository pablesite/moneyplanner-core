from django.contrib import admin

from .models import (
    AnnualExpenseEntry,
    AnnualIncomeEntry,
    SettlementAccount,
    SettlementOpeningAdjustment,
    SettlementOpeningBalance,
    SettlementProfile,
)


@admin.register(AnnualIncomeEntry)
class AnnualIncomeEntryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "name",
        "category",
        "subcategory",
        "time_profile",
        "cashflow_role",
        "amount_annual",
        "currency",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "category",
        "subcategory",
        "income_type",
        "time_profile",
        "cashflow_role",
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


@admin.register(AnnualExpenseEntry)
class AnnualExpenseEntryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "name",
        "category",
        "subcategory",
        "time_profile",
        "cashflow_role",
        "amount_annual",
        "currency",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "category",
        "subcategory",
        "expense_type",
        "time_profile",
        "cashflow_role",
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


admin.site.register(SettlementProfile)
admin.site.register(SettlementAccount)
admin.site.register(SettlementOpeningBalance)
admin.site.register(SettlementOpeningAdjustment)
