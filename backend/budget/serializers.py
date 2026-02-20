from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import AnnualIncomeEntry
from .services import normalize_currency_code, validate_annual_income_taxonomy


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
            "fiscal_year",
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

    def validate_fiscal_year(self, value: int):
        if value < 1900 or value > 3000:
            raise serializers.ValidationError("Ejercicio fiscal invalido.")
        return value

    def validate(self, attrs):
        category = attrs.get("category") or getattr(self.instance, "category", "")
        subcategory = attrs.get("subcategory") or getattr(self.instance, "subcategory", "")
        try:
            validate_annual_income_taxonomy(category=category, subcategory=subcategory)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs
