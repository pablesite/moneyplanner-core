from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from accounting.models import LedgerAccount
from memberships.models import FamilyMember, Ownership
from net_worth.models import Asset

from .models import (
    AllocationStrategy,
    AllocationTarget,
    ContributionBasket,
    ContributionBasketLine,
    ContributionCommitment,
    PositionAllocationRule,
    ContainerCashAccount,
    Instrument,
    InstrumentPrice,
    InstrumentProviderMapping,
    InvestmentContainer,
    Portfolio,
    PortfolioMigrationIssue,
    PortfolioPosition,
    PositionValuation,
    PositionOwnershipPeriod,
    PositionOwnershipShare,
)
from .services import (
    close_open_ownership_period_before,
    position_coverage,
    validate_ownership_period,
)


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
        # Al editar se valida sobre una copia de la fila existente, no sobre una nueva
        # con el mismo pk: Django solo se excluye a si misma de las unicidades cuando la
        # instancia no esta en estado "adding", asi que cambiar la cuenta de efectivo de
        # un contenedor chocaba contra su propio enlace.
        if self.instance is not None:
            instance = ContainerCashAccount.objects.get(pk=self.instance.pk)
        else:
            instance = ContainerCashAccount()
        instance.container = attrs.get("container", getattr(self.instance, "container", None))
        instance.ledger_account = attrs.get(
            "ledger_account", getattr(self.instance, "ledger_account", None)
        )
        instance.currency = attrs.get("currency", getattr(self.instance, "currency", ""))
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


class InstrumentProviderMappingSerializer(serializers.ModelSerializer):
    instrument_id = serializers.PrimaryKeyRelatedField(
        source="instrument", queryset=Instrument.objects.all()
    )

    class Meta:
        model = InstrumentProviderMapping
        fields = [
            "id",
            "instrument_id",
            "provider",
            "provider_symbol",
            "provider_market",
            "quote_currency",
            "is_confirmed",
            "confirmed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "confirmed_at", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        fields["instrument_id"].queryset = Instrument.objects.filter(
            user=_request_user(self.context)
        )
        return fields

    def validate_provider_symbol(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El símbolo del proveedor es obligatorio.")
        return value

    def validate_quote_currency(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3:
            raise serializers.ValidationError("Usa una moneda de tres letras.")
        return value

    def validate(self, attrs: dict) -> dict:
        provider = attrs.get("provider", getattr(self.instance, "provider", ""))
        instrument = attrs.get("instrument", getattr(self.instance, "instrument", None))
        provider_symbol = attrs.get(
            "provider_symbol", getattr(self.instance, "provider_symbol", "")
        )
        provider_market = (
            attrs.get("provider_market", getattr(self.instance, "provider_market", ""))
            .strip()
            .upper()
        )
        attrs["provider_market"] = provider_market
        if provider == InstrumentProviderMapping.Provider.TWELVE_DATA and not provider_market:
            raise serializers.ValidationError(
                {"provider_market": "Confirma el mercado para Twelve Data."}
            )
        if provider == InstrumentProviderMapping.Provider.COINGECKO:
            if instrument.instrument_type != Instrument.InstrumentType.CRYPTO:
                raise serializers.ValidationError(
                    {"provider": "CoinGecko solo admite instrumentos crypto."}
                )
            if provider_symbol.lower() not in {"bitcoin", "ethereum"}:
                raise serializers.ValidationError(
                    {"provider_symbol": "Solo bitcoin y ethereum tienen fallback confirmado."}
                )
            attrs["provider_market"] = ""
        return attrs

    def create(self, validated_data: dict) -> InstrumentProviderMapping:
        if validated_data.get("is_confirmed"):
            validated_data["confirmed_at"] = timezone.now()
        return InstrumentProviderMapping.objects.create(**validated_data)

    def update(
        self, instance: InstrumentProviderMapping, validated_data: dict
    ) -> InstrumentProviderMapping:
        if validated_data.get("is_confirmed") and not instance.is_confirmed:
            validated_data["confirmed_at"] = timezone.now()
        if validated_data.get("is_confirmed") is False:
            validated_data["confirmed_at"] = None
        return super().update(instance, validated_data)


class InstrumentPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstrumentPrice
        fields = [
            "id",
            "instrument_id",
            "provider_mapping_id",
            "price_date",
            "close",
            "currency",
            "source",
            "source_key",
            "source_market",
            "fetched_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PositionValuationSerializer(serializers.ModelSerializer):
    position_id = serializers.PrimaryKeyRelatedField(
        source="position", queryset=PortfolioPosition.objects.all()
    )

    class Meta:
        model = PositionValuation
        fields = [
            "id",
            "position_id",
            "valuation_date",
            "value",
            "currency",
            "source",
            "legacy_asset_valuation_id",
            "legacy_ledger_transaction_id",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "source",
            "legacy_asset_valuation_id",
            "legacy_ledger_transaction_id",
            "created_at",
            "updated_at",
        ]

    def get_fields(self):
        fields = super().get_fields()
        fields["position_id"].queryset = PortfolioPosition.objects.filter(
            portfolio__user=_request_user(self.context)
        )
        return fields

    def validate_currency(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3:
            raise serializers.ValidationError("Usa una moneda de tres letras.")
        return value

    def validate(self, attrs: dict) -> dict:
        if self.instance is not None and self.instance.source != PositionValuation.Source.MANUAL:
            raise serializers.ValidationError("Las valoraciones legacy son de solo lectura.")
        return attrs

    def create(self, validated_data: dict) -> PositionValuation:
        return PositionValuation.objects.create(
            source=PositionValuation.Source.MANUAL,
            **validated_data,
        )


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
        # El tramo anterior se cierra la víspera: registrar un cambio de titularidad es
        # decir "desde esta fecha manda esto", no abrir un periodo suelto.
        close_open_ownership_period_before(
            position=validated_data["position"], start_date=validated_data["start_date"]
        )
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
            "history_mode",
            "history_start_date",
            "setup_confirmed_at",
            "coverage",
            "ownership_periods",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "coverage",
            "ownership_periods",
            "setup_confirmed_at",
            "created_at",
            "updated_at",
        ]

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
            "history_mode": attrs.get(
                "history_mode", getattr(self.instance, "history_mode", "reconstructed")
            ),
            "history_start_date": attrs.get(
                "history_start_date", getattr(self.instance, "history_start_date", None)
            ),
        }
        candidate = PortfolioPosition(**values)
        if self.instance is not None:
            candidate.pk = self.instance.pk
            candidate._state.adding = False
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


class AllocationTargetSerializer(serializers.ModelSerializer):
    position_id = serializers.PrimaryKeyRelatedField(
        source="position",
        queryset=PortfolioPosition.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = AllocationTarget
        fields = [
            "id",
            "asset_class",
            "position_id",
            "target_percent",
            "min_percent",
            "max_percent",
        ]
        read_only_fields = ["id"]

    def get_fields(self):
        fields = super().get_fields()
        user = _request_user(self.context)
        fields["position_id"].queryset = PortfolioPosition.objects.filter(portfolio__user=user)
        return fields

    def validate(self, attrs: dict) -> dict:
        asset_class = attrs.get("asset_class") or ""
        position = attrs.get("position")
        if bool(asset_class) == bool(position):
            raise serializers.ValidationError(
                "Un objetivo es de una clase o de una posición, no de las dos."
            )
        # "Sin clasificar" es la ausencia de respuesta: no se le pone objetivo.
        if asset_class == Instrument.AssetClass.UNCLASSIFIED:
            raise serializers.ValidationError(
                {"asset_class": "Clasifica el activo antes de ponerle objetivo."}
            )
        return attrs


class AllocationStrategySerializer(serializers.ModelSerializer):
    ownership_id = serializers.PrimaryKeyRelatedField(
        source="ownership", queryset=Ownership.objects.all()
    )
    targets = AllocationTargetSerializer(many=True)
    target_total = serializers.SerializerMethodField()

    class Meta:
        model = AllocationStrategy
        fields = [
            "id",
            "ownership_id",
            "effective_from",
            "note",
            "max_cost_share",
            "min_line_amount",
            "targets",
            "target_total",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_target_total(self, obj: AllocationStrategy) -> str:
        # Solo las lineas de clase: una linea de posicion reparte dentro de su clase y no
        # suma sobre la cartera.
        return str(
            sum((row.target_percent for row in obj.targets.all() if row.asset_class), Decimal("0"))
        )

    def get_fields(self):
        fields = super().get_fields()
        user = _request_user(self.context)
        fields["ownership_id"].queryset = Ownership.objects.filter(user=user)
        return fields

    def validate_targets(self, value: list[dict]) -> list[dict]:
        # Una linea de posicion reparte dentro de su clase, asi que varias de la misma
        # clase no pueden pedir mas del 100%: seria repartir un pastel que no existe.
        claimed: dict[str, Decimal] = {}
        for row in value:
            position = row.get("position")
            if position is None:
                continue
            asset_class = position.effective_asset_class
            claimed[asset_class] = claimed.get(asset_class, Decimal("0")) + row["target_percent"]
        excess = [name for name, total in claimed.items() if total > Decimal("100")]
        if excess:
            raise serializers.ValidationError(
                "Dentro de una clase los objetivos por producto no pueden pasar del 100%: "
                + ", ".join(sorted(excess))
            )
        return value

    def _write_targets(self, strategy: AllocationStrategy, targets: list[dict]) -> None:
        strategy.targets.all().delete()
        AllocationTarget.objects.bulk_create(
            [AllocationTarget(strategy=strategy, **row) for row in targets]
        )

    @transaction.atomic
    def create(self, validated_data: dict) -> AllocationStrategy:
        targets = validated_data.pop("targets", [])
        portfolio = Portfolio.objects.get(user=_request_user(self.context))
        strategy = AllocationStrategy.objects.create(portfolio=portfolio, **validated_data)
        self._write_targets(strategy, targets)
        return strategy

    @transaction.atomic
    def update(self, instance: AllocationStrategy, validated_data: dict) -> AllocationStrategy:
        targets = validated_data.pop("targets", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if targets is not None:
            self._write_targets(instance, targets)
        return instance


class PositionAllocationRuleSerializer(serializers.ModelSerializer):
    position_id = serializers.PrimaryKeyRelatedField(
        source="position", queryset=PortfolioPosition.objects.all()
    )

    class Meta:
        model = PositionAllocationRule
        fields = [
            "id",
            "position_id",
            "excluded",
            "min_contribution",
            "rounding_step",
            "operation_cost",
            "fee_free_plan",
        ]
        read_only_fields = ["id"]

    def get_fields(self):
        fields = super().get_fields()
        user = _request_user(self.context)
        fields["position_id"].queryset = PortfolioPosition.objects.filter(portfolio__user=user)
        return fields


class ContributionCommitmentSerializer(serializers.ModelSerializer):
    position_id = serializers.PrimaryKeyRelatedField(
        source="position", queryset=PortfolioPosition.objects.all()
    )

    class Meta:
        model = ContributionCommitment
        fields = ["id", "position_id", "period", "amount", "reason", "is_active"]
        read_only_fields = ["id"]

    def get_fields(self):
        fields = super().get_fields()
        user = _request_user(self.context)
        fields["position_id"].queryset = PortfolioPosition.objects.filter(portfolio__user=user)
        return fields


class ContributionBasketLineSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = ContributionBasketLine
        fields = [
            "id",
            "position_id",
            "cash_account_id",
            "name",
            "amount",
            "reason",
            "status",
            "confirmed_at",
        ]

    def get_name(self, obj: ContributionBasketLine) -> str:
        if obj.position_id:
            return obj.position.asset.name
        return f"Efectivo · {obj.cash_account.container.name}"


class ContributionBasketSerializer(serializers.ModelSerializer):
    lines = ContributionBasketLineSerializer(many=True, read_only=True)

    class Meta:
        model = ContributionBasket
        fields = [
            "id",
            "ownership_id",
            "strategy_id",
            "booking_date",
            "amount",
            "reserved_cash",
            "leftover",
            "status",
            "source_account_id",
            "explanation",
            "lines",
            "created_at",
            "confirmed_at",
        ]
