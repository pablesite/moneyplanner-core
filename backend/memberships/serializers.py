from django.utils import timezone
from rest_framework import serializers

from .models import FamilyMember, Ownership, OwnershipIncomeRule, OwnershipLink, OwnershipSplit
from .services import (
    create_member_with_default_ownership,
    create_ownership,
    ownership_is_in_use,
    update_ownership,
    validate_split_percent,
    validate_ownership_write_payload,
)
from .services_allocations import resolve_ownership_allocation


class FamilyMemberSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return create_member_with_default_ownership(user=user, validated_data=validated_data)

    class Meta:
        model = FamilyMember
        fields = ["id", "name", "role", "is_active"]


class FamilyMemberMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        fields = ["id", "name", "role"]


class OwnershipSplitReadSerializer(serializers.ModelSerializer):
    member = FamilyMemberMiniSerializer(read_only=True)

    class Meta:
        model = OwnershipSplit
        fields = ["member", "percent"]


class OwnershipIncomeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = OwnershipIncomeRule
        fields = ["category_key", "subcategory_key"]


class OwnershipReadSerializer(serializers.ModelSerializer):
    member = FamilyMemberMiniSerializer(read_only=True)
    splits = OwnershipSplitReadSerializer(many=True, read_only=True)
    is_in_use = serializers.SerializerMethodField()
    income_rules = OwnershipIncomeRuleSerializer(many=True, read_only=True)
    effective_splits = serializers.SerializerMethodField()

    class Meta:
        model = Ownership
        fields = [
            "id",
            "kind",
            "member",
            "splits",
            "allocation_basis",
            "income_rules",
            "effective_splits",
            "is_in_use",
        ]

    def get_is_in_use(self, obj):
        return ownership_is_in_use(obj)

    def get_effective_splits(self, obj):
        if obj.allocation_basis != Ownership.AllocationBasis.RECURRING_INCOME_12M:
            return None

        today = timezone.localdate()
        allocation = resolve_ownership_allocation(
            ownership=obj,
            fiscal_year=today.year,
            month=today.month,
            persist=False,
        )
        return [
            {
                "member_id": share["member_id"],
                "member_name": share["member_name"],
                "percent": share["percent"],
            }
            for share in allocation["shares"]
        ]


class OwnershipSplitInputSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()
    percent = serializers.DecimalField(max_digits=5, decimal_places=2)

    def validate_percent(self, value):
        validate_split_percent(percent=value)
        return value


class OwnershipWriteSerializer(serializers.ModelSerializer):
    splits = OwnershipSplitInputSerializer(many=True, required=False)
    income_rules = OwnershipIncomeRuleSerializer(many=True, required=False)

    class Meta:
        model = Ownership
        fields = ["id", "kind", "member", "splits", "allocation_basis", "income_rules"]

    def _get_user(self):
        req = self.context.get("request")
        return getattr(req, "user", None)

    def validate(self, attrs):
        validate_ownership_write_payload(
            user=self._get_user(),
            instance=self.instance,
            attrs=attrs,
        )
        return attrs

    def create(self, validated_data):
        return create_ownership(user=self._get_user(), validated_data=validated_data)

    def update(self, instance, validated_data):
        return update_ownership(
            ownership=instance,
            user=self._get_user(),
            validated_data=validated_data,
        )


class OwnershipLinkReadSerializer(serializers.ModelSerializer):
    ownership_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = OwnershipLink
        fields = ["id", "target_type", "target_id", "ownership_id", "updated_at"]


class OwnershipLinkSyncSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=OwnershipLink.TargetType.choices)
    target_id = serializers.IntegerField(min_value=1)
    ownership_id = serializers.IntegerField(required=False, allow_null=True)
