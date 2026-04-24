from __future__ import annotations

from rest_framework import serializers

from memberships.models import Ownership

from .models import BrokerCredential
from .services.encryption import encrypt


class BrokerCredentialSerializer(serializers.ModelSerializer):
    ownership_id = serializers.PrimaryKeyRelatedField(
        source="ownership", queryset=Ownership.objects.all()
    )
    api_secret = serializers.CharField(write_only=True, max_length=200)
    api_key_masked = serializers.SerializerMethodField(read_only=True)
    has_secret = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = BrokerCredential
        fields = [
            "id",
            "broker",
            "label",
            "ownership_id",
            "api_key",
            "api_secret",
            "api_key_masked",
            "has_secret",
            "last_sync_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "api_key_masked",
            "has_secret",
            "last_sync_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"api_key": {"write_only": True}}

    @staticmethod
    def _mask_api_key(value: str) -> str:
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"

    def get_api_key_masked(self, obj: BrokerCredential) -> str:
        return self._mask_api_key(obj.api_key)

    @staticmethod
    def get_has_secret(obj: BrokerCredential) -> bool:
        return bool(obj.api_secret_encrypted)

    def validate_ownership_id(self, ownership: Ownership) -> Ownership:
        request = self.context["request"]
        if ownership.user_id != request.user.id:
            raise serializers.ValidationError("La ownership no pertenece al usuario autenticado.")
        return ownership

    def create(self, validated_data: dict) -> BrokerCredential:
        request = self.context["request"]
        api_secret = validated_data.pop("api_secret")
        return BrokerCredential.objects.create(
            user=request.user,
            api_secret_encrypted=encrypt(api_secret),
            **validated_data,
        )


class BrokerSyncRequestSerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100, required=False)


class BrokerCsvImportSerializer(serializers.Serializer):
    broker = serializers.ChoiceField(choices=BrokerCredential.Broker.choices)
    file_type = serializers.ChoiceField(
        choices=[
            "pionex_trading",
            "pionex_futures",
            "pionex_staking",
            "pionex_others",
            "pionex_dust",
            "binance_transactions",
            "binance_convert",
            "binance_recurring",
        ]
    )
    file = serializers.FileField()


class BrokerFiscalReportQuerySerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100, required=False)
    ownership_id = serializers.PrimaryKeyRelatedField(
        source="ownership",
        queryset=Ownership.objects.all(),
        required=False,
        allow_null=True,
    )
