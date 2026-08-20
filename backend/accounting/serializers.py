from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from typing import cast

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from accounts.models import UserSettings
from budget.services import (
    validate_annual_expense_taxonomy,
    validate_annual_income_taxonomy,
)
from core.services import build_fx_cache, convert_currency_cached
from memberships.models import Ownership
from net_worth.models import Asset, Liability

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .services_ledger import (
    get_account_balance,
    get_or_create_system_account,
    normalize_currency_code,
    validate_counterparty_account_type,
    validate_liquidity_account,
)
from .services_quick_entry import create_quick_transaction
from .services_start_dates import sync_position_start_dates_for_transaction
from .services_transactions import (
    classify_transaction_activity_kind,
    transaction_needs_review,
    validate_booking_and_value_dates,
    validate_transaction_entries,
)


def _context_user(context: dict):
    request = context.get("request")
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return user


def _scope_queryset_to_context_user(*, context: dict, base_queryset):
    user = _context_user(context)
    if user is None:
        return base_queryset.none()
    return base_queryset.filter(user=user)


class LedgerAccountSerializer(serializers.ModelSerializer):
    asset_id = serializers.PrimaryKeyRelatedField(
        source="asset",
        queryset=Asset.objects.all(),
        allow_null=True,
        required=False,
    )
    liability_id = serializers.PrimaryKeyRelatedField(
        source="liability",
        queryset=Liability.objects.all(),
        allow_null=True,
        required=False,
    )
    current_balance = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = LedgerAccount
        fields = [
            "id",
            "name",
            "display_name",
            "account_type",
            "currency",
            "origin",
            "asset_id",
            "liability_id",
            "is_active",
            "notes",
            "current_balance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "display_name", "current_balance", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        fields["asset_id"].queryset = _scope_queryset_to_context_user(
            context=self.context,
            base_queryset=Asset.objects.all(),
        )
        fields["liability_id"].queryset = _scope_queryset_to_context_user(
            context=self.context,
            base_queryset=Liability.objects.all(),
        )
        return fields

    def get_current_balance(self, obj: LedgerAccount) -> str:
        # En listados el viewset precalcula todos los saldos en una sola query
        # agregada; el fallback por cuenta queda para respuestas individuales.
        balances_by_id = self.context.get("account_balances_by_id")
        if balances_by_id is not None:
            return str(balances_by_id.get(obj.id, Decimal("0")))
        return str(
            get_account_balance(account=obj, status=cast(str, LedgerTransaction.Status.POSTED))
        )

    def get_display_name(self, obj: LedgerAccount) -> str:
        if obj.asset_id and obj.asset and obj.asset.name:
            return obj.asset.name
        if obj.liability_id and obj.liability and obj.liability.name:
            return obj.liability.name
        return obj.name

    def validate_currency(self, value: str) -> str:
        normalized = normalize_currency_code(value)
        if len(normalized) != 3:
            raise serializers.ValidationError("Moneda invalida. Usa codigos ISO de 3 letras.")
        return normalized

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        asset = attrs.get("asset", getattr(self.instance, "asset", None))
        liability = attrs.get("liability", getattr(self.instance, "liability", None))
        account_type = attrs.get("account_type", getattr(self.instance, "account_type", None))
        currency = attrs.get("currency", getattr(self.instance, "currency", ""))

        if asset is not None and liability is not None:
            raise serializers.ValidationError(
                {
                    "liability_id": "Una cuenta no puede vincularse a un activo y a un pasivo a la vez."
                }
            )
        if asset is not None:
            if user is not None and asset.user_id != user.id:
                raise serializers.ValidationError(
                    {"asset_id": "El activo no pertenece al usuario autenticado."}
                )
            if account_type != LedgerAccount.AccountType.ASSET:
                raise serializers.ValidationError(
                    {"account_type": "Las cuentas ligadas a activos deben ser de tipo asset."}
                )
            if currency != asset.currency:
                raise serializers.ValidationError(
                    {"currency": "La moneda de la cuenta debe coincidir con la del activo."}
                )
        if liability is not None:
            if user is not None and liability.user_id != user.id:
                raise serializers.ValidationError(
                    {"liability_id": "El pasivo no pertenece al usuario autenticado."}
                )
            if account_type != LedgerAccount.AccountType.LIABILITY:
                raise serializers.ValidationError(
                    {"account_type": "Las cuentas ligadas a pasivos deben ser de tipo liability."}
                )
            if currency != liability.currency:
                raise serializers.ValidationError(
                    {"currency": "La moneda de la cuenta debe coincidir con la del pasivo."}
                )
        return attrs

    def create(self, validated_data: dict) -> LedgerAccount:
        request = self.context["request"]
        return LedgerAccount.objects.create(user=request.user, **validated_data)


class LedgerEntrySerializer(serializers.ModelSerializer):
    account_id = serializers.PrimaryKeyRelatedField(
        source="account",
        queryset=LedgerAccount.objects.all(),
    )
    asset_id = serializers.PrimaryKeyRelatedField(
        source="asset",
        queryset=Asset.objects.all(),
        allow_null=True,
        required=False,
    )
    liability_id = serializers.PrimaryKeyRelatedField(
        source="liability",
        queryset=Liability.objects.all(),
        allow_null=True,
        required=False,
    )
    account_name = serializers.CharField(source="account.name", read_only=True)
    amount_base = serializers.SerializerMethodField()
    flow_family = serializers.ChoiceField(
        choices=LedgerEntry.FlowFamily.choices,
        allow_blank=True,
        required=False,
    )
    category_key = serializers.CharField(
        max_length=64,
        allow_blank=True,
        required=False,
    )
    subcategory_key = serializers.CharField(
        max_length=64,
        allow_blank=True,
        required=False,
    )

    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "account_id",
            "account_name",
            "side",
            "amount",
            "amount_base",
            "currency",
            "flow_family",
            "category_key",
            "subcategory_key",
            "asset_id",
            "liability_id",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "account_name", "amount_base"]

    def get_fields(self):
        fields = super().get_fields()
        fields["account_id"].queryset = _scope_queryset_to_context_user(
            context=self.context,
            base_queryset=LedgerAccount.objects.all(),
        )
        fields["asset_id"].queryset = _scope_queryset_to_context_user(
            context=self.context,
            base_queryset=Asset.objects.all(),
        )
        fields["liability_id"].queryset = _scope_queryset_to_context_user(
            context=self.context,
            base_queryset=Liability.objects.all(),
        )
        return fields

    def get_amount_base(self, obj: LedgerEntry) -> str:
        base_currency = self.context.get("base_currency")
        if not isinstance(base_currency, str):
            request = self.context.get("request")
            user = getattr(request, "user", None)
            base_currency = (
                UserSettings.objects.filter(user_id=user.id)
                .values_list("base_currency", flat=True)
                .first()
                if user is not None
                else None
            )
            base_currency = str(base_currency or "EUR").strip().upper()
            self.context["base_currency"] = base_currency
        base_currency = str(base_currency or "EUR").strip().upper()
        entry_currency = str(obj.currency or base_currency).strip().upper()
        if entry_currency == base_currency:
            return str(obj.amount.quantize(Decimal("0.01")))

        fx_cache = self.context.get("fx_cache")
        if not isinstance(fx_cache, dict):
            fx_cache = build_fx_cache({entry_currency, base_currency, "USD"})
            self.context["fx_cache"] = fx_cache
        try:
            converted = convert_currency_cached(
                obj.amount,
                entry_currency,
                base_currency,
                rate_date=obj.transaction.booking_date,
                fx_cache=fx_cache,
            )
        except DjangoValidationError:
            return str(obj.amount)
        return str(converted)

    def validate_currency(self, value: str) -> str:
        normalized = normalize_currency_code(value)
        if len(normalized) != 3:
            raise serializers.ValidationError("Moneda invalida. Usa codigos ISO de 3 letras.")
        return normalized

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        account = attrs.get("account", getattr(self.instance, "account", None))
        asset = attrs.get("asset", getattr(self.instance, "asset", None))
        liability = attrs.get("liability", getattr(self.instance, "liability", None))
        flow_family = attrs.get("flow_family", getattr(self.instance, "flow_family", ""))
        category_key = attrs.get("category_key", getattr(self.instance, "category_key", ""))
        subcategory_key = attrs.get(
            "subcategory_key", getattr(self.instance, "subcategory_key", "")
        )

        for field_name, value in (
            ("account_id", account),
            ("asset_id", asset),
            ("liability_id", liability),
        ):
            if value is not None and user is not None and value.user_id != user.id:
                raise serializers.ValidationError(
                    {field_name: "La referencia no pertenece al usuario autenticado."}
                )

        has_flow_family = bool(flow_family)
        has_category_key = bool(category_key)
        has_subcategory_key = bool(subcategory_key)
        if has_flow_family or has_category_key or has_subcategory_key:
            if not (has_flow_family and has_category_key and has_subcategory_key):
                raise serializers.ValidationError(
                    {
                        "subcategory_key": (
                            "flow_family, category_key y subcategory_key deben informarse juntos."
                        )
                    }
                )
        return attrs


class LedgerTransactionSerializer(serializers.ModelSerializer):
    entries = LedgerEntrySerializer(many=True)
    activity_kind = serializers.SerializerMethodField()
    account_balance_after = serializers.SerializerMethodField()
    needs_review = serializers.SerializerMethodField()
    ownership_id = serializers.PrimaryKeyRelatedField(
        source="ownership",
        queryset=Ownership.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = LedgerTransaction
        fields = [
            "id",
            "booking_date",
            "value_date",
            "description",
            "status",
            "origin",
            "member_tag",
            "notes",
            "import_source",
            "import_fingerprint",
            "ownership_id",
            "quick_entry_kind",
            "investment_direction",
            "investment_units",
            "investment_unit_price",
            "realized_cost_basis",
            "realized_gain_loss",
            "activity_kind",
            "account_balance_after",
            "needs_review",
            "entries",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "import_source",
            "import_fingerprint",
            "realized_cost_basis",
            "realized_gain_loss",
            "created_at",
            "updated_at",
        ]

    def get_fields(self):
        fields = super().get_fields()
        if self.context.get("include_entries") is False:
            fields.pop("entries", None)
        fields["ownership_id"].queryset = _scope_queryset_to_context_user(
            context=self.context,
            base_queryset=Ownership.objects.all(),
        )
        return fields

    def get_activity_kind(self, obj: LedgerTransaction) -> str:
        return classify_transaction_activity_kind(obj)

    def get_account_balance_after(self, obj: LedgerTransaction) -> str | None:
        by_tx_id = self.context.get("account_balance_after_by_tx_id")
        if not isinstance(by_tx_id, dict):
            return None
        value = by_tx_id.get(obj.id)
        return str(value) if value is not None else None

    def get_needs_review(self, obj: LedgerTransaction) -> bool:
        return transaction_needs_review(obj)

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        ownership = attrs.get("ownership", getattr(self.instance, "ownership", None))
        if ownership is not None and user is not None and ownership.user_id != user.id:
            raise serializers.ValidationError(
                {"ownership_id": "La titularidad no pertenece al usuario autenticado."}
            )

        booking_date = attrs.get("booking_date", getattr(self.instance, "booking_date", None))
        value_date = attrs.get("value_date", getattr(self.instance, "value_date", None))
        if booking_date is not None and value_date is not None:
            validate_booking_and_value_dates(booking_date=booking_date, value_date=value_date)
        return attrs

    @transaction.atomic
    def create(self, validated_data: dict) -> LedgerTransaction:
        entries_data = validated_data.pop("entries")
        request = self.context["request"]
        quick_entry_kind = validated_data.get("quick_entry_kind", "")
        allow_unbalanced_multicurrency = self._allow_unbalanced_multicurrency_create(
            incoming_entries=entries_data,
            quick_entry_kind=quick_entry_kind,
        )
        validate_transaction_entries(
            entries_data=entries_data,
            user_id=request.user.id,
            allow_unbalanced_multicurrency=allow_unbalanced_multicurrency,
        )
        transaction = LedgerTransaction.objects.create(user=request.user, **validated_data)
        for entry_data in entries_data:
            payload = {**entry_data}
            payload["currency"] = payload.get("currency") or payload["account"].currency
            LedgerEntry.objects.create(transaction=transaction, **payload)
        sync_position_start_dates_for_transaction(transaction=transaction)
        return transaction

    @transaction.atomic
    def update(self, instance: LedgerTransaction, validated_data: dict) -> LedgerTransaction:
        entries_data = validated_data.pop("entries", None)
        target_quick_entry_kind = validated_data.get("quick_entry_kind", instance.quick_entry_kind)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if entries_data is not None:
            request = self.context["request"]
            existing_entries = list(instance.entries.select_related("account").all())
            allow_unbalanced_multicurrency = self._allow_unbalanced_multicurrency_update(
                existing_entries=existing_entries,
                incoming_entries=entries_data,
                quick_entry_kind=target_quick_entry_kind,
            )
            validate_transaction_entries(
                entries_data=entries_data,
                user_id=request.user.id,
                allow_unbalanced_multicurrency=allow_unbalanced_multicurrency,
            )
            instance.entries.all().delete()
            for entry_data in entries_data:
                payload = {**entry_data}
                payload["currency"] = payload.get("currency") or payload["account"].currency
                LedgerEntry.objects.create(transaction=instance, **payload)
        sync_position_start_dates_for_transaction(transaction=instance)
        return instance

    @staticmethod
    def _entry_currency_from_payload(entry_data: dict) -> str:
        account = entry_data["account"]
        return str(entry_data.get("currency") or account.currency).strip().upper()

    @classmethod
    def _is_unbalanced_by_currency_from_existing(cls, entries: list[LedgerEntry]) -> bool:
        totals: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: {"debit": Decimal("0"), "credit": Decimal("0")}
        )
        for entry in entries:
            currency = str(entry.currency).strip().upper()
            totals[currency][entry.side] += entry.amount
        return any(values["debit"] != values["credit"] for values in totals.values())

    @classmethod
    def _is_unbalanced_by_currency_from_payload(cls, entries_data: list[dict]) -> bool:
        totals: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: {"debit": Decimal("0"), "credit": Decimal("0")}
        )
        for entry_data in entries_data:
            currency = cls._entry_currency_from_payload(entry_data)
            totals[currency][entry_data["side"]] += entry_data["amount"]
        return any(values["debit"] != values["credit"] for values in totals.values())

    @classmethod
    def _same_structure(
        cls, existing_entries: list[LedgerEntry], incoming_entries: list[dict]
    ) -> bool:
        if len(existing_entries) != len(incoming_entries):
            return False
        existing_signature = Counter(
            (
                entry.account_id,
                entry.side,
                str(entry.currency).strip().upper(),
            )
            for entry in existing_entries
        )
        incoming_signature = Counter(
            (
                entry_data["account"].id,
                entry_data["side"],
                cls._entry_currency_from_payload(entry_data),
            )
            for entry_data in incoming_entries
        )
        return existing_signature == incoming_signature

    @classmethod
    def _allow_unbalanced_multicurrency_update(
        cls,
        *,
        existing_entries: list[LedgerEntry],
        incoming_entries: list[dict],
        quick_entry_kind: str,
    ) -> bool:
        if not existing_entries or not incoming_entries:
            return False
        incoming_currencies = {
            cls._entry_currency_from_payload(entry) for entry in incoming_entries
        }
        if len(incoming_currencies) < 2:
            return False

        # Align update semantics with quick-entry create/edit:
        # investment and transfer movements can be naturally unbalanced per currency.
        if quick_entry_kind in {
            LedgerTransaction.QuickEntryKind.INVESTMENT,
            LedgerTransaction.QuickEntryKind.TRANSFER,
        } and cls._is_unbalanced_by_currency_from_payload(incoming_entries):
            return True

        # Backward-compatible lane for legacy mixed-currency rows.
        existing_currencies = {str(entry.currency).strip().upper() for entry in existing_entries}
        if len(existing_currencies) < 2:
            return False
        if not cls._is_unbalanced_by_currency_from_existing(existing_entries):
            return False
        if not cls._same_structure(existing_entries, incoming_entries):
            return False
        return cls._is_unbalanced_by_currency_from_payload(incoming_entries)

    @classmethod
    def _allow_unbalanced_multicurrency_create(
        cls,
        *,
        incoming_entries: list[dict],
        quick_entry_kind: str,
    ) -> bool:
        incoming_currencies = {
            cls._entry_currency_from_payload(entry) for entry in incoming_entries
        }
        if len(incoming_currencies) < 2:
            return False
        if not cls._is_unbalanced_by_currency_from_payload(incoming_entries):
            return False

        if quick_entry_kind in {
            LedgerTransaction.QuickEntryKind.INVESTMENT,
            LedgerTransaction.QuickEntryKind.TRANSFER,
        }:
            return True

        # Legacy lane for imported rows without quick_entry_kind:
        # allow multicurrency asymmetry when shape maps to classic transfer/investment.
        has_income_like = any(
            entry.get("flow_family") == LedgerEntry.FlowFamily.INCOME for entry in incoming_entries
        )
        has_expense_like = any(
            entry.get("flow_family") == LedgerEntry.FlowFamily.EXPENSE for entry in incoming_entries
        )
        has_liability_link = any(entry.get("liability") is not None for entry in incoming_entries)
        asset_account_entries = sum(
            1
            for entry in incoming_entries
            if entry["account"].account_type == LedgerAccount.AccountType.ASSET
        )
        has_investment_shape = any(
            entry["account"].account_type == LedgerAccount.AccountType.ASSET
            and entry["account"].asset_id is not None
            for entry in incoming_entries
        )
        has_transfer_shape = (
            asset_account_entries >= 2
            and not has_income_like
            and not has_expense_like
            and not has_liability_link
        )
        return has_investment_shape or has_transfer_shape


class QuickLedgerTransactionSerializer(serializers.Serializer):
    movement_type = serializers.ChoiceField(
        choices=[
            "income",
            "expense",
            "transfer",
            "adjustment",
            "investment",
            "debt_payment",
            "revaluation",
        ]
    )
    investment_direction = serializers.ChoiceField(
        choices=LedgerTransaction.InvestmentDirection.choices,
        allow_blank=True,
        required=False,
    )
    booking_date = serializers.DateField(default=timezone.localdate)
    value_date = serializers.DateField(default=timezone.localdate)
    description = serializers.CharField(max_length=240)
    amount = serializers.DecimalField(max_digits=20, decimal_places=8)
    destination_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        allow_null=True,
        required=False,
    )
    account_id = serializers.PrimaryKeyRelatedField(
        source="account",
        queryset=LedgerAccount.objects.select_related("asset"),
    )
    ownership_id = serializers.PrimaryKeyRelatedField(
        source="ownership",
        queryset=Ownership.objects.all(),
        allow_null=True,
        required=False,
    )
    counterparty_account_id = serializers.PrimaryKeyRelatedField(
        source="counterparty_account",
        queryset=LedgerAccount.objects.select_related("asset", "liability"),
        allow_null=True,
        required=False,
    )
    liability_account_id = serializers.PrimaryKeyRelatedField(
        source="liability_account",
        queryset=LedgerAccount.objects.select_related("liability"),
        allow_null=True,
        required=False,
    )
    interest_account_id = serializers.PrimaryKeyRelatedField(
        source="interest_account",
        queryset=LedgerAccount.objects.select_related("liability"),
        allow_null=True,
        required=False,
    )
    principal_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        allow_null=True,
        required=False,
    )
    interest_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        allow_null=True,
        required=False,
    )
    realized_cost_basis = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        allow_null=True,
        required=False,
    )
    realized_gain_loss = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        allow_null=True,
        required=False,
    )
    # Detalle de la operación para posiciones seguidas por unidades: sin esto, registrar
    # una compra desde Contabilidad perdía el rastro de cuántas unidades movió.
    investment_units = serializers.DecimalField(
        max_digits=28,
        decimal_places=12,
        allow_null=True,
        required=False,
    )
    investment_unit_price = serializers.DecimalField(
        max_digits=28,
        decimal_places=12,
        allow_null=True,
        required=False,
    )
    # La comisión del broker, que se registra como gasto propio vinculado al movimiento.
    fee_amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=8,
        allow_null=True,
        required=False,
    )
    flow_family = serializers.ChoiceField(
        choices=LedgerEntry.FlowFamily.choices,
        allow_blank=True,
        required=False,
    )
    category_key = serializers.CharField(
        max_length=64,
        allow_blank=True,
        required=False,
    )
    subcategory_key = serializers.CharField(
        max_length=64,
        allow_blank=True,
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=LedgerTransaction.Status.choices,
        default=LedgerTransaction.Status.POSTED,
    )
    origin = serializers.ChoiceField(
        choices=LedgerTransaction.Origin.choices,
        default=LedgerTransaction.Origin.MANUAL,
    )

    def get_fields(self):
        fields = super().get_fields()
        ledger_accounts = _scope_queryset_to_context_user(
            context=self.context,
            base_queryset=LedgerAccount.objects.select_related("asset", "liability"),
        )
        fields["account_id"].queryset = ledger_accounts.select_related("asset")
        fields["counterparty_account_id"].queryset = ledger_accounts
        fields["liability_account_id"].queryset = ledger_accounts.select_related("liability")
        fields["interest_account_id"].queryset = ledger_accounts.select_related("liability")
        fields["ownership_id"].queryset = _scope_queryset_to_context_user(
            context=self.context,
            base_queryset=Ownership.objects.all(),
        )
        return fields

    def validate(self, attrs: dict) -> dict:
        request = self.context["request"]
        user = request.user
        ownership = attrs.get("ownership")
        movement_type = attrs["movement_type"]
        investment_direction = attrs.get("investment_direction", "")
        amount = attrs["amount"]
        destination_amount = attrs.get("destination_amount")
        account = attrs["account"]
        counterparty_account = attrs.get("counterparty_account")
        liability_account = attrs.get("liability_account")
        interest_account = attrs.get("interest_account")
        flow_family = attrs.get("flow_family", "")
        category_key = attrs.get("category_key", "")
        subcategory_key = attrs.get("subcategory_key", "")
        principal_amount = attrs.get("principal_amount")
        interest_amount = attrs.get("interest_amount")
        realized_cost_basis = attrs.get("realized_cost_basis")
        realized_gain_loss = attrs.get("realized_gain_loss")

        if ownership is not None and ownership.user_id != user.id:
            raise serializers.ValidationError(
                {"ownership_id": "La titularidad no pertenece al usuario autenticado."}
            )

        movement_type, investment_direction = self._normalize_investment_payload(
            movement_type=movement_type,
            investment_direction=investment_direction,
        )
        attrs["movement_type"] = movement_type
        attrs["investment_direction"] = investment_direction

        self._apply_canonical_classification_policy(
            attrs=attrs,
            movement_type=movement_type,
            investment_direction=investment_direction,
            liability_account=liability_account,
        )
        self._infer_missing_flow_family(
            attrs=attrs,
            movement_type=movement_type,
            interest_amount=interest_amount or Decimal("0"),
        )
        flow_family = attrs.get("flow_family", "")
        category_key = attrs.get("category_key", "")
        subcategory_key = attrs.get("subcategory_key", "")

        validate_booking_and_value_dates(
            booking_date=attrs["booking_date"],
            value_date=attrs["value_date"],
        )
        if movement_type in {"income", "expense"}:
            self._validate_income_expense_origin_account(
                movement_type=movement_type,
                account=account,
                user_id=user.id,
            )
        else:
            requires_liquidity_origin = movement_type not in {
                "transfer",
                "adjustment",
                "investment",
                "revaluation",
            }
            if requires_liquidity_origin:
                validate_liquidity_account(
                    account=account, user_id=user.id, field_name="account_id"
                )

        inferred_flow_family = self._infer_flow_family(
            movement_type=movement_type,
            interest_amount=interest_amount,
        )
        if (category_key or subcategory_key) and not flow_family and inferred_flow_family:
            attrs["flow_family"] = inferred_flow_family
            flow_family = inferred_flow_family
        self._validate_functional_classification(
            flow_family=flow_family,
            category_key=category_key,
            subcategory_key=subcategory_key,
        )
        if movement_type == "income" and flow_family == LedgerEntry.FlowFamily.EXPENSE:
            raise serializers.ValidationError(
                {"flow_family": "No aplica a movimientos de ingreso."}
            )
        if (
            movement_type in {"expense", "debt_payment"}
            and flow_family == LedgerEntry.FlowFamily.INCOME
        ):
            raise serializers.ValidationError({"flow_family": "No aplica a movimientos de gasto."})
        if (
            movement_type == "investment"
            and investment_direction == LedgerTransaction.InvestmentDirection.INFLOW
            and flow_family == LedgerEntry.FlowFamily.INCOME
        ):
            raise serializers.ValidationError(
                {"flow_family": "Las inversiones solo pueden clasificarse como gasto."}
            )
        if (
            movement_type == "investment"
            and investment_direction == LedgerTransaction.InvestmentDirection.REINVESTMENT
            and (flow_family or category_key or subcategory_key)
        ):
            raise serializers.ValidationError(
                {
                    "flow_family": (
                        "La reinversion entre cuentas de inversion no admite clasificacion funcional."
                    )
                }
            )
        if movement_type in {"transfer", "adjustment", "revaluation"} and (
            flow_family or category_key or subcategory_key
        ):
            raise serializers.ValidationError(
                {
                    "flow_family": (
                        "No aplica a transferencias internas, ajustes ni revalorizaciones."
                    )
                }
            )
        self._validate_investment_metadata(
            movement_type=movement_type,
            realized_cost_basis=realized_cost_basis,
            realized_gain_loss=realized_gain_loss,
        )
        self._validate_investment_fee(
            movement_type=movement_type,
            fee_amount=attrs.get("fee_amount"),
        )
        self._validate_destination_amount_contract(
            movement_type=movement_type,
            amount=amount,
            destination_amount=destination_amount,
        )
        self._validate_required_category_contract(
            movement_type=movement_type,
            investment_direction=investment_direction,
            category_key=category_key,
            subcategory_key=subcategory_key,
            interest_amount=interest_amount,
        )
        self._validate_category_taxonomy(
            flow_family=flow_family,
            category_key=category_key,
            subcategory_key=subcategory_key,
        )

        if movement_type == "income":
            self._validate_income_movement(
                attrs=attrs,
                user_id=user.id,
                account=account,
                counterparty_account=counterparty_account,
            )
        elif movement_type == "expense":
            self._validate_expense_movement(
                attrs=attrs,
                user_id=user.id,
                account=account,
                counterparty_account=counterparty_account,
            )
        elif movement_type == "transfer":
            self._validate_transfer_movement(
                user_id=user.id,
                account=account,
                counterparty_account=counterparty_account,
                destination_amount=destination_amount,
            )
        elif movement_type == "adjustment":
            self._validate_adjustment_movement(
                attrs=attrs,
                user_id=user.id,
                account=account,
                counterparty_account=counterparty_account,
            )
        elif movement_type == "investment":
            self._validate_investment_movement(
                attrs=attrs,
                user_id=user.id,
                account=account,
                counterparty_account=counterparty_account,
                investment_direction=investment_direction,
                destination_amount=destination_amount,
            )
        elif movement_type == "revaluation":
            self._validate_revaluation_movement(
                attrs=attrs,
                user_id=user.id,
                account=account,
            )
        else:
            self._validate_debt_payment_movement(
                attrs=attrs,
                user_id=user.id,
                amount=amount,
                account=account,
                liability_account=liability_account,
                interest_account=interest_account,
                principal_amount=principal_amount,
                interest_amount=interest_amount,
            )

        return attrs

    def _apply_canonical_classification_policy(
        self,
        *,
        attrs: dict,
        movement_type: str,
        investment_direction: str,
        liability_account: LedgerAccount | None,
    ) -> None:
        if movement_type in {"transfer", "adjustment", "revaluation"}:
            attrs["flow_family"] = ""
            attrs["category_key"] = ""
            attrs["subcategory_key"] = ""
            return

        if movement_type == "expense":
            return

        if movement_type == "investment":
            if investment_direction == LedgerTransaction.InvestmentDirection.OUTFLOW:
                attrs["flow_family"] = cast(str, LedgerEntry.FlowFamily.INCOME)
                attrs["category_key"] = "capital_gains"
                attrs["subcategory_key"] = "sale_financial_assets"
                return
            if investment_direction == LedgerTransaction.InvestmentDirection.REINVESTMENT:
                attrs["flow_family"] = ""
                attrs["category_key"] = ""
                attrs["subcategory_key"] = ""
                return
            return

        if movement_type != "debt_payment":
            return

        if liability_account is None or liability_account.liability is None:
            return
        liability_category = liability_account.liability.category
        if liability_category == Liability.Category.MORTGAGE:
            attrs["flow_family"] = cast(str, LedgerEntry.FlowFamily.EXPENSE)
            attrs["category_key"] = "real_estate_assets"
            attrs["subcategory_key"] = "mortgage_principal"
            return

    def _normalize_investment_payload(
        self,
        *,
        movement_type: str,
        investment_direction: str,
    ) -> tuple[str, str]:
        if movement_type != "investment":
            return movement_type, ""
        if not investment_direction:
            raise serializers.ValidationError(
                {"investment_direction": "Indica si es aporte, desinversion o reinversion."}
            )
        return movement_type, investment_direction

    def _validate_destination_amount_contract(
        self,
        *,
        movement_type: str,
        amount: Decimal,
        destination_amount: Decimal | None,
    ) -> None:
        if movement_type not in {"investment", "transfer"}:
            if destination_amount is not None:
                raise serializers.ValidationError(
                    {
                        "destination_amount": "Solo aplica a movimientos de inversion o transferencia."
                    }
                )
            return
        if amount <= 0:
            raise serializers.ValidationError({"amount": "Debe ser mayor que cero."})
        if destination_amount is not None and destination_amount <= 0:
            raise serializers.ValidationError(
                {"destination_amount": "Debe ser mayor que cero cuando se informa."}
            )

    def _validate_investment_metadata(
        self,
        *,
        movement_type: str,
        realized_cost_basis: Decimal | None,
        realized_gain_loss: Decimal | None,
    ) -> None:
        if movement_type == "investment":
            if realized_cost_basis is not None and realized_cost_basis < 0:
                raise serializers.ValidationError(
                    {"realized_cost_basis": "Debe ser mayor o igual que cero."}
                )
            return
        if realized_cost_basis is not None:
            raise serializers.ValidationError(
                {"realized_cost_basis": "Solo aplica a movimientos de inversion."}
            )
        if realized_gain_loss is not None:
            raise serializers.ValidationError(
                {"realized_gain_loss": "Solo aplica a movimientos de inversion."}
            )

    def _validate_investment_fee(
        self,
        *,
        movement_type: str,
        fee_amount: Decimal | None,
    ) -> None:
        if fee_amount is None:
            return
        if movement_type != "investment":
            raise serializers.ValidationError(
                {"fee_amount": "Solo aplica a movimientos de inversion."}
            )
        if fee_amount < 0:
            raise serializers.ValidationError({"fee_amount": "Debe ser mayor o igual que cero."})

    def _infer_flow_family(self, *, movement_type: str, interest_amount: Decimal | None) -> str:
        if movement_type == "income":
            return cast(str, LedgerEntry.FlowFamily.INCOME)
        if movement_type in {"expense", "debt_payment", "investment"}:
            return cast(str, LedgerEntry.FlowFamily.EXPENSE)
        return ""

    def _validate_required_category_contract(
        self,
        *,
        movement_type: str,
        investment_direction: str,
        category_key: str,
        subcategory_key: str,
        interest_amount: Decimal | None,
    ) -> None:
        has_classification = bool(category_key and subcategory_key)
        if movement_type == "income" and not has_classification:
            raise serializers.ValidationError(
                {"subcategory_key": "Categoria y subcategoria son obligatorias para ingresos."}
            )
        if movement_type == "expense" and not has_classification:
            raise serializers.ValidationError(
                {"subcategory_key": "Categoria y subcategoria son obligatorias para gastos."}
            )
        if movement_type == "debt_payment" and not has_classification:
            raise serializers.ValidationError(
                {
                    "subcategory_key": (
                        "Categoria y subcategoria son obligatorias para pagos de deuda."
                    )
                }
            )
        if movement_type == "debt_payment" and (interest_amount or Decimal("0")) > 0:
            if not has_classification:
                raise serializers.ValidationError(
                    {
                        "subcategory_key": (
                            "Cuando hay intereses debes informar categoria/subcategoria de gasto."
                        )
                    }
                )

    def _validate_income_expense_origin_account(
        self,
        *,
        movement_type: str,
        account: LedgerAccount,
        user_id: int,
    ) -> None:
        # Allow posting income/expense directly on liabilities (e.g., credit cards).
        if account.account_type == LedgerAccount.AccountType.LIABILITY:
            return

        if account.account_type != LedgerAccount.AccountType.ASSET:
            raise serializers.ValidationError(
                {"account_id": "La cuenta debe ser de tipo asset o liability."}
            )

        # Income can also target accounting investment assets for reinvested yield.
        if movement_type == "income" and account.asset_id is not None:
            return

        validate_liquidity_account(account=account, user_id=user_id, field_name="account_id")

    def _validate_functional_classification(
        self,
        *,
        flow_family: str,
        category_key: str,
        subcategory_key: str,
    ) -> None:
        has_flow_family = bool(flow_family)
        has_category_key = bool(category_key)
        has_subcategory_key = bool(subcategory_key)
        if has_flow_family or has_category_key or has_subcategory_key:
            if not (has_flow_family and has_category_key and has_subcategory_key):
                raise serializers.ValidationError(
                    {
                        "subcategory_key": (
                            "flow_family, category_key y subcategory_key deben informarse juntos."
                        )
                    }
                )

    def _validate_category_taxonomy(
        self,
        *,
        flow_family: str,
        category_key: str,
        subcategory_key: str,
    ) -> None:
        if not category_key and not subcategory_key:
            return
        if flow_family == LedgerEntry.FlowFamily.INCOME:
            try:
                validate_annual_income_taxonomy(category=category_key, subcategory=subcategory_key)
            except Exception as exc:
                raise serializers.ValidationError(
                    {"subcategory_key": "Subcategoria de ingreso no valida para la categoria dada."}
                ) from exc
            return
        if flow_family == LedgerEntry.FlowFamily.EXPENSE:
            try:
                validate_annual_expense_taxonomy(
                    category=category_key,
                    subcategory=subcategory_key,
                )
            except Exception as exc:
                raise serializers.ValidationError(
                    {"subcategory_key": "Subcategoria de gasto no valida para la categoria dada."}
                ) from exc

    def _infer_missing_flow_family(
        self,
        *,
        attrs: dict,
        movement_type: str,
        interest_amount: Decimal,
    ) -> None:
        category_key = attrs.get("category_key", "")
        subcategory_key = attrs.get("subcategory_key", "")
        flow_family = attrs.get("flow_family", "")
        if category_key and subcategory_key and not flow_family:
            attrs["flow_family"] = self._infer_flow_family(
                movement_type=movement_type,
                interest_amount=interest_amount,
            )

    def _validate_income_movement(
        self,
        *,
        attrs: dict,
        user_id: int,
        account: LedgerAccount,
        counterparty_account: LedgerAccount | None,
    ) -> None:
        if counterparty_account is not None:
            validate_counterparty_account_type(
                account=counterparty_account,
                user_id=user_id,
                expected_type=cast(str, LedgerAccount.AccountType.INCOME),
                field_name="counterparty_account_id",
            )
            return
        attrs["counterparty_account"] = get_or_create_system_account(
            user_id=user_id,
            account_type=cast(str, LedgerAccount.AccountType.INCOME),
            currency=account.currency,
            name="Ingresos sin categoria",
        )

    def _validate_expense_movement(
        self,
        *,
        attrs: dict,
        user_id: int,
        account: LedgerAccount,
        counterparty_account: LedgerAccount | None,
    ) -> None:
        if counterparty_account is not None:
            validate_counterparty_account_type(
                account=counterparty_account,
                user_id=user_id,
                expected_type=cast(str, LedgerAccount.AccountType.EXPENSE),
                field_name="counterparty_account_id",
            )
            return
        attrs["counterparty_account"] = get_or_create_system_account(
            user_id=user_id,
            account_type=cast(str, LedgerAccount.AccountType.EXPENSE),
            currency=account.currency,
            name="Gastos sin categoria",
        )

    def _validate_transfer_movement(
        self,
        *,
        user_id: int,
        account: LedgerAccount,
        counterparty_account: LedgerAccount | None,
        destination_amount: Decimal | None,
    ) -> None:
        self._validate_transfer_account(
            account=account,
            user_id=user_id,
            field_name="account_id",
        )
        self._validate_transfer_account(
            account=counterparty_account,
            user_id=user_id,
            field_name="counterparty_account_id",
        )
        if account.id == counterparty_account.id:
            raise serializers.ValidationError(
                {"counterparty_account_id": "La cuenta destino debe ser distinta a la origen."}
            )
        if account.currency != counterparty_account.currency and destination_amount is None:
            raise serializers.ValidationError(
                {
                    "destination_amount": (
                        "Indica el importe destino cuando origen y destino usan distinta moneda."
                    )
                }
            )

    def _validate_transfer_account(
        self,
        *,
        account: LedgerAccount | None,
        user_id: int,
        field_name: str,
    ) -> None:
        if account is None:
            raise serializers.ValidationError({field_name: "La cuenta es obligatoria."})
        if account.user_id != user_id:
            raise serializers.ValidationError(
                {field_name: "La cuenta no pertenece al usuario autenticado."}
            )
        if account.account_type == LedgerAccount.AccountType.LIABILITY:
            if account.liability_id is None:
                raise serializers.ValidationError(
                    {
                        field_name: (
                            "La transferencia con pasivos requiere una cuenta vinculada a pasivo."
                        )
                    }
                )
            return
        validate_liquidity_account(account=account, user_id=user_id, field_name=field_name)

    def _validate_adjustment_movement(
        self,
        *,
        attrs: dict,
        user_id: int,
        account: LedgerAccount,
        counterparty_account: LedgerAccount | None,
    ) -> None:
        if account.account_type not in {
            LedgerAccount.AccountType.ASSET,
            LedgerAccount.AccountType.LIABILITY,
        }:
            raise serializers.ValidationError(
                {
                    "account_id": (
                        "El ajuste de conciliacion solo admite cuentas de tipo asset o liability."
                    )
                }
            )
        if counterparty_account is not None:
            validate_counterparty_account_type(
                account=counterparty_account,
                user_id=user_id,
                expected_type=cast(str, LedgerAccount.AccountType.EQUITY),
                field_name="counterparty_account_id",
            )
        else:
            counterparty_account = get_or_create_system_account(
                user_id=user_id,
                account_type=cast(str, LedgerAccount.AccountType.EQUITY),
                currency=account.currency,
                name="Ajustes de conciliacion",
            )
            attrs["counterparty_account"] = counterparty_account

        if account.id == counterparty_account.id:
            raise serializers.ValidationError(
                {"counterparty_account_id": "La contracuenta de ajuste debe ser distinta."}
            )
        if account.currency != counterparty_account.currency:
            raise serializers.ValidationError(
                {
                    "counterparty_account_id": (
                        "El ajuste de conciliacion exige la misma moneda en ambas cuentas."
                    )
                }
            )

    def _validate_investment_movement(
        self,
        *,
        attrs: dict,
        user_id: int,
        account: LedgerAccount,
        counterparty_account: LedgerAccount | None,
        investment_direction: str,
        destination_amount: Decimal | None,
    ) -> None:
        if investment_direction not in {
            LedgerTransaction.InvestmentDirection.INFLOW,
            LedgerTransaction.InvestmentDirection.OUTFLOW,
            LedgerTransaction.InvestmentDirection.REINVESTMENT,
        }:
            raise serializers.ValidationError(
                {"investment_direction": "Indica si es aporte, desinversion o reinversion."}
            )
        validate_counterparty_account_type(
            account=counterparty_account,
            user_id=user_id,
            expected_type=cast(str, LedgerAccount.AccountType.ASSET),
            field_name="counterparty_account_id",
        )
        if account.id == counterparty_account.id:
            raise serializers.ValidationError(
                {
                    "counterparty_account_id": (
                        "La cuenta de destino debe ser distinta de la cuenta origen."
                    )
                }
            )
        if investment_direction == LedgerTransaction.InvestmentDirection.REINVESTMENT:
            if account.asset_id is None:
                raise serializers.ValidationError(
                    {
                        "account_id": (
                            "La reinversion requiere que la cuenta origen sea una cuenta de inversion."
                        )
                    }
                )
            if counterparty_account.asset_id is None:
                raise serializers.ValidationError(
                    {
                        "counterparty_account_id": (
                            "La reinversion requiere que la cuenta destino sea una cuenta de inversion."
                        )
                    }
                )
            if account.asset.category != Asset.Category.INVESTMENTS:
                raise serializers.ValidationError(
                    {
                        "account_id": (
                            "La reinversion solo admite cuentas ligadas a activos de categoria inversiones."
                        )
                    }
                )
            if counterparty_account.asset.category != Asset.Category.INVESTMENTS:
                raise serializers.ValidationError(
                    {
                        "counterparty_account_id": (
                            "La reinversion solo admite cuentas ligadas a activos de categoria inversiones."
                        )
                    }
                )
            origin_currency = account.currency
            destination_currency = counterparty_account.currency
        else:
            origin_currency = (
                counterparty_account.currency
                if investment_direction == LedgerTransaction.InvestmentDirection.OUTFLOW
                else account.currency
            )
            destination_currency = (
                account.currency
                if investment_direction == LedgerTransaction.InvestmentDirection.OUTFLOW
                else counterparty_account.currency
            )
        if origin_currency != destination_currency and destination_amount is None:
            raise serializers.ValidationError(
                {
                    "destination_amount": (
                        "Indica el importe destino cuando origen y destino usan distinta moneda."
                    )
                }
            )

        category_key = attrs.get("category_key", "")
        if category_key and investment_direction == LedgerTransaction.InvestmentDirection.INFLOW:
            if category_key not in {
                "financial_investments",
                "real_estate_assets",
                "tangible_assets",
            }:
                raise serializers.ValidationError(
                    {
                        "category_key": (
                            "Los aportes de inversion solo admiten categorias de inversion."
                        )
                    }
                )

    def _validate_revaluation_movement(
        self,
        *,
        attrs: dict,
        user_id: int,
        account: LedgerAccount,
    ) -> None:
        # Revaluations adjust an asset account value directly; no counterparty required.
        if attrs.get("counterparty_account") is None:
            attrs["counterparty_account"] = get_or_create_system_account(
                user_id=user_id,
                account_type=cast(str, LedgerAccount.AccountType.EXPENSE),
                currency=account.currency,
                name="Revalorizaciones",
            )

    def _validate_debt_payment_movement(
        self,
        *,
        attrs: dict,
        user_id: int,
        amount: Decimal,
        account: LedgerAccount,
        liability_account: LedgerAccount | None,
        interest_account: LedgerAccount | None,
        principal_amount: Decimal | None,
        interest_amount: Decimal | None,
    ) -> None:
        validate_counterparty_account_type(
            account=liability_account,
            user_id=user_id,
            expected_type=cast(str, LedgerAccount.AccountType.LIABILITY),
            field_name="liability_account_id",
        )
        if liability_account.liability_id is None:
            raise serializers.ValidationError(
                {
                    "liability_account_id": (
                        "La cuenta de pasivo debe estar vinculada a un pasivo concreto."
                    )
                }
            )
        principal = principal_amount
        if principal is None or principal <= 0:
            raise serializers.ValidationError(
                {"principal_amount": "Debe ser mayor que cero para pagos de deuda."}
            )

        interest = interest_amount or 0
        if interest < 0:
            raise serializers.ValidationError(
                {"interest_amount": "Debe ser mayor o igual que cero."}
            )
        if interest > 0:
            validate_counterparty_account_type(
                account=interest_account,
                user_id=user_id,
                expected_type=cast(str, LedgerAccount.AccountType.EXPENSE),
                field_name="interest_account_id",
            )
        elif interest_account is not None:
            raise serializers.ValidationError(
                {"interest_account_id": "Solo aplica cuando interest_amount es mayor que cero."}
            )

        if account.currency != liability_account.currency:
            raise serializers.ValidationError(
                {
                    "liability_account_id": (
                        "El pago de deuda exige la misma moneda entre liquidez y pasivo."
                    )
                }
            )
        if interest > 0 and account.currency != interest_account.currency:
            raise serializers.ValidationError(
                {
                    "interest_account_id": (
                        "La cuenta de interes debe usar la misma moneda que liquidez."
                    )
                }
            )
        if amount != principal + interest:
            raise serializers.ValidationError(
                {"amount": "Debe coincidir con principal_amount + interest_amount."}
            )

        attrs["counterparty_account"] = liability_account
        attrs["principal_amount"] = principal
        attrs["interest_amount"] = interest

    def create(self, validated_data: dict) -> LedgerTransaction:
        request = self.context["request"]
        return create_quick_transaction(user=request.user, **validated_data)
