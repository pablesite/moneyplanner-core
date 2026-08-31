from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import SettlementAccount, SettlementOpeningAdjustment


class SettlementAccountInputSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField(min_value=1)
    role = serializers.ChoiceField(choices=SettlementAccount.Role.choices)
    member_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    is_primary = serializers.BooleanField(default=False)
    accepted_physical_balance = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        required=False,
        allow_null=True,
        min_value=0,
    )


class SettlementOpeningAdjustmentInputSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField(min_value=1)
    member_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=20, decimal_places=8)
    kind = serializers.ChoiceField(
        choices=SettlementOpeningAdjustment.Kind.choices,
        default=SettlementOpeningAdjustment.Kind.MANUAL,
    )
    note = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")


class SettlementConfigurationWriteSerializer(serializers.Serializer):
    base_currency = serializers.CharField(min_length=3, max_length=3)
    accounts = SettlementAccountInputSerializer(many=True)
    opening_adjustments = SettlementOpeningAdjustmentInputSerializer(many=True, required=False)
    normalization_transaction_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )


class SettlementActivationSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    activation_date = serializers.DateField(required=False, write_only=True)

    def validate(self, attrs):
        if attrs.get("start_date") and attrs.get("activation_date"):
            raise serializers.ValidationError(
                "Usa start_date; activation_date se conserva solo por compatibilidad."
            )
        return attrs


class SettlementWalletBalanceInputSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField(min_value=1)
    accepted_physical_balance = serializers.DecimalField(
        max_digits=20, decimal_places=8, min_value=0
    )


class SettlementRebaselineSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    wallet_balances = SettlementWalletBalanceInputSerializer(many=True)
    opening_adjustments = SettlementOpeningAdjustmentInputSerializer(many=True, required=False)
    normalization_transaction_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )


class SettlementExecutionSerializer(serializers.Serializer):
    execution_date = serializers.DateField(default=timezone.localdate)
    amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        required=False,
        allow_null=True,
        min_value=Decimal("0.01"),
    )
    idempotency_key = serializers.CharField(
        max_length=128, required=False, allow_blank=True, default=""
    )


class SettlementReconciliationSerializer(serializers.Serializer):
    transaction_id = serializers.IntegerField(min_value=1)
