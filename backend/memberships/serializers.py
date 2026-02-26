from rest_framework import serializers

from .models import FamilyMember, Ownership, OwnershipLink, OwnershipSplit
from .services import (
    create_ownership,
    ownership_is_in_use,
    update_ownership,
    validate_split_percent,
    validate_ownership_write_payload,
)


class FamilyMemberSerializer(serializers.ModelSerializer):
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


class OwnershipReadSerializer(serializers.ModelSerializer):
    member = FamilyMemberMiniSerializer(read_only=True)
    splits = OwnershipSplitReadSerializer(many=True, read_only=True)
    is_in_use = serializers.SerializerMethodField()

    class Meta:
        model = Ownership
        fields = ["id", "kind", "member", "splits", "is_in_use"]

    def get_is_in_use(self, obj):
        return ownership_is_in_use(obj)


class OwnershipSplitInputSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()
    percent = serializers.DecimalField(max_digits=5, decimal_places=2)

    def validate_percent(self, value):
        validate_split_percent(percent=value)
        return value


class OwnershipWriteSerializer(serializers.ModelSerializer):
    splits = OwnershipSplitInputSerializer(many=True, required=False)

    class Meta:
        model = Ownership
        fields = ["id", "kind", "member", "splits"]

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
