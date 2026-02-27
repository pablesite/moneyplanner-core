from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from typing import cast

from .models import (
    AnnualExpenseEntry,
    AnnualExpenseMonthlyCheckin,
    AnnualIncomeEntry,
    AnnualIncomeMonthlyCheckin,
)
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

    def validate_target_month(self, value: int | None):
        if value is None:
            return value
        if value < 1 or value > 12:
            raise serializers.ValidationError("Mes objetivo invalido (1-12).")
        return value


def income_type_from_time_profile(time_profile: str) -> str:
    return "one_off" if time_profile == AnnualIncomeEntry.TimeProfile.ONE_OFF else "recurrent"


def expense_type_from_time_profile(time_profile: str) -> str:
    return "one_off" if time_profile == AnnualExpenseEntry.TimeProfile.ONE_OFF else "recurrent"


def default_income_time_profile_from_income_type(income_type: str) -> str:
    return (
        cast(str, AnnualIncomeEntry.TimeProfile.ONE_OFF)
        if income_type == AnnualIncomeEntry.IncomeType.ONE_OFF
        else cast(str, AnnualIncomeEntry.TimeProfile.STRUCTURAL_RECURRENT)
    )


def default_expense_time_profile_from_expense_type(expense_type: str) -> str:
    return (
        cast(str, AnnualExpenseEntry.TimeProfile.ONE_OFF)
        if expense_type == AnnualExpenseEntry.ExpenseType.ONE_OFF
        else cast(str, AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT)
    )


def default_income_cashflow_role_from_category(category: str) -> str:
    normalized = (category or "").strip()
    if normalized == AnnualIncomeEntry.Category.CAPITAL_GAINS:
        return cast(str, AnnualIncomeEntry.CashflowRole.ASSET_SALE)
    if normalized in {
        AnnualIncomeEntry.Category.TRANSFERS_SUPPORT,
        AnnualIncomeEntry.Category.PUBLIC_BENEFITS,
    }:
        return cast(str, AnnualIncomeEntry.CashflowRole.TRANSFER)
    if normalized == AnnualIncomeEntry.Category.OTHER_INCOME:
        return cast(str, AnnualIncomeEntry.CashflowRole.OTHER)
    return cast(str, AnnualIncomeEntry.CashflowRole.OPERATING)


def default_expense_cashflow_role_from_category(category: str, subcategory: str) -> str:
    normalized_category = (category or "").strip()
    normalized_subcategory = (subcategory or "").strip()
    if normalized_category == AnnualExpenseEntry.Category.SAVINGS_ALLOCATION:
        return cast(str, AnnualExpenseEntry.CashflowRole.SAVINGS)
    if normalized_category == AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS:
        return cast(str, AnnualExpenseEntry.CashflowRole.INVESTMENT)
    if normalized_category in {
        AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS,
        AnnualExpenseEntry.Category.TANGIBLE_ASSETS,
    }:
        return (
            cast(str, AnnualExpenseEntry.CashflowRole.TAX_FEE)
            if normalized_subcategory in {"real_estate_fees_taxes"}
            else cast(str, AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE)
        )
    return cast(str, AnnualExpenseEntry.CashflowRole.OPERATING)


EXPENSE_STRUCTURAL_ALLOWED_CASHFLOW_ROLES: set[str] = {
    cast(str, AnnualExpenseEntry.CashflowRole.OPERATING),
    cast(str, AnnualExpenseEntry.CashflowRole.SAVINGS),
    cast(str, AnnualExpenseEntry.CashflowRole.INVESTMENT),
    cast(str, AnnualExpenseEntry.CashflowRole.TAX_FEE),
    cast(str, AnnualExpenseEntry.CashflowRole.OTHER),
}

EXPENSE_ONE_OFF_ALLOWED_CASHFLOW_ROLES: set[str] = {
    cast(str, AnnualExpenseEntry.CashflowRole.SAVINGS),
    cast(str, AnnualExpenseEntry.CashflowRole.INVESTMENT),
    cast(str, AnnualExpenseEntry.CashflowRole.TAX_FEE),
    cast(str, AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE),
    cast(str, AnnualExpenseEntry.CashflowRole.TRANSFER),
    cast(str, AnnualExpenseEntry.CashflowRole.OTHER),
}


def normalize_expense_cashflow_role_for_time_profile(
    *, time_profile: str, cashflow_role: str
) -> str:
    if time_profile == AnnualExpenseEntry.TimeProfile.TERM_RECURRENT:
        return cast(str, AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT)
    if time_profile == AnnualExpenseEntry.TimeProfile.ONE_OFF:
        return (
            cashflow_role
            if cashflow_role in EXPENSE_ONE_OFF_ALLOWED_CASHFLOW_ROLES
            else cast(str, AnnualExpenseEntry.CashflowRole.OTHER)
        )
    return (
        cashflow_role
        if cashflow_role in EXPENSE_STRUCTURAL_ALLOWED_CASHFLOW_ROLES
        else cast(str, AnnualExpenseEntry.CashflowRole.OPERATING)
    )


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
            "target_month",
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
        attrs["cashflow_role"] = normalize_expense_cashflow_role_for_time_profile(
            time_profile=attrs["time_profile"],
            cashflow_role=attrs["cashflow_role"],
        )

        fiscal_year = attrs.get("fiscal_year") or getattr(self.instance, "fiscal_year", None)
        target_month = attrs.get("target_month")
        if "target_month" not in attrs and self.instance is not None:
            target_month = self.instance.target_month
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
        if attrs["time_profile"] == AnnualExpenseEntry.TimeProfile.ONE_OFF and target_month is None:
            raise serializers.ValidationError(
                {"target_month": "El mes objetivo es obligatorio para gastos puntuales."}
            )
        if attrs["time_profile"] != AnnualExpenseEntry.TimeProfile.TERM_RECURRENT:
            attrs["term_end_year"] = None
        if attrs["time_profile"] != AnnualExpenseEntry.TimeProfile.ONE_OFF:
            attrs["target_month"] = None
        return attrs


class AnnualExpenseMonthlyCheckinSerializer(
    AnnualEntryValidationMixin, serializers.ModelSerializer
):
    annual_expense_entry_id = serializers.PrimaryKeyRelatedField(
        source="annual_expense_entry",
        queryset=AnnualExpenseEntry.objects.all(),
    )

    class Meta:
        model = AnnualExpenseMonthlyCheckin
        fields = [
            "id",
            "annual_expense_entry_id",
            "fiscal_year",
            "month",
            "status",
            "executed_amount",
            "note",
            "confirmed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "confirmed_at", "created_at", "updated_at"]

    def validate_executed_amount(self, value):
        if value is None:
            return value
        if value < 0:
            raise serializers.ValidationError("El importe ejecutado no puede ser negativo.")
        return value

    def validate_month(self, value: int):
        if value < 1 or value > 12:
            raise serializers.ValidationError("Mes invalido (1-12).")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        entry = attrs.get("annual_expense_entry") or getattr(
            self.instance, "annual_expense_entry", None
        )
        status_value = attrs.get("status") or getattr(self.instance, "status", None)
        executed_amount = attrs.get("executed_amount", serializers.empty)
        fiscal_year = attrs.get("fiscal_year") or getattr(self.instance, "fiscal_year", None)
        month = attrs.get("month") or getattr(self.instance, "month", None)

        if entry is None:
            raise serializers.ValidationError(
                {"annual_expense_entry_id": "Entrada de gasto requerida."}
            )
        if user is not None and entry.user_id != user.id:
            raise serializers.ValidationError(
                {
                    "annual_expense_entry_id": "La entrada de gasto no pertenece al usuario autenticado."
                }
            )
        if fiscal_year is not None and entry.fiscal_year != fiscal_year:
            raise serializers.ValidationError(
                {
                    "fiscal_year": "El ejercicio del check-in debe coincidir con el ejercicio del gasto anual."
                }
            )
        if (
            entry.time_profile == AnnualExpenseEntry.TimeProfile.ONE_OFF
            and entry.target_month is not None
            and month is not None
            and month != entry.target_month
        ):
            raise serializers.ValidationError(
                {"month": "Los gastos puntuales solo admiten check-in en su mes objetivo."}
            )
        if status_value == AnnualExpenseMonthlyCheckin.Status.SKIPPED:
            attrs["executed_amount"] = None
        elif executed_amount is serializers.empty and self.instance is None:
            attrs["executed_amount"] = None
        return attrs


class AnnualIncomeMonthlyCheckinSerializer(AnnualEntryValidationMixin, serializers.ModelSerializer):
    annual_income_entry_id = serializers.PrimaryKeyRelatedField(
        source="annual_income_entry",
        queryset=AnnualIncomeEntry.objects.all(),
    )

    class Meta:
        model = AnnualIncomeMonthlyCheckin
        fields = [
            "id",
            "annual_income_entry_id",
            "fiscal_year",
            "month",
            "status",
            "executed_amount",
            "note",
            "confirmed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "confirmed_at", "created_at", "updated_at"]

    def validate_executed_amount(self, value):
        if value is None:
            return value
        if value < 0:
            raise serializers.ValidationError("El importe ejecutado no puede ser negativo.")
        return value

    def validate_month(self, value: int):
        if value < 1 or value > 12:
            raise serializers.ValidationError("Mes invalido (1-12).")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        entry = attrs.get("annual_income_entry") or getattr(
            self.instance, "annual_income_entry", None
        )
        status_value = attrs.get("status") or getattr(self.instance, "status", None)
        executed_amount = attrs.get("executed_amount", serializers.empty)
        fiscal_year = attrs.get("fiscal_year") or getattr(self.instance, "fiscal_year", None)

        if entry is None:
            raise serializers.ValidationError(
                {"annual_income_entry_id": "Entrada de ingreso requerida."}
            )
        if user is not None and entry.user_id != user.id:
            raise serializers.ValidationError(
                {
                    "annual_income_entry_id": "La entrada de ingreso no pertenece al usuario autenticado."
                }
            )
        if fiscal_year is not None and entry.fiscal_year != fiscal_year:
            raise serializers.ValidationError(
                {
                    "fiscal_year": "El ejercicio del check-in debe coincidir con el ejercicio del ingreso anual."
                }
            )
        # v1: one-off incomes are excluded from monthly summary until target_month exists in AnnualIncomeEntry.
        if entry.time_profile == AnnualIncomeEntry.TimeProfile.ONE_OFF:
            raise serializers.ValidationError(
                {
                    "annual_income_entry_id": "Los ingresos puntuales aun no soportan check-in mensual (falta mes objetivo)."
                }
            )
        if status_value == AnnualIncomeMonthlyCheckin.Status.SKIPPED:
            attrs["executed_amount"] = None
        elif executed_amount is serializers.empty and self.instance is None:
            attrs["executed_amount"] = None
        return attrs
