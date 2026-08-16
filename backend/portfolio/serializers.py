from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from accounting.models import LedgerAccount
from memberships.models import FamilyMember, Ownership
from net_worth.models import Asset

from .models import (
    ContainerCashAccount,
    Instrument,
    InvestmentContainer,
    Portfolio,
    PortfolioMigrationIssue,
    PortfolioPosition,
    PositionOwnershipPeriod,
    PositionOwnershipShare,
)
from .services import position_coverage, validate_ownership_period


def _request_user(context: dict):
    return context["request"].user


def _raise_model_validation(instance) -> None:
    try:
        instance.full_clean()
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.message_dict) from exc


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = ["id", "base_currency", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_base_currency(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3:
            raise serializers.ValidationError("Usa un código de moneda de tres letras.")
        return value


class InvestmentContainerSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentContainer
        fields = [
            "id",
            "name",
            "container_type",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data: dict) -> InvestmentContainer:
        portfolio = Portfolio.objects.get(user=_request_user(self.context))
        return InvestmentContainer.objects.create(portfolio=portfolio, **validated_data)


class ContainerCashAccountSerializer(serializers.ModelSerializer):
    container_id = serializers.PrimaryKeyRelatedField(
        source="container", queryset=InvestmentContainer.objects.all()
    )
    ledger_account_id = serializers.PrimaryKeyRelatedField(
        source="ledger_account", queryset=LedgerAccount.objects.all()
    )

    class Meta:
        model = ContainerCashAccount
        fields = ["id", "container_id", "ledger_account_id", "currency", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_fields(self):
        fields = super().get_fields()
        user = _request_user(self.context)
        fields["container_id"].queryset = InvestmentContainer.objects.filter(portfolio__user=user)
        fields["ledger_account_id"].queryset = LedgerAccount.objects.filter(user=user)
        return fields

    def validate_currency(self, value: str) -> str:
        return value.strip().upper()

    def validate(self, attrs: dict) -> dict:
        instance = ContainerCashAccount(
            container=attrs.get("container", getattr(self.instance, "container", None)),
            ledger_account=attrs.get(
                "ledger_account", getattr(self.instance, "ledger_account", None)
            ),
            currency=attrs.get("currency", getattr(self.instance, "currency", "")),
        )
        if self.instance is not None:
            instance.pk = self.instance.pk
        _raise_model_validation(instance)
        return attrs


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = [
            "id",
            "identity_kind",
            "name",
            "asset_class",
            "instrument_type",
            "quote_currency",
            "isin",
            "ticker",
            "market",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_quote_currency(self, value: str) -> str:
        return value.strip().upper()

    def validate(self, attrs: dict) -> dict:
        identity_kind = attrs.get(
            "identity_kind", getattr(self.instance, "identity_kind", Instrument.IdentityKind.CUSTOM)
        )
        if self.instance is None and identity_kind != Instrument.IdentityKind.CUSTOM:
            raise serializers.ValidationError(
                {"identity_kind": "La API de usuario solo crea instrumentos custom."}
            )
        return attrs

    def create(self, validated_data: dict) -> Instrument:
        return Instrument.objects.create(user=_request_user(self.context), **validated_data)


class PositionOwnershipShareSerializer(serializers.ModelSerializer):
    member_id = serializers.PrimaryKeyRelatedField(
        source="member", queryset=FamilyMember.objects.all()
    )

    class Meta:
        model = PositionOwnershipShare
        fields = ["id", "member_id", "percent", "created_at"]
        read_only_fields = ["id", "created_at"]


class PositionOwnershipPeriodSerializer(serializers.ModelSerializer):
    position_id = serializers.PrimaryKeyRelatedField(
        source="position", queryset=PortfolioPosition.objects.all()
    )
    ownership_id = serializers.PrimaryKeyRelatedField(
        source="ownership", queryset=Ownership.objects.all()
    )
    shares = PositionOwnershipShareSerializer(many=True)

    class Meta:
        model = PositionOwnershipPeriod
        fields = [
            "id",
            "position_id",
            "ownership_id",
            "start_date",
            "end_date",
            "shares",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_fields(self):
        fields = super().get_fields()
        user = _request_user(self.context)
        fields["position_id"].queryset = PortfolioPosition.objects.filter(portfolio__user=user)
        fields["ownership_id"].queryset = Ownership.objects.filter(user=user)
        share_field = fields["shares"].child.fields["member_id"]
        share_field.queryset = FamilyMember.objects.filter(user=user)
        return fields

    def validate(self, attrs: dict) -> dict:
        if self.instance is not None:
            raise serializers.ValidationError("Los periodos de titularidad son inmutables.")
        shares = attrs.get("shares", [])
        if not shares or sum(row["percent"] for row in shares) != Decimal("100"):
            raise serializers.ValidationError({"shares": "Las participaciones deben sumar 100%."})
        member_ids = [row["member"].id for row in shares]
        if len(member_ids) != len(set(member_ids)):
            raise serializers.ValidationError({"shares": "No se puede repetir un miembro."})
        position = attrs["position"]
        ownership = attrs["ownership"]
        if position.portfolio.user_id != ownership.user_id:
            raise serializers.ValidationError({"ownership_id": "Titularidad fuera de la cartera."})
        try:
            validate_ownership_period(
                position=position,
                start_date=attrs["start_date"],
                end_date=attrs.get("end_date"),
            )
        except ValueError as exc:
            raise serializers.ValidationError({"start_date": str(exc)}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict) -> PositionOwnershipPeriod:
        shares = validated_data.pop("shares")
        period = PositionOwnershipPeriod.objects.create(**validated_data)
        PositionOwnershipShare.objects.bulk_create(
            [PositionOwnershipShare(period=period, **share) for share in shares]
        )
        return period


class PortfolioPositionSerializer(serializers.ModelSerializer):
    container_id = serializers.PrimaryKeyRelatedField(
        source="container", queryset=InvestmentContainer.objects.all()
    )
    instrument_id = serializers.PrimaryKeyRelatedField(
        source="instrument", queryset=Instrument.objects.all()
    )
    asset_id = serializers.PrimaryKeyRelatedField(source="asset", queryset=Asset.objects.all())
    ledger_account_id = serializers.PrimaryKeyRelatedField(
        source="ledger_account",
        queryset=LedgerAccount.objects.all(),
        allow_null=True,
        required=False,
    )
    coverage = serializers.SerializerMethodField()
    ownership_periods = PositionOwnershipPeriodSerializer(many=True, read_only=True)

    class Meta:
        model = PortfolioPosition
        fields = [
            "id",
            "container_id",
            "instrument_id",
            "asset_id",
            "ledger_account_id",
            "tracking_style",
            "status",
            "opened_on",
            "closed_on",
            "coverage",
            "ownership_periods",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "coverage", "ownership_periods", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        user = _request_user(self.context)
        fields["container_id"].queryset = InvestmentContainer.objects.filter(portfolio__user=user)
        fields["instrument_id"].queryset = Instrument.objects.filter(
            Q(user=user) | Q(user__isnull=True)
        )
        fields["asset_id"].queryset = Asset.objects.filter(
            user=user, category=Asset.Category.INVESTMENTS
        )
        fields["ledger_account_id"].queryset = LedgerAccount.objects.filter(user=user)
        return fields

    def get_coverage(self, obj: PortfolioPosition) -> dict:
        return position_coverage(obj)

    def validate(self, attrs: dict) -> dict:
        portfolio = Portfolio.objects.get(user=_request_user(self.context))
        values = {
            "portfolio": portfolio,
            "container": attrs.get("container", getattr(self.instance, "container", None)),
            "instrument": attrs.get("instrument", getattr(self.instance, "instrument", None)),
            "asset": attrs.get("asset", getattr(self.instance, "asset", None)),
            "ledger_account": attrs.get(
                "ledger_account", getattr(self.instance, "ledger_account", None)
            ),
            "tracking_style": attrs.get(
                "tracking_style", getattr(self.instance, "tracking_style", "")
            ),
            "status": attrs.get("status", getattr(self.instance, "status", "")),
            "opened_on": attrs.get("opened_on", getattr(self.instance, "opened_on", None)),
            "closed_on": attrs.get("closed_on", getattr(self.instance, "closed_on", None)),
        }
        candidate = PortfolioPosition(**values)
        if self.instance is not None:
            candidate.pk = self.instance.pk
        _raise_model_validation(candidate)
        return attrs

    def create(self, validated_data: dict) -> PortfolioPosition:
        portfolio = Portfolio.objects.get(user=_request_user(self.context))
        return PortfolioPosition.objects.create(portfolio=portfolio, **validated_data)


class PortfolioMigrationIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioMigrationIssue
        fields = ["id", "asset_id", "code", "status", "detail", "created_at", "updated_at"]
        read_only_fields = fields
