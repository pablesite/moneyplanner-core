from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Asset,
    Liability,
    ASSET_SUBCATEGORY_MAP,
    NetWorthSnapshot,
    FamilyMember,
    Ownership,
    OwnershipSplit,
)
from core.services import convert_currency


class EmptySerializer(serializers.Serializer):
    pass


class FamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        fields = ["id", "name", "role", "is_active"]


# ---------- Ownership (READ) ----------

class FamilyMemberMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        fields = ["id", "name", "role"]


class OwnershipSplitReadSerializer(serializers.ModelSerializer):
    member = FamilyMemberMiniSerializer(read_only=True)

    class Meta:
        model = OwnershipSplit
        fields = ["member", "percent"]


class OwnershipReadSerializer(serializers.ModelSerializer):
    member = FamilyMemberMiniSerializer(read_only=True)
    splits = OwnershipSplitReadSerializer(many=True, read_only=True)
    is_in_use = serializers.SerializerMethodField()

    class Meta:
        model = Ownership
        fields = ["id", "kind", "member", "splits", "is_in_use"]

    def get_is_in_use(self, obj):
        # usa related_name="assets"/"liabilities" que ya tienes
        return obj.assets.exists() or obj.liabilities.exists()
    





# ---------- Ownership (WRITE) ----------

class OwnershipSplitInputSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()
    percent = serializers.DecimalField(max_digits=5, decimal_places=2)

    def validate_percent(self, value):
        if value <= 0:
            raise serializers.ValidationError("El porcentaje debe ser > 0.")
        if value > 100:
            raise serializers.ValidationError("El porcentaje no puede ser > 100.")
        return value


class OwnershipWriteSerializer(serializers.ModelSerializer):
    splits = OwnershipSplitInputSerializer(many=True, required=False)

    class Meta:
        model = Ownership
        fields = ["id", "kind", "member", "splits"]

    def _get_user(self):
        req = self.context.get("request")
        return getattr(req, "user", None)

    def validate_member(self, value):
        user = self._get_user()
        if value is None or user is None:
            return value
        if value.user_id != user.id:
            raise serializers.ValidationError("El miembro no pertenece a este usuario.")
        return value

    def validate(self, attrs):
        user = self._get_user()

        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        member = attrs.get("member", getattr(self.instance, "member", None))

        splits = attrs.get("splits", None)
        if splits is None and self.instance is not None:
            splits = [{"member_id": s.member_id, "percent": s.percent} for s in self.instance.splits.all()]

        if kind == Ownership.Kind.INDIVIDUAL:
            if member is None:
                raise serializers.ValidationError({"member": "Obligatorio para titularidad individual."})
            if splits:
                raise serializers.ValidationError({"splits": "No se permiten splits en titularidad individual."})

        elif kind == Ownership.Kind.SHARED:
            if member is not None:
                raise serializers.ValidationError({"member": "Debe ser null en titularidad compartida."})
            if not splits:
                raise serializers.ValidationError({"splits": "Obligatorio indicar splits en titularidad compartida."})

            member_ids = [s["member_id"] for s in splits]

            if len(member_ids) != len(set(member_ids)):
                raise serializers.ValidationError({"splits": "No puede haber miembros duplicados en splits."})

            members = FamilyMember.objects.filter(id__in=member_ids)

            if members.count() != len(member_ids):
                raise serializers.ValidationError({"splits": "Algún member_id no existe."})

            if user is not None and members.exclude(user=user).exists():
                raise serializers.ValidationError({"splits": "Los miembros deben pertenecer a este usuario."})

            if members.exclude(role=FamilyMember.Role.ADULT).exists():
                raise serializers.ValidationError({"splits": "Solo se permiten adultos en compartidos (Lucas no cuenta)."})

            total = sum(Decimal(str(s["percent"])) for s in splits)
            if total != Decimal("100"):
                raise serializers.ValidationError({"splits": f"La suma de porcentajes debe ser 100. Ahora es {total}."})

        else:
            raise serializers.ValidationError({"kind": "Tipo de titularidad inválido."})

        return attrs

    def create(self, validated_data):
        splits = validated_data.pop("splits", [])
        user = self._get_user()

        ownership = Ownership.objects.create(user=user, **validated_data)

        if ownership.kind == Ownership.Kind.SHARED:
            OwnershipSplit.objects.bulk_create(
                [
                    OwnershipSplit(
                        ownership=ownership,
                        member_id=s["member_id"],
                        percent=s["percent"],
                    )
                    for s in splits
                ]
            )

        return ownership

    def update(self, instance, validated_data):
        splits = validated_data.pop("splits", None)

        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()

        if splits is not None:
            instance.splits.all().delete()
            if instance.kind == Ownership.Kind.SHARED:
                OwnershipSplit.objects.bulk_create(
                    [
                        OwnershipSplit(
                            ownership=instance,
                            member_id=s["member_id"],
                            percent=s["percent"],
                        )
                        for s in splits
                    ]
                )

        return instance


# ---------- Asset / Liability ----------

class AssetSerializer(serializers.ModelSerializer):
    amount_base = serializers.SerializerMethodField()
    # INPUTS
    ownership_id = serializers.PrimaryKeyRelatedField(
        queryset=Ownership.objects.none(),  # se setea en __init__
        source="ownership",
        required=False,
        allow_null=True,
        write_only=True,
    )
    ownership = OwnershipWriteSerializer(required=False, write_only=True)

    # OUTPUTS
    ownership_ref = serializers.IntegerField(source="ownership_id", read_only=True)
    ownership_detail = OwnershipReadSerializer(source="ownership", read_only=True)

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
            "ownership_id",       # input
            "ownership",          # input nested
            "ownership_ref",      # output
            "ownership_detail",   # output
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            self.fields["ownership_id"].queryset = Ownership.objects.filter(user=request.user)

    def _has_nested_ownership(self):
        data = getattr(self, "initial_data", {}) or {}
        return isinstance(data.get("ownership"), dict)

    def _has_ownership_id(self):
        data = getattr(self, "initial_data", {}) or {}
        return "ownership_id" in data and data.get("ownership_id") not in (None, "", [])

    def validate(self, attrs):
        request = self.context["request"]

        tracking_mode = attrs.get("tracking_mode", getattr(self.instance, "tracking_mode", None))
        accounting_account_id = attrs.get("accounting_account_id", getattr(self.instance, "accounting_account_id", None))

        if tracking_mode == Asset.TrackingMode.ACCOUNTING and not accounting_account_id:
            raise serializers.ValidationError(
                {"accounting_account_id": "Requerido si tracking_mode=accounting (placeholder hasta que exista contabilidad)."}
            )

        if self._has_nested_ownership() and self._has_ownership_id():
            raise serializers.ValidationError("Usa solo ownership_id o ownership (no ambos).")

        category = attrs.get("category", getattr(self.instance, "category", None))
        subcategory = attrs.get("subcategory", getattr(self.instance, "subcategory", None))
        if category and subcategory:
            allowed = ASSET_SUBCATEGORY_MAP.get(category)
            if allowed and subcategory not in allowed:
                raise serializers.ValidationError({"subcategory": "Subcategoría inválida para esta categoría."})

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

    def _create_ownership_from_nested(self):
        data = self.initial_data.get("ownership")
        serializer = OwnershipWriteSerializer(data=data, context=self.context)
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def create(self, validated_data):
        request = self.context["request"]

        if self._has_nested_ownership():
            validated_data["ownership"] = self._create_ownership_from_nested()

        return Asset.objects.create(user=request.user, **validated_data)

    def update(self, instance, validated_data):
        if self._has_nested_ownership():
            validated_data["ownership"] = self._create_ownership_from_nested()

        return super().update(instance, validated_data)



# ---------- Snapshot ----------

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


class AssetMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ["id", "name", "category", "subcategory"]


class LiabilitySerializer(serializers.ModelSerializer):
    amount_base = serializers.SerializerMethodField()
    ownership_id = serializers.PrimaryKeyRelatedField(
        queryset=Ownership.objects.none(),
        source="ownership",
        required=False,
        allow_null=True,
        write_only=True,
    )
    ownership = OwnershipWriteSerializer(required=False, write_only=True)

    financed_asset_id = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects.none(),   # se setea en __init__
        source="financed_asset",
        required=False,
        allow_null=True,
        write_only=True,
    )

    # OUTPUTS
    ownership_ref = serializers.IntegerField(source="ownership_id", read_only=True)
    ownership_detail = OwnershipReadSerializer(source="ownership", read_only=True)

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
            "is_asset_backed",        # lo mantenemos, pero lo autogestionamos
            "financed_asset_id",      # input
            "financed_asset_ref",     # output
            "financed_asset_detail",  # output mini
            "notes",
            "ownership_id",           # input
            "ownership",              # input nested
            "ownership_ref",          # output
            "ownership_detail",       # output
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            self.fields["ownership_id"].queryset = Ownership.objects.filter(user=request.user)
            self.fields["financed_asset_id"].queryset = Asset.objects.filter(
                user=request.user,
                is_active=True,  # <-- SOLO ACTIVOS ACTIVOS
            )

    def _has_nested_ownership(self):
        data = getattr(self, "initial_data", {}) or {}
        return isinstance(data.get("ownership"), dict)

    def _has_ownership_id(self):
        data = getattr(self, "initial_data", {}) or {}
        return "ownership_id" in data and data.get("ownership_id") not in (None, "", [])

    def validate(self, attrs):
        tracking_mode = attrs.get("tracking_mode", getattr(self.instance, "tracking_mode", None))
        accounting_account_id = attrs.get("accounting_account_id", getattr(self.instance, "accounting_account_id", None))

        if tracking_mode == Liability.TrackingMode.ACCOUNTING and not accounting_account_id:
            raise serializers.ValidationError(
                {"accounting_account_id": "Requerido si tracking_mode=accounting (placeholder hasta que exista contabilidad)."}
            )

        if self._has_nested_ownership() and self._has_ownership_id():
            raise serializers.ValidationError("Usa solo ownership_id o ownership (no ambos).")

        # --- coherencia: si hay activo financiado => deuda respaldada; si no => no respaldada
        financed_asset = attrs.get("financed_asset", getattr(self.instance, "financed_asset", None))
        attrs["is_asset_backed"] = financed_asset is not None

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

    def _create_ownership_from_nested(self):
        data = self.initial_data.get("ownership")
        serializer = OwnershipWriteSerializer(data=data, context=self.context)
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def create(self, validated_data):
        request = self.context["request"]

        if self._has_nested_ownership():
            validated_data["ownership"] = self._create_ownership_from_nested()

        return Liability.objects.create(user=request.user, **validated_data)

    def update(self, instance, validated_data):
        if self._has_nested_ownership():
            validated_data["ownership"] = self._create_ownership_from_nested()

        return super().update(instance, validated_data)
    
    




