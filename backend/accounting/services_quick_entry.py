from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .services_ledger import ZERO, get_or_create_system_account
from .services_start_dates import sync_position_start_dates_for_transaction
from .services_transactions import validate_booking_and_value_dates, validate_transaction_entries

ROTATORY_DEPOSIT_ASSET_SUBCATEGORIES = {"deposits", "short_term_deposit"}
INVESTMENT_FEE_ACCOUNT_NAME = "Comisiones de inversión"
# La comisión no es capital colocado: el dinero se consume, no se convierte en patrimonio.
# Clasificarla como inversión la contaría como ahorro en el cierre mensual y dejaría un
# residuo de conciliación por el importe exacto de la comisión.
INVESTMENT_FEE_CATEGORY_KEY = "consumption_expenses"
INVESTMENT_FEE_SUBCATEGORY_KEY = "financial_commitments"


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
    investment_units: Decimal | None = None,
    investment_unit_price: Decimal | None = None,
    fee_amount: Decimal | None = None,
    fee_for: LedgerTransaction | None = None,
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
        normalized_movement_type in {"investment", "transfer"}
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
        investment_units=investment_units if normalized_movement_type == "investment" else None,
        investment_unit_price=(
            investment_unit_price if normalized_movement_type == "investment" else None
        ),
        fee_for=fee_for,
    )
    for entry_data in payload:
        LedgerEntry.objects.create(transaction=transaction_row, **entry_data)
    sync_position_start_dates_for_transaction(transaction=transaction_row)
    if normalized_movement_type == "investment" and fee_amount is not None:
        create_investment_fee_transaction(
            user=user,
            investment_transaction=transaction_row,
            account=account,
            fee_amount=Decimal(fee_amount),
        )
    return transaction_row


def create_investment_fee_transaction(
    *,
    user,
    investment_transaction: LedgerTransaction,
    account: LedgerAccount,
    fee_amount: Decimal,
) -> LedgerTransaction | None:
    """Registra la comisión de una operación de inversión como gasto propio y vinculado.

    La comisión no puede ir dentro del propio movimiento de inversión: todo lo que lee un
    aporte o una retirada —cartera, patrimonio, cierre— cuenta con dos apuntes, uno por
    cuenta, y un tercero desviaría el importe invertido hacia el coste. Va aparte, contra
    la misma cuenta que financia el movimiento, y queda enlazada para que borrar la
    inversión se lleve su comisión y para que la cartera pueda copiarla a su operación.
    """
    if fee_amount <= ZERO:
        return None
    fee_account = get_or_create_system_account(
        user_id=user.id,
        account_type=cast(str, LedgerAccount.AccountType.EXPENSE),
        currency=account.currency,
        name=INVESTMENT_FEE_ACCOUNT_NAME,
    )
    fingerprint = investment_transaction.import_fingerprint
    return create_quick_transaction(
        user=user,
        movement_type="expense",
        booking_date=investment_transaction.booking_date,
        value_date=investment_transaction.value_date,
        description=f"Comisión · {investment_transaction.description}"[:240],
        amount=fee_amount,
        account=account,
        counterparty_account=fee_account,
        status=investment_transaction.status,
        origin=investment_transaction.origin,
        import_source=investment_transaction.import_source,
        # El fingerprint es único por usuario y origen, así que la comisión necesita el suyo.
        import_fingerprint=f"{fingerprint[:59]}:fee" if fingerprint else "",
        member_tag=investment_transaction.member_tag,
        ownership=investment_transaction.ownership,
        flow_family=cast(str, LedgerEntry.FlowFamily.EXPENSE),
        category_key=INVESTMENT_FEE_CATEGORY_KEY,
        subcategory_key=INVESTMENT_FEE_SUBCATEGORY_KEY,
        fee_for=investment_transaction,
    )


def _build_quick_entry_payload(
    *,
    movement_type: str,
    amount: Decimal,
    account: LedgerAccount,
    counterparty_account: LedgerAccount,
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
    category_key, subcategory_key = _normalize_investment_budget_classification(
        movement_type=movement_type,
        investment_direction=investment_direction,
        category_key=category_key,
        subcategory_key=subcategory_key,
        counterparty_account=counterparty_account,
    )
    classification = _resolve_entry_classification(
        movement_type=movement_type,
        flow_family=flow_family,
        category_key=category_key,
        subcategory_key=subcategory_key,
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
                **classification,
            },
            {
                "account": account,
                "side": LedgerEntry.Side.CREDIT,
                "amount": base_amount,
                "currency": account.currency,
            },
        ]
    if movement_type == "transfer":
        destination_value = (
            Decimal(destination_amount) if destination_amount is not None else base_amount
        )
        return [
            {
                "account": counterparty_account,
                "side": LedgerEntry.Side.DEBIT,
                "amount": destination_value,
                "currency": counterparty_account.currency,
            },
            {
                "account": account,
                "side": LedgerEntry.Side.CREDIT,
                "amount": base_amount,
                "currency": account.currency,
            },
        ]
    if movement_type == "investment":
        destination_value = (
            Decimal(destination_amount) if destination_amount is not None else base_amount
        )
        if investment_direction == LedgerTransaction.InvestmentDirection.REINVESTMENT:
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
                    "asset": account.asset if account.asset_id else None,
                },
            ]
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
                    **classification,
                },
            ]
        return [
            {
                "account": counterparty_account,
                "side": LedgerEntry.Side.DEBIT,
                "amount": destination_value,
                "currency": counterparty_account.currency,
                "asset": counterparty_account.asset if counterparty_account.asset_id else None,
                **classification,
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
            counterparty_flow_family = LedgerEntry.FlowFamily.INCOME
        else:
            asset_side = LedgerEntry.Side.CREDIT
            counterparty_side = LedgerEntry.Side.DEBIT
            counterparty_flow_family = LedgerEntry.FlowFamily.EXPENSE
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
                "flow_family": counterparty_flow_family,
            },
        ]
    if movement_type == "adjustment":
        abs_amount = abs(base_amount)
        account_side = _resolve_adjustment_side(
            account_type=account.account_type,
            delta=base_amount,
        )
        counterparty_side = (
            LedgerEntry.Side.CREDIT
            if account_side == LedgerEntry.Side.DEBIT
            else LedgerEntry.Side.DEBIT
        )
        return [
            {
                "account": account,
                "side": account_side,
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
                **classification,
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


def _resolve_adjustment_side(*, account_type: str, delta: Decimal) -> str:
    debit_increases = account_type in {
        LedgerAccount.AccountType.ASSET,
        LedgerAccount.AccountType.EXPENSE,
    }
    if delta >= ZERO:
        return cast(str, LedgerEntry.Side.DEBIT if debit_increases else LedgerEntry.Side.CREDIT)
    return cast(str, LedgerEntry.Side.CREDIT if debit_increases else LedgerEntry.Side.DEBIT)


def _resolve_entry_classification(
    *,
    movement_type: str,
    flow_family: str,
    category_key: str,
    subcategory_key: str,
) -> dict[str, str]:
    if flow_family and category_key and subcategory_key:
        return {
            "flow_family": flow_family,
            "category_key": category_key,
            "subcategory_key": subcategory_key,
        }

    return {}


def _normalize_investment_budget_classification(
    *,
    movement_type: str,
    investment_direction: str,
    category_key: str,
    subcategory_key: str,
    counterparty_account: LedgerAccount,
) -> tuple[str, str]:
    if movement_type != "investment":
        return category_key, subcategory_key
    if investment_direction == LedgerTransaction.InvestmentDirection.REINVESTMENT:
        return category_key, subcategory_key
    if category_key != "financial_investments":
        return category_key, subcategory_key
    asset = counterparty_account.asset if counterparty_account.asset_id else None
    if asset is None or asset.subcategory not in ROTATORY_DEPOSIT_ASSET_SUBCATEGORIES:
        return category_key, subcategory_key
    return category_key, "deposits_fixed_income"


def _normalize_quick_movement_type(movement_type: str) -> str:
    return movement_type


def _normalize_investment_direction(*, movement_type: str, investment_direction: str) -> str:
    if movement_type != "investment":
        return ""
    if investment_direction:
        return investment_direction
    return cast(str, LedgerTransaction.InvestmentDirection.INFLOW)
