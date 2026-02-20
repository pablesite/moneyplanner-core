from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import AnnualIncomeEntry, FxRate, InflationIndex
from .services import (
    normalize_currency_code,
    validate_annual_income_taxonomy,
    validate_fx_currency_pair,
    validate_inflation_period_start,
)


class FxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FxRate
        fields = ["id", "rate_date", "from_currency", "to_currency", "rate", "updated_at"]
        read_only_fields = ["id", "updated_at"]

    def validate_from_currency(self, value: str):
        return normalize_currency_code(value)

    def validate_to_currency(self, value: str):
        return normalize_currency_code(value)

    def validate(self, attrs):
        from_c = attrs.get("from_currency") or getattr(self.instance, "from_currency", "")
        to_c = attrs.get("to_currency") or getattr(self.instance, "to_currency", "")
        try:
            validate_fx_currency_pair(from_currency=from_c, to_currency=to_c)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs


class InflationIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = InflationIndex
        fields = ["id", "region", "period", "index", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_period(self, value):
        try:
            validate_inflation_period_start(period=value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


class AnnualIncomeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnualIncomeEntry
        fields = [
            "id",
            "name",
            "category",
            "subcategory",
            "owner_name",
            "income_type",
            "amount_annual",
            "currency",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_currency(self, value: str):
        normalized = normalize_currency_code(value)
        if len(normalized) != 3:
            raise serializers.ValidationError("Moneda invalida. Usa codigos ISO de 3 letras.")
        return normalized

    def validate_amount_annual(self, value):
        if value <= 0:
            raise serializers.ValidationError("El importe anual debe ser mayor que cero.")
        return value

    def validate(self, attrs):
        category = attrs.get("category") or getattr(self.instance, "category", "")
        subcategory = attrs.get("subcategory") or getattr(self.instance, "subcategory", "")
        try:
            validate_annual_income_taxonomy(category=category, subcategory=subcategory)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs
