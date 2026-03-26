from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .services_ledger import ZERO
from .services_transactions import validate_booking_and_value_dates, validate_transaction_entries


@transaction.atomic
def create_quick_transaction(
    *,
    user,
    movement_type: str,
    booking_date: date,
    value_date: date,
    description: str,
    amount: Decimal,
    account: LedgerAccount,
    counterparty_account: LedgerAccount,
    status: str,
    origin: str,
    notes: str = "",
    import_source: str = "",
    import_fingerprint: str = "",
    member_tag: str = "",
    ownership=None,
    annual_income_entry=None,
    annual_expense_entry=None,
    flow_family: str = "",
    category_key: str = "",
    subcategory_key: str = "",
    principal_amount: Decimal | None = None,
    interest_amount: Decimal | None = None,
    liability_account: LedgerAccount | None = None,
    interest_account: LedgerAccount | None = None,
    investment_direction: str = "",
    destination_amount: Decimal | None = None,
    realized_cost_basis: Decimal | None = None,
    realized_gain_loss: Decimal | None = None,
) -> LedgerTransaction:
    normalized_movement_type = _normalize_quick_movement_type(movement_type)
    normalized_direction = _normalize_investment_direction(
        movement_type=normalized_movement_type,
        investment_direction=investment_direction,
    )
    payload = _build_quick_entry_payload(
        movement_type=normalized_movement_type,
        amount=amount,
        account=account,
        counterparty_account=counterparty_account,
        annual_income_entry=annual_income_entry,
        annual_expense_entry=annual_expense_entry,
        flow_family=flow_family,
        category_key=category_key,
        subcategory_key=subcategory_key,
        principal_amount=principal_amount,
        interest_amount=interest_amount,
        liability_account=liability_account,
        interest_account=interest_account,
        investment_direction=normalized_direction,
        destination_amount=destination_amount,
    )
    validate_booking_and_value_dates(booking_date=booking_date, value_date=value_date)
    allow_unbalanced_multicurrency = (
        normalized_movement_type == "investment"
        and account.currency.strip().upper() != counterparty_account.currency.strip().upper()
    )
    validate_transaction_entries(
        entries_data=payload,
        user_id=user.id,
        allow_unbalanced_multicurrency=allow_unbalanced_multicurrency,
    )

    transaction_row = LedgerTransaction.objects.create(
        user=user,
        booking_date=booking_date,
        value_date=value_date,
        description=description,
        status=status,
        origin=origin,
        notes=notes,
        import_source=import_source,
        import_fingerprint=import_fingerprint,
        member_tag=member_tag,
        ownership=ownership,
        quick_entry_kind=normalized_movement_type,
        investment_direction=normalized_direction,
        realized_cost_basis=(
            realized_cost_basis if normalized_movement_type == "investment" else None
        ),
        realized_gain_loss=realized_gain_loss if normalized_movement_type == "investment" else None,
    )
    for entry_data in payload:
        LedgerEntry.objects.create(transaction=transaction_row, **entry_data)
    return transaction_row


def _build_quick_entry_payload(
    *,
    movement_type: str,
    amount: Decimal,
    account: LedgerAccount,
    counterparty_account: LedgerAccount,
    annual_income_entry=None,
    annual_expense_entry=None,
    flow_family: str = "",
    category_key: str = "",
    subcategory_key: str = "",
    principal_amount: Decimal | None = None,
    interest_amount: Decimal | None = None,
    liability_account: LedgerAccount | None = None,
    interest_account: LedgerAccount | None = None,
    investment_direction: str = "",
    destination_amount: Decimal | None = None,
) -> list[dict]:
    base_amount = Decimal(amount)
    classification = _resolve_entry_classification(
        movement_type=movement_type,
        flow_family=flow_family,
        category_key=category_key,
        subcategory_key=subcategory_key,
        annual_income_entry=annual_income_entry,
        annual_expense_entry=annual_expense_entry,
    )
    if movement_type == "income":
        return [
            {
                "account": account,
                "side": LedgerEntry.Side.DEBIT,
                "amount": base_amount,
                "currency": account.currency,
            },
            {
                "account": counterparty_account,
                "side": LedgerEntry.Side.CREDIT,
                "amount": base_amount,
                "currency": counterparty_account.currency,
                "annual_income_entry": annual_income_entry,
                **classification,
            },
        ]
    if movement_type == "expense":
        return [
            {
                "account": counterparty_account,
                "side": LedgerEntry.Side.DEBIT,
                "amount": base_amount,
                "currency": counterparty_account.currency,
                "annual_expense_entry": annual_expense_entry,
                **classification,
            },
            {
                "account": account,
                "side": LedgerEntry.Side.CREDIT,
                "amount": base_amount,
                "currency": account.currency,
            },
        ]
    if movement_type == "investment":
        destination_value = Decimal(destination_amount) if destination_amount is not None else base_amount
        if investment_direction == LedgerTransaction.InvestmentDirection.OUTFLOW:
            return [
                {
                    "account": account,
                    "side": LedgerEntry.Side.DEBIT,
                    "amount": destination_value,
                    "currency": account.currency,
                },
                {
                    "account": counterparty_account,
                    "side": LedgerEntry.Side.CREDIT,
                    "amount": base_amount,
                    "currency": counterparty_account.currency,
                    "asset": counterparty_account.asset if counterparty_account.asset_id else None,
                },
            ]
        return [
            {
                "account": counterparty_account,
                "side": LedgerEntry.Side.DEBIT,
                "amount": destination_value,
                "currency": counterparty_account.currency,
                "asset": counterparty_account.asset if counterparty_account.asset_id else None,
            },
            {
                "account": account,
                "side": LedgerEntry.Side.CREDIT,
                "amount": base_amount,
                "currency": account.currency,
            },
        ]
    if movement_type == "revaluation":
        # Positive amount (gain): asset DR / counterparty CR.
        # Negative amount (loss): counterparty DR / asset CR.
        abs_amount = abs(base_amount)
        if base_amount >= 0:
            asset_side = LedgerEntry.Side.DEBIT
            counterparty_side = LedgerEntry.Side.CREDIT
        else:
            asset_side = LedgerEntry.Side.CREDIT
            counterparty_side = LedgerEntry.Side.DEBIT
        return [
            {
                "account": account,
                "side": asset_side,
                "amount": abs_amount,
                "currency": account.currency,
            },
            {
                "account": counterparty_account,
                "side": counterparty_side,
                "amount": abs_amount,
                "currency": counterparty_account.currency,
            },
        ]
    if movement_type == "debt_payment":
        principal = Decimal(principal_amount or ZERO)
        interest = Decimal(interest_amount or ZERO)
        if liability_account is None:
            raise ValidationError({"liability_account_id": "La cuenta de pasivo es obligatoria."})
        rows: list[dict] = [
            {
                "account": liability_account,
                "side": LedgerEntry.Side.DEBIT,
                "amount": principal,
                "currency": liability_account.currency,
                "liability": liability_account.liability
                if liability_account.liability_id
                else None,
            },
            {
                "account": account,
                "side": LedgerEntry.Side.CREDIT,
                "amount": base_amount,
                "currency": account.currency,
            },
        ]
        if interest > ZERO:
            if interest_account is None:
                raise ValidationError(
                    {"interest_account_id": "La cuenta de intereses es obligatoria."}
                )
            rows.insert(
                1,
                {
                    "account": interest_account,
                    "side": LedgerEntry.Side.DEBIT,
                    "amount": interest,
                    "currency": interest_account.currency,
                    "annual_expense_entry": annual_expense_entry,
                    **classification,
                },
            )
        return rows
    return [
        {
            "account": counterparty_account,
            "side": LedgerEntry.Side.DEBIT,
            "amount": base_amount,
            "currency": counterparty_account.currency,
        },
        {
            "account": account,
            "side": LedgerEntry.Side.CREDIT,
            "amount": base_amount,
            "currency": account.currency,
        },
    ]


def _resolve_entry_classification(
    *,
    movement_type: str,
    flow_family: str,
    category_key: str,
    subcategory_key: str,
    annual_income_entry,
    annual_expense_entry,
) -> dict[str, str]:
    if flow_family and category_key and subcategory_key:
        return {
            "flow_family": flow_family,
            "category_key": category_key,
            "subcategory_key": subcategory_key,
        }

    if movement_type == "income" and annual_income_entry is not None:
        return {
            "flow_family": LedgerEntry.FlowFamily.INCOME,
            "category_key": annual_income_entry.category,
            "subcategory_key": annual_income_entry.subcategory,
        }
    if movement_type in {"expense", "debt_payment"} and annual_expense_entry is not None:
        return {
            "flow_family": LedgerEntry.FlowFamily.EXPENSE,
            "category_key": annual_expense_entry.category,
            "subcategory_key": annual_expense_entry.subcategory,
        }
    return {}


def _normalize_quick_movement_type(movement_type: str) -> str:
    if movement_type == "investment_purchase":
        return "investment"
    return movement_type


def _normalize_investment_direction(*, movement_type: str, investment_direction: str) -> str:
    if movement_type != "investment":
        return ""
    if investment_direction:
        return investment_direction
    return cast(str, LedgerTransaction.InvestmentDirection.INFLOW)
