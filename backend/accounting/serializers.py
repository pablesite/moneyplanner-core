from __future__ import annotations

from rest_framework import serializers

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from net_worth.models import Asset, Liability

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .services import (
    get_account_balance,
    normalize_currency_code,
    validate_booking_and_value_dates,
    validate_transaction_entries,
)


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

    class Meta:
        model = LedgerAccount
        fields = [
            "id",
            "name",
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
        read_only_fields = ["id", "current_balance", "created_at", "updated_at"]

    def get_current_balance(self, obj: LedgerAccount) -> str:
        return str(get_account_balance(account=obj))

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
    annual_income_entry_id = serializers.PrimaryKeyRelatedField(
        source="annual_income_entry",
        queryset=AnnualIncomeEntry.objects.all(),
        allow_null=True,
        required=False,
    )
    annual_expense_entry_id = serializers.PrimaryKeyRelatedField(
        source="annual_expense_entry",
        queryset=AnnualExpenseEntry.objects.all(),
        allow_null=True,
        required=False,
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

    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "account_id",
            "account_name",
            "side",
            "amount",
            "currency",
            "annual_income_entry_id",
            "annual_expense_entry_id",
            "asset_id",
            "liability_id",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "account_name"]

    def validate_currency(self, value: str) -> str:
        normalized = normalize_currency_code(value)
        if len(normalized) != 3:
            raise serializers.ValidationError("Moneda invalida. Usa codigos ISO de 3 letras.")
        return normalized

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        account = attrs.get("account", getattr(self.instance, "account", None))
        annual_income_entry = attrs.get(
            "annual_income_entry", getattr(self.instance, "annual_income_entry", None)
        )
        annual_expense_entry = attrs.get(
            "annual_expense_entry", getattr(self.instance, "annual_expense_entry", None)
        )
        asset = attrs.get("asset", getattr(self.instance, "asset", None))
        liability = attrs.get("liability", getattr(self.instance, "liability", None))

        if annual_income_entry is not None and annual_expense_entry is not None:
            raise serializers.ValidationError(
                {
                    "annual_expense_entry_id": (
                        "Un apunte no puede vincularse a una entrada anual de ingreso y gasto a la vez."
                    )
                }
            )
        for field_name, value in (
            ("account_id", account),
            ("annual_income_entry_id", annual_income_entry),
            ("annual_expense_entry_id", annual_expense_entry),
            ("asset_id", asset),
            ("liability_id", liability),
        ):
            if value is not None and user is not None and value.user_id != user.id:
                raise serializers.ValidationError(
                    {field_name: "La referencia no pertenece al usuario autenticado."}
                )
        return attrs


class LedgerTransactionSerializer(serializers.ModelSerializer):
    entries = LedgerEntrySerializer(many=True)

    class Meta:
        model = LedgerTransaction
        fields = [
            "id",
            "booking_date",
            "value_date",
            "description",
            "status",
            "origin",
            "notes",
            "entries",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs: dict) -> dict:
        booking_date = attrs.get("booking_date", getattr(self.instance, "booking_date", None))
        value_date = attrs.get("value_date", getattr(self.instance, "value_date", None))
        if booking_date is not None and value_date is not None:
            validate_booking_and_value_dates(booking_date=booking_date, value_date=value_date)
        return attrs

    def create(self, validated_data: dict) -> LedgerTransaction:
        entries_data = validated_data.pop("entries")
        request = self.context["request"]
        validate_transaction_entries(entries_data=entries_data, user_id=request.user.id)
        transaction = LedgerTransaction.objects.create(user=request.user, **validated_data)
        for entry_data in entries_data:
            payload = {**entry_data}
            payload["currency"] = payload.get("currency") or payload["account"].currency
            LedgerEntry.objects.create(transaction=transaction, **payload)
        return transaction

    def update(self, instance: LedgerTransaction, validated_data: dict) -> LedgerTransaction:
        entries_data = validated_data.pop("entries", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if entries_data is not None:
            request = self.context["request"]
            validate_transaction_entries(entries_data=entries_data, user_id=request.user.id)
            instance.entries.all().delete()
            for entry_data in entries_data:
                payload = {**entry_data}
                payload["currency"] = payload.get("currency") or payload["account"].currency
                LedgerEntry.objects.create(transaction=instance, **payload)
        return instance
