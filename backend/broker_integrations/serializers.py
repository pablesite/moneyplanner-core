from __future__ import annotations

from rest_framework import serializers

from memberships.models import Ownership

from .models import BotNetResult, BrokerCredential, BrokerSyncRun, BrokerTrade, IncomeEvent
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


class BrokerSyncRunListQuerySerializer(serializers.Serializer):
    credential_id = serializers.IntegerField(required=False, min_value=1)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)


class BrokerTradeListQuerySerializer(serializers.Serializer):
    credential_id = serializers.IntegerField(required=False, min_value=1)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)
    source = serializers.ChoiceField(choices=BrokerTrade.Source.choices, required=False)
    symbol = serializers.CharField(required=False, max_length=20)
    side = serializers.ChoiceField(choices=BrokerTrade.Side.choices, required=False)
    bot_id = serializers.CharField(required=False, max_length=100)
    sync_run = serializers.IntegerField(required=False, min_value=1)


class BrokerIncomeEventListQuerySerializer(serializers.Serializer):
    credential_id = serializers.IntegerField(required=False, min_value=1)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)
    source = serializers.ChoiceField(choices=IncomeEvent.Source.choices, required=False)
    sync_run = serializers.IntegerField(required=False, min_value=1)


class BrokerBotResultListQuerySerializer(serializers.Serializer):
    credential_id = serializers.IntegerField(required=False, min_value=1)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)
    bot_id = serializers.CharField(required=False, max_length=100)
    sync_run = serializers.IntegerField(required=False, min_value=1)


class BrokerTradeSerializer(serializers.ModelSerializer):
    bot_id = serializers.CharField(source="bot.bot_id", read_only=True)

    class Meta:
        model = BrokerTrade
        fields = [
            "id",
            "credential_id",
            "bot_id",
            "source",
            "trade_id",
            "symbol",
            "base_asset",
            "quote_asset",
            "side",
            "price",
            "quantity",
            "fee",
            "fee_asset",
            "timestamp",
        ]


class IncomeEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeEvent
        fields = [
            "id",
            "credential_id",
            "source",
            "income_type",
            "asset",
            "amount",
            "timestamp",
            "description",
        ]


class BotNetResultSerializer(serializers.ModelSerializer):
    fill_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = BotNetResult
        fields = [
            "id",
            "credential_id",
            "bot_id",
            "bot_type",
            "label",
            "base_asset",
            "quote_asset",
            "realized_profit",
            "total_fee_base",
            "total_fee_quote",
            "period_start",
            "period_end",
            "synced_at",
            "fill_count",
        ]


class BrokerSyncRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrokerSyncRun
        fields = [
            "id",
            "credential_id",
            "year",
            "status",
            "started_at",
            "finished_at",
            "stats",
            "gaps",
            "new_trade_ids",
            "updated_trade_ids",
            "new_income_event_ids",
            "updated_income_event_ids",
            "new_bot_result_ids",
            "updated_bot_result_ids",
        ]
