from decimal import Decimal
from rest_framework import serializers

from .models import Asset, Liability, NetWorthSnapshot


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ["id", "name", "category", "amount", "notes", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        # Forzamos usuario desde request
        request = self.context["request"]
        return Asset.objects.create(user=request.user, **validated_data)


class LiabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Liability
        fields = ["id", "name", "category", "amount", "notes", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context["request"]
        return Liability.objects.create(user=request.user, **validated_data)


class NetWorthSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetWorthSnapshot
        fields = [
            "id",
            "snapshot_date",
            "total_assets",
            "total_liabilities",
            "net_worth",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        # Si no viene net_worth lo calculamos; si viene, validamos coherencia
        total_assets = attrs.get("total_assets")
        total_liabilities = attrs.get("total_liabilities")
        net_worth = attrs.get("net_worth")

        if total_assets is not None and total_liabilities is not None:
            computed = (total_assets or Decimal("0")) - (total_liabilities or Decimal("0"))
            if net_worth is None:
                attrs["net_worth"] = computed
            else:
                if net_worth != computed:
                    raise serializers.ValidationError(
                        {"net_worth": "net_worth debe ser total_assets - total_liabilities"}
                    )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        return NetWorthSnapshot.objects.create(user=request.user, **validated_data)
