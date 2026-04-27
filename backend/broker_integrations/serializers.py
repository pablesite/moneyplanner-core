from __future__ import annotations

from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from memberships.models import Ownership

from .models import (
    BotNetResult,
    BrokerCredential,
    BrokerSyncRun,
    BrokerTrade,
    IncomeEvent,
    ManualCostBasis,
)
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
    credential_id = serializers.PrimaryKeyRelatedField(
        source="credential",
        queryset=BrokerCredential.objects.all(),
        required=False,
        allow_null=True,
    )
    file_type = serializers.ChoiceField(
        choices=[
            "pionex_trading",
            "pionex_futures",
            "pionex_staking",
            "pionex_others",
            "pionex_dust",
            "pionex_deposit_withdraw",
            "binance_transactions",
            "binance_fiat_deposits",
            "binance_simple_earn_flexible",
            "binance_convert",
            "binance_recurring",
        ]
    )
    file = serializers.FileField()

    def validate(self, attrs: dict) -> dict:
        request = self.context["request"]
        broker = attrs.get("broker")
        credential = attrs.get("credential")
        if credential is None:
            return attrs
        if credential.user_id != request.user.id:
            raise serializers.ValidationError(
                {"credential_id": "La credencial no pertenece al usuario autenticado."}
            )
        if credential.broker != broker:
            raise serializers.ValidationError(
                {"credential_id": "La credencial no corresponde al broker seleccionado."}
            )
        return attrs


class BrokerFiscalReportQuerySerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100, required=False)
    ownership_id = serializers.PrimaryKeyRelatedField(
        source="ownership",
        queryset=Ownership.objects.all(),
        required=False,
        allow_null=True,
    )


class BrokerFiscalReportExportQuerySerializer(BrokerFiscalReportQuerySerializer):
    format = serializers.ChoiceField(choices=["csv", "pdf"], required=False, default="csv")


class BrokerSyncRunListQuerySerializer(serializers.Serializer):
    credential_id = serializers.IntegerField(required=False, min_value=1)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)


class BrokerTradeListQuerySerializer(serializers.Serializer):
    credential_id = serializers.IntegerField(required=False, min_value=1)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)
    source = serializers.ChoiceField(choices=BrokerTrade.Source.choices, required=False)
    symbol = serializers.CharField(required=False, max_length=20)
    tax_id = serializers.CharField(required=False, max_length=100)
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


class ManualCostBasisQuerySerializer(serializers.Serializer):
    asset = serializers.CharField(required=False, max_length=10)


class ManualCostBasisSerializer(serializers.ModelSerializer):
    ownership_id = serializers.PrimaryKeyRelatedField(
        source="ownership",
        queryset=Ownership.objects.all(),
        required=False,
    )

    class Meta:
        model = ManualCostBasis
        fields = [
            "id",
            "ownership_id",
            "asset",
            "quantity",
            "quantity_remaining",
            "acquired_at",
            "cost_eur",
            "exchange_origin",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "quantity_remaining", "created_at"]

    def validate_asset(self, value: str) -> str:
        return value.strip().upper()

    def validate_ownership_id(self, ownership: Ownership) -> Ownership:
        request = self.context["request"]
        if ownership.user_id != request.user.id:
            raise serializers.ValidationError("La ownership no pertenece al usuario autenticado.")
        return ownership

    def create(self, validated_data: dict) -> ManualCostBasis:
        request = self.context["request"]
        ownership = validated_data.get("ownership")
        if ownership is None:
            credential = (
                BrokerCredential.objects.filter(user=request.user)
                .select_related("ownership")
                .order_by("id")
                .first()
            )
            if credential is None:
                raise serializers.ValidationError(
                    {"ownership_id": "No hay ownership disponible para el usuario autenticado."}
                )
            validated_data["ownership"] = credential.ownership
        validated_data["quantity_remaining"] = validated_data["quantity"]
        return super().create(validated_data)


class BrokerTradeSerializer(serializers.ModelSerializer):
    bot_id = serializers.CharField(source="bot.bot_id", read_only=True)
    tax_id = serializers.SerializerMethodField()

    @staticmethod
    def get_tax_id(obj: BrokerTrade) -> str:
        raw = obj.raw if isinstance(obj.raw, dict) else {}
        return str(raw.get("tax_id") or "").strip()

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
            "price_eur",
            "quantity",
            "fee",
            "fee_eur",
            "fee_asset",
            "tax_id",
            "eur_rate_source",
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
    bot_profit_quote = serializers.SerializerMethodField()
    grid_profit = serializers.SerializerMethodField()
    total_profit_quote = serializers.SerializerMethodField()

    @staticmethod
    def _decimal_from_raw(value) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def _bot_raw_data(obj: BotNetResult) -> dict:
        raw = obj.raw if isinstance(obj.raw, dict) else {}
        nested = raw.get("buOrderData")
        return nested if isinstance(nested, dict) else raw

    def get_grid_profit(self, obj: BotNetResult) -> str:
        raw = self._bot_raw_data(obj)
        root_raw = obj.raw if isinstance(obj.raw, dict) else {}
        grid_profit = self._decimal_from_raw(raw.get("gridProfit"))
        if grid_profit is None:
            grid_profit = self._decimal_from_raw(root_raw.get("gridProfit"))
        if grid_profit is not None:
            return format(grid_profit, "f")
        return format(obj.realized_profit, "f")

    def get_bot_profit_quote(self, obj: BotNetResult) -> str:
        raw = self._bot_raw_data(obj)
        root_raw = obj.raw if isinstance(obj.raw, dict) else {}
        bot_type = str(obj.bot_type or "").strip().lower()
        if bot_type == "smart_copy":
            profit = self._decimal_from_raw(raw.get("profit"))
            if profit is None:
                profit = self._decimal_from_raw(root_raw.get("profit"))
            if profit is not None:
                return format(profit, "f")
        return self.get_grid_profit(obj)

    def get_total_profit_quote(self, obj: BotNetResult) -> str | None:
        raw = self._bot_raw_data(obj)
        root_raw = obj.raw if isinstance(obj.raw, dict) else {}
        bot_type = str(obj.bot_type or "").strip().lower()
        if bot_type == "smart_copy":
            profit = self._decimal_from_raw(raw.get("profit"))
            if profit is None:
                profit = self._decimal_from_raw(root_raw.get("profit"))
            if profit is not None:
                return format(profit, "f")
            quote_amount = self._decimal_from_raw(raw.get("currentQuoteAmount"))
            invested_quote = self._decimal_from_raw(raw.get("quoteTotalInvestment"))
            if quote_amount is not None and invested_quote is not None:
                return format(quote_amount - invested_quote, "f")
            return None
        quote_amount = self._decimal_from_raw(raw.get("quoteAmount"))
        base_amount = self._decimal_from_raw(raw.get("baseAmount"))
        invested_quote = self._decimal_from_raw(raw.get("quoteTotalInvestment"))
        closed_price = self._decimal_from_raw(raw.get("closedPrice"))
        open_price = self._decimal_from_raw(raw.get("openPrice"))

        if quote_amount is None or base_amount is None or invested_quote is None:
            return None

        mark_price = None
        if closed_price is not None and closed_price > 0:
            mark_price = closed_price
        elif open_price is not None and open_price > 0:
            mark_price = open_price
        if mark_price is None:
            return None

        total_profit = quote_amount + (base_amount * mark_price) - invested_quote
        return format(total_profit, "f")

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
            "bot_profit_quote",
            "grid_profit",
            "total_profit_quote",
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
