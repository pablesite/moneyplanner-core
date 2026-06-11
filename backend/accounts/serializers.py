from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import UserSettings
from core.models import InflationIndex

User = get_user_model()


class UserRegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Este nombre de usuario ya existe.")
        return value

    def validate(self, data: dict) -> dict:
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Las contraseñas no coinciden."})
        validate_password(data["password"])
        return data

    def create(self, validated_data: dict):
        return User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
        )


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


class ExternalIdentitySerializer(serializers.Serializer):
    provider = serializers.CharField()
    external_user_id = serializers.CharField()


class CoreAdminUserSerializer(serializers.ModelSerializer):
    external_identities = serializers.SerializerMethodField()
    origin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "is_active",
            "is_staff",
            "origin",
            "external_identities",
        ]

    def get_external_identities(self, obj) -> list[dict[str, str]]:
        identities = getattr(obj, "prefetched_external_identities", None)
        if identities is None:
            identities = obj.external_identities.all()
        return ExternalIdentitySerializer(identities, many=True).data

    def get_origin(self, obj) -> str:
        identities = getattr(obj, "prefetched_external_identities", None)
        if identities is None:
            identities = obj.external_identities.all()
        return "saas_bootstrap" if any(identities) else "core_native"
