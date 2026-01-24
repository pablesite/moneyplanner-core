from decimal import Decimal
from rest_framework import serializers

from .models import Asset, Liability, NetWorthSnapshot


class EmptySerializer(serializers.Serializer):
    pass


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = [
            "id",
            "name",
            "category",
            "tracking_mode",
            "accounting_account_id",
            "currency",
            "amount",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        tracking_mode = attrs.get("tracking_mode", getattr(self.instance, "tracking_mode", None))
        accounting_account_id = attrs.get("accounting_account_id", getattr(self.instance, "accounting_account_id", None))

        # si está en modo contabilidad, recomendamos tener referencia
        if tracking_mode == Asset.TrackingMode.ACCOUNTING and not accounting_account_id:
            raise serializers.ValidationError(
                {"accounting_account_id": "Requerido si tracking_mode=accounting (placeholder hasta que exista contabilidad)."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        return Asset.objects.create(user=request.user, **validated_data)


class LiabilitySerializer(serializers.ModelSerializer):
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
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        tracking_mode = attrs.get("tracking_mode", getattr(self.instance, "tracking_mode", None))
        accounting_account_id = attrs.get("accounting_account_id", getattr(self.instance, "accounting_account_id", None))

        if tracking_mode == Liability.TrackingMode.ACCOUNTING and not accounting_account_id:
            raise serializers.ValidationError(
                {"accounting_account_id": "Requerido si tracking_mode=accounting (placeholder hasta que exista contabilidad)."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        return Liability.objects.create(user=request.user, **validated_data)


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
            else:
                if net_worth != computed:
                    raise serializers.ValidationError({"net_worth": "net_worth debe ser total_assets - total_liabilities"})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        return NetWorthSnapshot.objects.create(user=request.user, **validated_data)
