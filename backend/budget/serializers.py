from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import AnnualExpenseEntry, AnnualIncomeEntry
from .services import (
    normalize_currency_code,
    validate_annual_expense_taxonomy,
    validate_annual_income_taxonomy,
)


class AnnualEntryValidationMixin:
    def validate_currency(self, value: str):
        normalized = normalize_currency_code(value)
        if len(normalized) != 3:
            raise serializers.ValidationError("Moneda invalida. Usa codigos ISO de 3 letras.")
        return normalized

    def validate_amount_annual(self, value):
        if value <= 0:
            raise serializers.ValidationError("El importe anual debe ser mayor que cero.")
        return value

    def validate_fiscal_year(self, value: int):
        if value < 1900 or value > 3000:
            raise serializers.ValidationError("Ejercicio fiscal invalido.")
        return value

    def validate_term_end_year(self, value: int | None):
        if value is None:
            return value
        if value < 1900 or value > 3000:
            raise serializers.ValidationError("Ano fin del compromiso invalido.")
        return value


def income_type_from_time_profile(time_profile: str) -> str:
    return "one_off" if time_profile == AnnualIncomeEntry.TimeProfile.ONE_OFF else "recurrent"


def expense_type_from_time_profile(time_profile: str) -> str:
    return "one_off" if time_profile == AnnualExpenseEntry.TimeProfile.ONE_OFF else "recurrent"


def default_income_time_profile_from_income_type(income_type: str) -> str:
    return (
        AnnualIncomeEntry.TimeProfile.ONE_OFF
        if income_type == AnnualIncomeEntry.IncomeType.ONE_OFF
        else AnnualIncomeEntry.TimeProfile.STRUCTURAL_RECURRENT
    )


def default_expense_time_profile_from_expense_type(expense_type: str) -> str:
    return (
        AnnualExpenseEntry.TimeProfile.ONE_OFF
        if expense_type == AnnualExpenseEntry.ExpenseType.ONE_OFF
        else AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT
    )


def default_income_cashflow_role_from_category(category: str) -> str:
    normalized = (category or "").strip()
    if normalized == AnnualIncomeEntry.Category.CAPITAL_GAINS:
        return AnnualIncomeEntry.CashflowRole.ASSET_SALE
    if normalized in {
        AnnualIncomeEntry.Category.TRANSFERS_SUPPORT,
        AnnualIncomeEntry.Category.PUBLIC_BENEFITS,
    }:
        return AnnualIncomeEntry.CashflowRole.TRANSFER
    if normalized == AnnualIncomeEntry.Category.OTHER_INCOME:
        return AnnualIncomeEntry.CashflowRole.OTHER
    return AnnualIncomeEntry.CashflowRole.OPERATING


def default_expense_cashflow_role_from_category(category: str, subcategory: str) -> str:
    normalized_category = (category or "").strip()
    normalized_subcategory = (subcategory or "").strip()
    if normalized_category == AnnualExpenseEntry.Category.SAVINGS_ALLOCATION:
        return AnnualExpenseEntry.CashflowRole.SAVINGS
    if normalized_category == AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS:
        return AnnualExpenseEntry.CashflowRole.INVESTMENT
    if normalized_category in {
        AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS,
        AnnualExpenseEntry.Category.TANGIBLE_ASSETS,
    }:
        return (
            AnnualExpenseEntry.CashflowRole.TAX_FEE
            if normalized_subcategory in {"real_estate_fees_taxes"}
            else AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE
        )
    return AnnualExpenseEntry.CashflowRole.OPERATING


class AnnualIncomeEntrySerializer(AnnualEntryValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = AnnualIncomeEntry
        fields = [
            "id",
            "name",
            "category",
            "subcategory",
            "owner_name",
            "income_type",
            "time_profile",
            "cashflow_role",
            "event_group",
            "term_end_year",
            "amount_annual",
            "fiscal_year",
            "currency",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        category = attrs.get("category") or getattr(self.instance, "category", "")
        subcategory = attrs.get("subcategory") or getattr(self.instance, "subcategory", "")
        income_type = attrs.get("income_type") or getattr(
            self.instance, "income_type", AnnualIncomeEntry.IncomeType.RECURRENT
        )
        try:
            validate_annual_income_taxonomy(category=category, subcategory=subcategory)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        if "time_profile" not in attrs:
            attrs["time_profile"] = default_income_time_profile_from_income_type(income_type)
        if "cashflow_role" not in attrs:
            attrs["cashflow_role"] = default_income_cashflow_role_from_category(category)
        attrs["income_type"] = income_type_from_time_profile(attrs["time_profile"])

        fiscal_year = attrs.get("fiscal_year") or getattr(self.instance, "fiscal_year", None)
        term_end_year = attrs.get("term_end_year")
        if "term_end_year" not in attrs and self.instance is not None:
            term_end_year = self.instance.term_end_year
        if (
            attrs["time_profile"] == AnnualIncomeEntry.TimeProfile.TERM_RECURRENT
            and term_end_year is None
        ):
            raise serializers.ValidationError(
                {"term_end_year": "El ano fin es obligatorio para ingresos recurrentes temporales."}
            )
        if term_end_year is not None and fiscal_year is not None and term_end_year < fiscal_year:
            raise serializers.ValidationError(
                {"term_end_year": "El ano fin no puede ser anterior al ejercicio fiscal."}
            )
        if attrs["time_profile"] != AnnualIncomeEntry.TimeProfile.TERM_RECURRENT:
            attrs["term_end_year"] = None
        return attrs


class AnnualExpenseEntrySerializer(AnnualEntryValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = AnnualExpenseEntry
        fields = [
            "id",
            "source_liability_id",
            "is_system_generated",
            "name",
            "category",
            "subcategory",
            "owner_name",
            "expense_type",
            "time_profile",
            "cashflow_role",
            "event_group",
            "term_end_year",
            "amount_annual",
            "fiscal_year",
            "currency",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "source_liability_id",
            "is_system_generated",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        category = attrs.get("category") or getattr(self.instance, "category", "")
        subcategory = attrs.get("subcategory") or getattr(self.instance, "subcategory", "")
        expense_type = attrs.get("expense_type") or getattr(
            self.instance, "expense_type", AnnualExpenseEntry.ExpenseType.RECURRENT
        )
        try:
            validate_annual_expense_taxonomy(category=category, subcategory=subcategory)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        if "time_profile" not in attrs:
            attrs["time_profile"] = default_expense_time_profile_from_expense_type(expense_type)
        if "cashflow_role" not in attrs:
            attrs["cashflow_role"] = default_expense_cashflow_role_from_category(
                category, subcategory
            )
        attrs["expense_type"] = expense_type_from_time_profile(attrs["time_profile"])

        fiscal_year = attrs.get("fiscal_year") or getattr(self.instance, "fiscal_year", None)
        term_end_year = attrs.get("term_end_year")
        if "term_end_year" not in attrs and self.instance is not None:
            term_end_year = self.instance.term_end_year
        if (
            attrs["time_profile"] == AnnualExpenseEntry.TimeProfile.TERM_RECURRENT
            and term_end_year is None
        ):
            raise serializers.ValidationError(
                {"term_end_year": "El ano fin es obligatorio para gastos recurrentes temporales."}
            )
        if term_end_year is not None and fiscal_year is not None and term_end_year < fiscal_year:
            raise serializers.ValidationError(
                {"term_end_year": "El ano fin no puede ser anterior al ejercicio fiscal."}
            )
        if attrs["time_profile"] != AnnualExpenseEntry.TimeProfile.TERM_RECURRENT:
            attrs["term_end_year"] = None
        return attrs
