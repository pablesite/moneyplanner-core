from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Asset,
    AssetImprovement,
    Liability,
    LiquidityMonthlyCheckin,
    NetWorthSnapshot,
)
from .services_assets import (
    RESIDENTIAL_REAL_ESTATE_SUBCATEGORIES,
    create_asset_for_user,
    get_default_amortization_term_years,
    get_effective_asset_amount,
    get_amount_base_value,
    validate_asset_improvement_payload,
    validate_asset_payload,
)
from .services_liabilities import (
    create_liability_for_user,
    estimate_liability_monthly_payment_simple,
    estimate_liability_outstanding_amount_simple,
    get_effective_liability_amount,
    infer_liability_is_asset_backed,
    validate_liability_payload,
)
from .services_snapshots import create_snapshot_for_user, validate_snapshot_payload


class EmptySerializer(serializers.Serializer):
    pass


class AssetImprovementSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = AssetImprovement
        fields = [
            "id",
            "name",
            "reform_date",
            "amount",
            "amortization_method",
            "amortization_term_years",
            "annual_interest_tae",
            "capitalize_interest",
            "manual_current_value",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        amortization_method = attrs.get(
            "amortization_method",
            getattr(self.instance, "amortization_method", AssetImprovement.AmortizationMethod.NONE),
        )
        amortization_term_years = attrs.get(
            "amortization_term_years",
            getattr(self.instance, "amortization_term_years", None),
        )
        capitalize_interest = attrs.get(
            "capitalize_interest",
            getattr(self.instance, "capitalize_interest", False),
        )
        annual_interest_tae = attrs.get(
            "annual_interest_tae",
            getattr(self.instance, "annual_interest_tae", None),
        )
        manual_current_value = attrs.get(
            "manual_current_value",
            getattr(self.instance, "manual_current_value", None),
        )
        validate_asset_improvement_payload(
            amortization_method=amortization_method,
            amortization_term_years=amortization_term_years,
            capitalize_interest=capitalize_interest,
            annual_interest_tae=annual_interest_tae,
            manual_current_value=manual_current_value,
        )
        return attrs


class AssetSerializer(serializers.ModelSerializer):
    amount_base = serializers.SerializerMethodField()
    effective_amount = serializers.SerializerMethodField()
    improvements = AssetImprovementSerializer(many=True, required=False)

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
            "start_date",
            "expected_end_date",
            "initial_purchase_value",
            "investment_contribution_mode",
            "monthly_contribution_amount",
            "amortization_method",
            "amortization_term_years",
            "valuation_model",
            "land_value_share_percent",
            "land_annual_appreciation_percent",
            "building_annual_depreciation_percent",
            "improvements",
            "annual_interest_tae",
            "estimated_average_balance_for_interest",
            "deposit_term_months",
            "amount",
            "effective_amount",
            "amount_base",
            "is_active",
            "notes",
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
        annual_interest_tae = attrs.get(
            "annual_interest_tae", getattr(self.instance, "annual_interest_tae", None)
        )
        deposit_term_months = attrs.get(
            "deposit_term_months", getattr(self.instance, "deposit_term_months", None)
        )
        if not (
            category == Asset.Category.CASH and subcategory == Asset.Subcategory.SHORT_TERM_DEPOSIT
        ):
            deposit_term_months = None
            attrs["deposit_term_months"] = None
        amortization_method = attrs.get(
            "amortization_method", getattr(self.instance, "amortization_method", None)
        )
        amortization_term_years = attrs.get(
            "amortization_term_years", getattr(self.instance, "amortization_term_years", None)
        )
        if amortization_term_years is None:
            default_term_years = get_default_amortization_term_years(
                category=category,
                subcategory=subcategory,
                amortization_method=amortization_method,
            )
            if default_term_years is not None:
                amortization_term_years = default_term_years
                attrs["amortization_term_years"] = default_term_years
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        initial_purchase_value = attrs.get(
            "initial_purchase_value", getattr(self.instance, "initial_purchase_value", None)
        )
        investment_contribution_mode = attrs.get(
            "investment_contribution_mode",
            getattr(
                self.instance,
                "investment_contribution_mode",
                Asset.InvestmentContributionMode.ONE_TIME,
            ),
        )
        expected_end_date = attrs.get(
            "expected_end_date", getattr(self.instance, "expected_end_date", None)
        )
        monthly_contribution_amount = attrs.get(
            "monthly_contribution_amount",
            getattr(self.instance, "monthly_contribution_amount", None),
        )
        valuation_model = attrs.get(
            "valuation_model", getattr(self.instance, "valuation_model", None)
        )
        land_value_share_percent = attrs.get(
            "land_value_share_percent", getattr(self.instance, "land_value_share_percent", None)
        )
        land_annual_appreciation_percent = attrs.get(
            "land_annual_appreciation_percent",
            getattr(self.instance, "land_annual_appreciation_percent", None),
        )
        building_annual_depreciation_percent = attrs.get(
            "building_annual_depreciation_percent",
            getattr(self.instance, "building_annual_depreciation_percent", None),
        )
        if (
            amortization_method
            and amortization_method != Asset.AmortizationMethod.NONE
            and initial_purchase_value is None
            and amount is not None
        ):
            initial_purchase_value = amount
            attrs["initial_purchase_value"] = amount

        if valuation_model == Asset.ValuationModel.REAL_ESTATE_AUTO:
            if initial_purchase_value is None and attrs.get("amount") is not None:
                initial_purchase_value = attrs["amount"]
                attrs["initial_purchase_value"] = attrs["amount"]
        else:
            attrs["land_value_share_percent"] = None
            attrs["land_annual_appreciation_percent"] = None
            attrs["building_annual_depreciation_percent"] = None
            if attrs.get("improvements"):
                raise serializers.ValidationError(
                    {
                        "improvements": (
                            "Solo disponibles para inmuebles residenciales con valoracion automatica."
                        )
                    }
                )
            if "improvements" not in attrs and self.instance is not None:
                attrs["improvements"] = []

        if category != Asset.Category.INVESTMENTS:
            investment_contribution_mode = Asset.InvestmentContributionMode.ONE_TIME
            expected_end_date = None
            monthly_contribution_amount = None
            attrs["investment_contribution_mode"] = investment_contribution_mode
            attrs["expected_end_date"] = None
            attrs["monthly_contribution_amount"] = None
        elif investment_contribution_mode != Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION:
            expected_end_date = None
            monthly_contribution_amount = None
            attrs["expected_end_date"] = None
            attrs["monthly_contribution_amount"] = None
        elif initial_purchase_value is None and amount is not None:
            # En aportacion periodica de inversiones, usamos el importe como valor inicial.
            initial_purchase_value = amount
            attrs["initial_purchase_value"] = amount

        validate_asset_payload(
            tracking_mode=tracking_mode,
            accounting_account_id=accounting_account_id,
            category=category,
            subcategory=subcategory,
            annual_interest_tae=annual_interest_tae,
            amortization_method=amortization_method,
            amortization_term_years=amortization_term_years,
            initial_purchase_value=initial_purchase_value,
            amount=amount,
            start_date=attrs.get("start_date", getattr(self.instance, "start_date", None)),
            valuation_model=valuation_model,
            land_value_share_percent=land_value_share_percent,
            land_annual_appreciation_percent=land_annual_appreciation_percent,
            building_annual_depreciation_percent=building_annual_depreciation_percent,
            deposit_term_months=deposit_term_months,
            investment_contribution_mode=investment_contribution_mode,
            expected_end_date=expected_end_date,
            monthly_contribution_amount=monthly_contribution_amount,
        )
        return attrs

    def get_amount_base(self, obj):
        effective_amount = get_effective_asset_amount(asset=obj)
        return get_amount_base_value(
            amount=effective_amount,
            currency=obj.currency,
            base_currency=self.context.get("base_currency"),
        )

    def get_effective_amount(self, obj):
        return str(get_effective_asset_amount(asset=obj))

    def create(self, validated_data):
        request = self.context["request"]
        improvements_data = validated_data.pop("improvements", [])
        asset = create_asset_for_user(user=request.user, validated_data=validated_data)
        self._sync_improvements(asset=asset, improvements_data=improvements_data)
        return asset

    def update(self, instance, validated_data):
        improvements_data = validated_data.pop("improvements", None)
        asset = super().update(instance, validated_data)
        if improvements_data is not None:
            self._sync_improvements(asset=asset, improvements_data=improvements_data)
        return asset

    def _sync_improvements(self, *, asset: Asset, improvements_data: list[dict]) -> None:
        if (
            asset.category != Asset.Category.REAL_ESTATE
            or asset.subcategory not in RESIDENTIAL_REAL_ESTATE_SUBCATEGORIES
            or asset.valuation_model != Asset.ValuationModel.REAL_ESTATE_AUTO
        ):
            if improvements_data:
                raise serializers.ValidationError(
                    {
                        "improvements": (
                            "Solo disponibles para inmuebles residenciales con valoracion automatica."
                        )
                    }
                )
            asset.improvements.all().delete()
            return

        existing_by_id = {row.id: row for row in asset.improvements.all()}
        seen_ids: set[int] = set()

        for row in improvements_data:
            improvement_id = row.pop("id", None)
            if improvement_id is None:
                AssetImprovement.objects.create(asset=asset, **row)
                continue
            current = existing_by_id.get(improvement_id)
            if current is None:
                raise serializers.ValidationError(
                    {"improvements": f"Reforma id={improvement_id} no encontrada en este activo."}
                )
            seen_ids.add(improvement_id)
            for key, value in row.items():
                setattr(current, key, value)
            current.save()

        for improvement_id, current in existing_by_id.items():
            if improvement_id not in seen_ids:
                current.delete()


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

        try:
            attrs["net_worth"] = validate_snapshot_payload(
                total_assets=total_assets,
                total_liabilities=total_liabilities,
                net_worth=net_worth,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
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
    estimated_monthly_payment_amount = serializers.SerializerMethodField()
    estimated_outstanding_amount = serializers.SerializerMethodField()
    effective_amount = serializers.SerializerMethodField()

    class Meta:
        model = Liability
        fields = [
            "id",
            "name",
            "category",
            "tracking_mode",
            "accounting_account_id",
            "currency",
            "start_date",
            "expected_end_date",
            "term_months",
            "principal_amount",
            "rate_type",
            "payment_frequency",
            "amortization_system",
            "annual_interest_tae",
            "estimated_monthly_payment_amount",
            "estimated_outstanding_amount",
            "effective_amount",
            "amount",
            "opening_fees_amount",
            "early_repayment_fee_percent",
            "novation_subrogation_fee_amount",
            "linked_products_monthly_cost",
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
        financed_asset_queryset = self.context.get("financed_asset_queryset")
        if financed_asset_queryset is not None:
            self.fields["financed_asset_id"].queryset = financed_asset_queryset

    def validate(self, attrs):
        tracking_mode = attrs.get("tracking_mode", getattr(self.instance, "tracking_mode", None))
        accounting_account_id = attrs.get(
            "accounting_account_id", getattr(self.instance, "accounting_account_id", None)
        )
        category = attrs.get("category", getattr(self.instance, "category", None))
        annual_interest_tae = attrs.get(
            "annual_interest_tae", getattr(self.instance, "annual_interest_tae", None)
        )
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        expected_end_date = attrs.get(
            "expected_end_date", getattr(self.instance, "expected_end_date", None)
        )
        payment_frequency = attrs.get(
            "payment_frequency", getattr(self.instance, "payment_frequency", None)
        )
        term_months = attrs.get("term_months", getattr(self.instance, "term_months", None))
        validate_liability_payload(
            tracking_mode=tracking_mode,
            accounting_account_id=accounting_account_id,
            category=category,
            annual_interest_tae=annual_interest_tae,
            start_date=start_date,
            expected_end_date=expected_end_date,
            payment_frequency=payment_frequency,
            term_months=term_months,
        )

        financed_asset = attrs.get("financed_asset", getattr(self.instance, "financed_asset", None))
        attrs["is_asset_backed"] = infer_liability_is_asset_backed(financed_asset=financed_asset)
        return attrs

    def get_amount_base(self, obj):
        effective_amount = get_effective_liability_amount(liability=obj)
        return get_amount_base_value(
            amount=effective_amount,
            currency=obj.currency,
            base_currency=self.context.get("base_currency"),
        )

    def get_estimated_monthly_payment_amount(self, obj):
        value = estimate_liability_monthly_payment_simple(
            amount=obj.principal_amount or obj.amount,
            annual_interest_tae=obj.annual_interest_tae,
            term_months=obj.term_months,
            payment_frequency=obj.payment_frequency,
            rate_type=obj.rate_type,
            amortization_system=obj.amortization_system,
        )
        return str(value) if value is not None else None

    def get_estimated_outstanding_amount(self, obj):
        value = estimate_liability_outstanding_amount_simple(liability=obj)
        return str(value) if value is not None else None

    def get_effective_amount(self, obj):
        return str(get_effective_liability_amount(liability=obj))

    def create(self, validated_data):
        request = self.context["request"]
        if (
            validated_data.get("principal_amount") is None
            and validated_data.get("term_months")
            and validated_data.get("amount") is not None
        ):
            validated_data["principal_amount"] = validated_data["amount"]
        return create_liability_for_user(user=request.user, validated_data=validated_data)


class LiquidityMonthlyCheckinSerializer(serializers.ModelSerializer):
    asset_id = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects.none(),
        source="asset",
        write_only=True,
    )
    asset_ref = serializers.IntegerField(source="asset_id", read_only=True)
    asset_detail = AssetMiniSerializer(source="asset", read_only=True)

    class Meta:
        model = LiquidityMonthlyCheckin
        fields = [
            "id",
            "asset_id",
            "asset_ref",
            "asset_detail",
            "fiscal_year",
            "month",
            "status",
            "closing_balance_real",
            "note",
            "confirmed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "confirmed_at", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        liquidity_asset_queryset = self.context.get("liquidity_asset_queryset")
        if liquidity_asset_queryset is not None:
            self.fields["asset_id"].queryset = liquidity_asset_queryset

    def validate_month(self, value: int) -> int:
        if value < 1 or value > 12:
            raise serializers.ValidationError("Mes invalido (1-12).")
        return value

    def validate(self, attrs):
        asset = attrs.get("asset", getattr(self.instance, "asset", None))
        if asset is None:
            raise serializers.ValidationError({"asset_id": "Requerido."})
        if asset.category != Asset.Category.CASH:
            raise serializers.ValidationError(
                {"asset_id": "Solo se permiten check-ins de activos de liquidez."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["user"] = request.user
        validated_data["confirmed_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data["confirmed_at"] = timezone.now()
        return super().update(instance, validated_data)
