from rest_framework import serializers

from .models import UserSettings
from core.models import InflationIndex


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = [
            "base_currency",
            "inflation_region",
        ]

    def validate_inflation_region(self, value: str) -> str:
        allowed = {row["code"] for row in InflationIndex.supported_regions()}
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise serializers.ValidationError("Region IPC no soportada.")
        return normalized
