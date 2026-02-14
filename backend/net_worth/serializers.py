from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from core.services import convert_currency

from .models import Asset, Liability, NetWorthSnapshot
from .services import (
    create_asset_for_user,
    create_liability_for_user,
    create_snapshot_for_user,
    infer_liability_is_asset_backed,
    validate_asset_payload,
    validate_liability_payload,
)


class EmptySerializer(serializers.Serializer):
    pass


class AssetSerializer(serializers.ModelSerializer):
    amount_base = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            "id",
            "name",
            "category",
            "subcategory",
            "tracking_mode",
            "accounting_account_id",
            "currency",
            "amount",
            "amount_base",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        tracking_mode = attrs.get("tracking_mode", getattr(self.instance, "tracking_mode", None))
        accounting_account_id = attrs.get(
            "accounting_account_id", getattr(self.instance, "accounting_account_id", None)
        )
        category = attrs.get("category", getattr(self.instance, "category", None))
        subcategory = attrs.get("subcategory", getattr(self.instance, "subcategory", None))
        validate_asset_payload(
            tracking_mode=tracking_mode,
            accounting_account_id=accounting_account_id,
            category=category,
            subcategory=subcategory,
        )
        return attrs

    def get_amount_base(self, obj):
        base_currency = self.context.get("base_currency")
        if not base_currency:
            return None
        try:
            today = timezone.localdate()
            return str(convert_currency(obj.amount, obj.currency, base_currency, date=today))
        except Exception:
            return None

    def create(self, validated_data):
        request = self.context["request"]
        return create_asset_for_user(user=request.user, validated_data=validated_data)


class NetWorthSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetWorthSnapshot
        fields = [
            "id",
            "snapshot_date",
            "base_currency",
            "total_assets",
            "total_liabilities",
            "net_worth",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        total_assets = attrs.get("total_assets")
        total_liabilities = attrs.get("total_liabilities")
        net_worth = attrs.get("net_worth")

        if total_assets is not None and total_liabilities is not None:
            computed = (total_assets or Decimal("0")) - (total_liabilities or Decimal("0"))
            if net_worth is None:
                attrs["net_worth"] = computed
            elif net_worth != computed:
                raise serializers.ValidationError(
                    {"net_worth": "net_worth debe ser total_assets - total_liabilities"}
                )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        return create_snapshot_for_user(user=request.user, validated_data=validated_data)


class AssetMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ["id", "name", "category", "subcategory"]


class LiabilitySerializer(serializers.ModelSerializer):
    amount_base = serializers.SerializerMethodField()

    financed_asset_id = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects.none(),
        source="financed_asset",
        required=False,
        allow_null=True,
        write_only=True,
    )

    financed_asset_ref = serializers.IntegerField(source="financed_asset_id", read_only=True)
    financed_asset_detail = AssetMiniSerializer(source="financed_asset", read_only=True)

    class Meta:
        model = Liability
        fields = [
            "id",
            "name",
            "category",
            "tracking_mode",
            "accounting_account_id",
            "currency",
            "amount",
            "amount_base",
            "is_active",
            "is_asset_backed",
            "financed_asset_id",
            "financed_asset_ref",
            "financed_asset_detail",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            self.fields["financed_asset_id"].queryset = Asset.objects.filter(
                user=request.user,
                is_active=True,
            )

    def validate(self, attrs):
        tracking_mode = attrs.get("tracking_mode", getattr(self.instance, "tracking_mode", None))
        accounting_account_id = attrs.get(
            "accounting_account_id", getattr(self.instance, "accounting_account_id", None)
        )
        validate_liability_payload(
            tracking_mode=tracking_mode,
            accounting_account_id=accounting_account_id,
        )

        financed_asset = attrs.get("financed_asset", getattr(self.instance, "financed_asset", None))
        attrs["is_asset_backed"] = infer_liability_is_asset_backed(financed_asset=financed_asset)
        return attrs

    def get_amount_base(self, obj):
        base_currency = self.context.get("base_currency")
        if not base_currency:
            return None
        try:
            today = timezone.localdate()
            return str(convert_currency(obj.amount, obj.currency, base_currency, date=today))
        except Exception:
            return None

    def create(self, validated_data):
        request = self.context["request"]
        return create_liability_for_user(user=request.user, validated_data=validated_data)
