from rest_framework import serializers

from .models import FxRate, InflationIndex


class FxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FxRate
        fields = ["id", "rate_date", "from_currency", "to_currency", "rate", "updated_at"]
        read_only_fields = ["id", "updated_at"]

    def validate_from_currency(self, value: str):
        return (value or "").upper().strip()

    def validate_to_currency(self, value: str):
        return (value or "").upper().strip()

    def validate(self, attrs):
        from_c = attrs.get("from_currency") or getattr(self.instance, "from_currency", "")
        to_c = attrs.get("to_currency") or getattr(self.instance, "to_currency", "")
        if len(from_c) != 3 or len(to_c) != 3:
            raise serializers.ValidationError("Moneda inválida. Usa códigos ISO de 3 letras.")
        return attrs


class InflationIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = InflationIndex
        fields = ["id", "region", "period", "index", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_period(self, value):
        if value.day != 1:
            raise serializers.ValidationError("El periodo debe ser el primer día del mes (YYYY-MM-01).")
        return value
