from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import FxRate, InflationIndex
from .services import (
    normalize_currency_code,
    validate_fx_currency_pair,
    validate_inflation_period_start,
)


class FxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FxRate
        fields = [
            "id",
            "rate_date",
            "from_currency",
            "to_currency",
            "rate",
            "last_synced_at",
            "updated_at",
        ]
        read_only_fields = ["id", "last_synced_at", "updated_at"]

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
        fields = ["id", "region", "period", "index", "last_synced_at", "created_at", "updated_at"]
        read_only_fields = ["id", "last_synced_at", "created_at", "updated_at"]

    def validate_period(self, value):
        try:
            validate_inflation_period_start(period=value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value
