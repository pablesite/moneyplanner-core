from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from accounting.services_ledger import (
    get_user_ledger_account,
    sync_net_worth_opening_balance_transaction,
)
from .models import (
    Asset,
    AssetImprovement,
    AssetValuation,
    InvestmentAssetEvent,
    Liability,
    LiabilityEvent,
    LiabilityValuation,
    LiquidityAssetEvent,
    LiquidityMonthlyCheckin,
    NetWorthSnapshot,
)
from .services_assets_core import (
    AccountingIntegrationState as AssetAccountingIntegrationState,
    RESIDENTIAL_REAL_ESTATE_SUBCATEGORIES,
    create_asset_for_user,
    ensure_asset_accounting_account,
    get_default_amortization_term_years,
    get_effective_asset_amount,
    get_amount_base_value,
    validate_asset_improvement_payload,
    validate_investment_asset_event_payload,
    validate_liquidity_asset_event_payload,
    validate_asset_payload,
)
from .services_liabilities_core import (
    AccountingIntegrationState as LiabilityAccountingIntegrationState,
    create_liability_for_user,
    ensure_liability_accounting_account,
    estimate_liability_monthly_payment_simple,
    estimate_liability_outstanding_amount_simple,
    get_effective_liability_amount,
    infer_liability_is_asset_backed,
    validate_liability_event_payload,
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
    accounting_integration_state = serializers.SerializerMethodField()
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
            "accounting_integration_state",
            "currency",
            "start_date",
            "expected_end_date",
            "initial_purchase_value",
            "investment_contribution_mode",
            "investment_contribution_frequency",
            "investment_contribution_currency",
            "monthly_contribution_amount",
            "market_value_override",
            "market_value_override_date",
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
        request = self.context.get("request")
        tracking_mode = attrs.get("tracking_mode", getattr(self.instance, "tracking_mode", None))
        accounting_account_id = attrs.get("accounting_account_id")
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
        investment_contribution_frequency = attrs.get(
            "investment_contribution_frequency",
            getattr(
                self.instance,
                "investment_contribution_frequency",
                Asset.InvestmentContributionFrequency.MONTHLY,
            ),
        )
        investment_contribution_currency = attrs.get(
            "investment_contribution_currency",
            getattr(self.instance, "investment_contribution_currency", None),
        )
        expected_end_date = attrs.get(
            "expected_end_date", getattr(self.instance, "expected_end_date", None)
        )
        monthly_contribution_amount = attrs.get(
            "monthly_contribution_amount",
            getattr(self.instance, "monthly_contribution_amount", None),
        )
        market_value_override = attrs.get(
            "market_value_override", getattr(self.instance, "market_value_override", None)
        )
        market_value_override_date = attrs.get(
            "market_value_override_date",
            getattr(self.instance, "market_value_override_date", None),
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
            # Keep the backend purchase value in sync with the single "importe" field exposed in UI.
            if attrs.get("amount") is not None:
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
            investment_contribution_frequency = Asset.InvestmentContributionFrequency.MONTHLY
            investment_contribution_currency = None
            expected_end_date = None
            monthly_contribution_amount = None
            market_value_override = None
            market_value_override_date = None
            attrs["investment_contribution_mode"] = investment_contribution_mode
            attrs["investment_contribution_frequency"] = investment_contribution_frequency
            attrs["investment_contribution_currency"] = None
            attrs["expected_end_date"] = None
            attrs["monthly_contribution_amount"] = None
            attrs["market_value_override"] = None
            attrs["market_value_override_date"] = None
        elif investment_contribution_mode != Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION:
            investment_contribution_frequency = Asset.InvestmentContributionFrequency.MONTHLY
            investment_contribution_currency = None
            expected_end_date = None
            monthly_contribution_amount = None
            attrs["investment_contribution_frequency"] = investment_contribution_frequency
            attrs["investment_contribution_currency"] = None
            attrs["expected_end_date"] = None
            attrs["monthly_contribution_amount"] = None
        elif initial_purchase_value is None and amount is not None:
            # En aportacion periodica de inversiones, usamos el importe como valor inicial.
            initial_purchase_value = amount
            attrs["initial_purchase_value"] = amount
        if (
            investment_contribution_mode == Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION
            and not str(investment_contribution_currency or "").strip()
        ):
            investment_contribution_currency = attrs.get(
                "currency", getattr(self.instance, "currency", None)
            )
            attrs["investment_contribution_currency"] = investment_contribution_currency

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
            investment_contribution_frequency=investment_contribution_frequency,
            investment_contribution_currency=investment_contribution_currency,
            expected_end_date=expected_end_date,
            monthly_contribution_amount=monthly_contribution_amount,
            market_value_override=market_value_override,
            market_value_override_date=market_value_override_date,
            user_id=getattr(getattr(request, "user", None), "id", None),
            current_asset_id=getattr(self.instance, "id", None),
            currency=attrs.get("currency", getattr(self.instance, "currency", None)),
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

    def get_accounting_integration_state(self, obj):
        cached_state = getattr(obj, "_accounting_integration_state", None)
        if cached_state in {
            AssetAccountingIntegrationState.LINKED,
            AssetAccountingIntegrationState.AUTO_CREATED,
            AssetAccountingIntegrationState.NEEDS_REVIEW,
        }:
            return cached_state
        state = ensure_asset_accounting_account(asset=obj)
        if state in {
            AssetAccountingIntegrationState.LINKED,
            AssetAccountingIntegrationState.AUTO_CREATED,
            AssetAccountingIntegrationState.NEEDS_REVIEW,
        }:
            return state
        return None

    def create(self, validated_data):
        request = self.context["request"]
        improvements_data = validated_data.pop("improvements", [])
        asset = create_asset_for_user(user=request.user, validated_data=validated_data)
        asset._accounting_integration_state = ensure_asset_accounting_account(asset=asset)
        self._ensure_accounting_opening_balance(asset=asset)
        self._sync_improvements(asset=asset, improvements_data=improvements_data)
        return asset

    def update(self, instance, validated_data):
        improvements_data = validated_data.pop("improvements", None)
        asset = super().update(instance, validated_data)
        asset._accounting_integration_state = ensure_asset_accounting_account(asset=asset)
        self._ensure_accounting_opening_balance(asset=asset)
        if improvements_data is not None:
            self._sync_improvements(asset=asset, improvements_data=improvements_data)
        return asset

    def _ensure_accounting_opening_balance(self, *, asset: Asset) -> None:
        if asset.tracking_mode != Asset.TrackingMode.ACCOUNTING:
            return
        account = get_user_ledger_account(
            user_id=asset.user_id,
            account_id=asset.accounting_account_id,
        )
        if account is None:
            return
        from decimal import Decimal

        sync_net_worth_opening_balance_transaction(
            user=asset.user,
            account=account,
            amount=Decimal(asset.amount or 0),
            booking_date=asset.start_date or timezone.localdate(),
            asset=asset,
        )

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
    accounting_integration_state = serializers.SerializerMethodField()

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
            "accounting_integration_state",
            "currency",
            "start_date",
            "payment_start_date",
            "expected_end_date",
            "term_months",
            "principal_amount",
            "rate_type",
            "payment_frequency",
            "expense_subcategory_override",
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
            "cancellation_forecast_enabled",
            "cancellation_date",
            "cancellation_fee_amount",
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
        request = self.context.get("request")
        tracking_mode = attrs.get("tracking_mode", getattr(self.instance, "tracking_mode", None))
        accounting_account_id = attrs.get("accounting_account_id")
        category = attrs.get("category", getattr(self.instance, "category", None))
        annual_interest_tae = attrs.get(
            "annual_interest_tae", getattr(self.instance, "annual_interest_tae", None)
        )
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        payment_start_date = attrs.get(
            "payment_start_date",
            getattr(self.instance, "payment_start_date", None),
        )
        expected_end_date = attrs.get(
            "expected_end_date", getattr(self.instance, "expected_end_date", None)
        )
        payment_frequency = attrs.get(
            "payment_frequency", getattr(self.instance, "payment_frequency", None)
        )
        term_months = attrs.get("term_months", getattr(self.instance, "term_months", None))
        cancellation_forecast_enabled = attrs.get(
            "cancellation_forecast_enabled",
            getattr(self.instance, "cancellation_forecast_enabled", False),
        )
        cancellation_date = attrs.get(
            "cancellation_date", getattr(self.instance, "cancellation_date", None)
        )
        cancellation_fee_amount = attrs.get(
            "cancellation_fee_amount", getattr(self.instance, "cancellation_fee_amount", None)
        )
        financed_asset = attrs.get("financed_asset", getattr(self.instance, "financed_asset", None))
        expense_subcategory_override = attrs.get(
            "expense_subcategory_override",
            getattr(self.instance, "expense_subcategory_override", None),
        )

        if category != Liability.Category.MORTGAGE:
            cancellation_forecast_enabled = False
            cancellation_date = None
            cancellation_fee_amount = None
            attrs["cancellation_forecast_enabled"] = False
            attrs["cancellation_date"] = None
            attrs["cancellation_fee_amount"] = None
        elif not cancellation_forecast_enabled:
            cancellation_date = None
            cancellation_fee_amount = None
            attrs["cancellation_date"] = None
            attrs["cancellation_fee_amount"] = None

        if financed_asset is not None or category == Liability.Category.MORTGAGE:
            expense_subcategory_override = None
            attrs["expense_subcategory_override"] = None

        validate_liability_payload(
            tracking_mode=tracking_mode,
            accounting_account_id=accounting_account_id,
            category=category,
            annual_interest_tae=annual_interest_tae,
            start_date=start_date,
            payment_start_date=payment_start_date,
            expected_end_date=expected_end_date,
            payment_frequency=payment_frequency,
            term_months=term_months,
            cancellation_forecast_enabled=cancellation_forecast_enabled,
            cancellation_date=cancellation_date,
            cancellation_fee_amount=cancellation_fee_amount,
            expense_subcategory_override=expense_subcategory_override,
            financed_asset=financed_asset,
            user_id=getattr(getattr(request, "user", None), "id", None),
            current_liability_id=getattr(self.instance, "id", None),
            currency=attrs.get("currency", getattr(self.instance, "currency", None)),
        )

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

    def get_accounting_integration_state(self, obj):
        cached_state = getattr(obj, "_accounting_integration_state", None)
        if cached_state in {
            LiabilityAccountingIntegrationState.LINKED,
            LiabilityAccountingIntegrationState.AUTO_CREATED,
            LiabilityAccountingIntegrationState.NEEDS_REVIEW,
        }:
            return cached_state
        state = ensure_liability_accounting_account(liability=obj)
        if state in {
            LiabilityAccountingIntegrationState.LINKED,
            LiabilityAccountingIntegrationState.AUTO_CREATED,
            LiabilityAccountingIntegrationState.NEEDS_REVIEW,
        }:
            return state
        return None

    def create(self, validated_data):
        request = self.context["request"]
        if (
            validated_data.get("principal_amount") is None
            and validated_data.get("term_months")
            and validated_data.get("amount") is not None
        ):
            validated_data["principal_amount"] = validated_data["amount"]
        liability = create_liability_for_user(user=request.user, validated_data=validated_data)
        liability._accounting_integration_state = ensure_liability_accounting_account(
            liability=liability
        )
        self._ensure_accounting_opening_balance(liability=liability)
        return liability

    def update(self, instance, validated_data):
        liability = super().update(instance, validated_data)
        liability._accounting_integration_state = ensure_liability_accounting_account(
            liability=liability
        )
        self._ensure_accounting_opening_balance(liability=liability)
        return liability

    def _ensure_accounting_opening_balance(self, *, liability: Liability) -> None:
        if liability.tracking_mode != Liability.TrackingMode.ACCOUNTING:
            return
        account = get_user_ledger_account(
            user_id=liability.user_id,
            account_id=liability.accounting_account_id,
        )
        if account is None:
            return
        opening_date = liability.start_date or timezone.localdate()
        opening_amount = liability.amount
        sync_net_worth_opening_balance_transaction(
            user=liability.user,
            account=account,
            amount=opening_amount,
            booking_date=opening_date,
            liability=liability,
        )


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


class AssetValuationSerializer(serializers.ModelSerializer):
    asset_id = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects.none(),
        source="asset",
        write_only=True,
    )
    asset_ref = serializers.IntegerField(source="asset_id", read_only=True)
    asset_detail = AssetMiniSerializer(source="asset", read_only=True)

    class Meta:
        model = AssetValuation
        fields = [
            "id",
            "asset_id",
            "asset_ref",
            "asset_detail",
            "valuation_date",
            "value",
            "source",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        asset_queryset = self.context.get("asset_queryset")
        if asset_queryset is not None:
            self.fields["asset_id"].queryset = asset_queryset

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["user"] = request.user
        return super().create(validated_data)


class InvestmentAssetEventSerializer(serializers.ModelSerializer):
    asset_id = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects.none(),
        source="asset",
        write_only=True,
    )
    asset_ref = serializers.IntegerField(source="asset_id", read_only=True)
    asset_detail = AssetMiniSerializer(source="asset", read_only=True)

    class Meta:
        model = InvestmentAssetEvent
        fields = [
            "id",
            "asset_id",
            "asset_ref",
            "asset_detail",
            "event_date",
            "event_type",
            "amount",
            "is_reinvested",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        asset_queryset = self.context.get("investment_asset_queryset")
        if asset_queryset is not None:
            self.fields["asset_id"].queryset = asset_queryset

    def validate(self, attrs):
        asset = attrs.get("asset", getattr(self.instance, "asset", None))
        event_type = attrs.get("event_type", getattr(self.instance, "event_type", None))
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        is_reinvested = attrs.get(
            "is_reinvested",
            getattr(self.instance, "is_reinvested", True),
        )
        validate_investment_asset_event_payload(
            asset=asset,
            event_date=attrs.get("event_date", getattr(self.instance, "event_date", None)),
            event_type=event_type,
            amount=amount,
            is_reinvested=is_reinvested,
        )
        if event_type != InvestmentAssetEvent.EventType.PASSIVE_INCOME:
            attrs["is_reinvested"] = True
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["user"] = request.user
        return super().create(validated_data)


class LiquidityAssetEventSerializer(serializers.ModelSerializer):
    asset_id = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects.none(),
        source="asset",
        write_only=True,
    )
    asset_ref = serializers.IntegerField(source="asset_id", read_only=True)
    asset_detail = AssetMiniSerializer(source="asset", read_only=True)

    class Meta:
        model = LiquidityAssetEvent
        fields = [
            "id",
            "asset_id",
            "asset_ref",
            "asset_detail",
            "event_date",
            "event_type",
            "amount",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        asset_queryset = self.context.get("liquidity_event_asset_queryset")
        if asset_queryset is not None:
            self.fields["asset_id"].queryset = asset_queryset

    def validate(self, attrs):
        validate_liquidity_asset_event_payload(
            asset=attrs.get("asset", getattr(self.instance, "asset", None)),
            event_date=attrs.get("event_date", getattr(self.instance, "event_date", None)),
            event_type=attrs.get("event_type", getattr(self.instance, "event_type", None)),
            amount=attrs.get("amount", getattr(self.instance, "amount", None)),
        )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["user"] = request.user
        return super().create(validated_data)


class LiabilityEventSerializer(serializers.ModelSerializer):
    liability_id = serializers.PrimaryKeyRelatedField(
        queryset=Liability.objects.none(),
        source="liability",
        write_only=True,
    )
    liability_ref = serializers.IntegerField(source="liability_id", read_only=True)
    liability_detail = serializers.SerializerMethodField()

    class Meta:
        model = LiabilityEvent
        fields = [
            "id",
            "liability_id",
            "liability_ref",
            "liability_detail",
            "event_date",
            "event_type",
            "amount",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        liability_queryset = self.context.get("liability_event_queryset")
        if liability_queryset is not None:
            self.fields["liability_id"].queryset = liability_queryset

    def get_liability_detail(self, obj):
        return {
            "id": obj.liability_id,
            "name": obj.liability.name,
            "category": obj.liability.category,
        }

    def validate(self, attrs):
        validate_liability_event_payload(
            liability=attrs.get("liability", getattr(self.instance, "liability", None)),
            event_date=attrs.get("event_date", getattr(self.instance, "event_date", None)),
            event_type=attrs.get("event_type", getattr(self.instance, "event_type", None)),
            amount=attrs.get("amount", getattr(self.instance, "amount", None)),
        )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["user"] = request.user
        return super().create(validated_data)


class LiabilityValuationSerializer(serializers.ModelSerializer):
    liability_id = serializers.PrimaryKeyRelatedField(
        queryset=Liability.objects.none(),
        source="liability",
        write_only=True,
    )
    liability_ref = serializers.IntegerField(source="liability_id", read_only=True)
    liability_detail = serializers.SerializerMethodField()

    class Meta:
        model = LiabilityValuation
        fields = [
            "id",
            "liability_id",
            "liability_ref",
            "liability_detail",
            "valuation_date",
            "value",
            "source",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        liability_queryset = self.context.get("liability_queryset")
        if liability_queryset is not None:
            self.fields["liability_id"].queryset = liability_queryset

    def get_liability_detail(self, obj):
        return {
            "id": obj.liability_id,
            "name": obj.liability.name,
            "category": obj.liability.category,
        }

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["user"] = request.user
        return super().create(validated_data)
