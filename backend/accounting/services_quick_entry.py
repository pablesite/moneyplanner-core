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
    destination_fee_amount: Decimal | None = None,
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
    if normalized_movement_type == "investment":
        # Los apuntes ya estan escritos, asi que cada comision puede resolver contra que
        # cuenta se cobra: la que suelta el dinero, y en un traspaso entre fondos tambien
        # la que lo recibe.
        transaction_row.refresh_from_db()
        sync_investment_fee(
            transaction_row=transaction_row,
            fee_amount=None if fee_amount is None else Decimal(fee_amount),
            destination_fee_amount=(
                None if destination_fee_amount is None else Decimal(destination_fee_amount)
            ),
        )
    return transaction_row


def investment_fee_amount(transaction_row: LedgerTransaction) -> str | None:
    """Lo que costo la parte del movimiento que paga la cuenta de origen."""
    return _fee_amount_for(transaction_row, resolve_investment_funding_account(transaction_row))


def investment_destination_fee_amount(transaction_row: LedgerTransaction) -> str | None:
    """Lo que costo la compra de una reinversion, que la paga la posicion que la recibe."""
    return _fee_amount_for(transaction_row, resolve_investment_destination_account(transaction_row))


def _fee_amount_for(
    transaction_row: LedgerTransaction, account: LedgerAccount | None
) -> str | None:
    fee = _fee_charged_to(transaction_row, account)
    if fee is None:
        return None
    entry = next(
        (row for row in fee.entries.all() if row.side == LedgerEntry.Side.DEBIT),
        None,
    )
    return str(entry.amount) if entry is not None else None


def _fee_charged_to(
    transaction_row: LedgerTransaction, account: LedgerAccount | None
) -> LedgerTransaction | None:
    """La comision que paga esa cuenta, entre las que cuelgan del movimiento.

    Un traspaso entre fondos paga dos: la de la venta la cuenta de la que sale el dinero y
    la de la compra la que lo recibe. Distinguirlas por quien las paga evita un campo nuevo
    en el modelo y sigue reconociendo las que ya estaban registradas.
    """
    if account is None:
        return None
    for fee in transaction_row.fee_movements.all():
        entry = next(
            (row for row in fee.entries.all() if row.side == LedgerEntry.Side.CREDIT),
            None,
        )
        if entry is not None and entry.account_id == account.id:
            return fee
    return None


def resolve_investment_funding_account(
    transaction_row: LedgerTransaction,
) -> LedgerAccount | None:
    """La cuenta que paga el movimiento, que es la que paga tambien su comision.

    En un aporte y en una reinversion es la que suelta el dinero; en una retirada, la que
    lo recibe, porque el broker descuenta su comision de lo que te abona. Se deduce de los
    apuntes para que editar un movimiento recoloque su comision donde toque, aunque hayan
    cambiado las cuentas.
    """
    if transaction_row.quick_entry_kind != "investment":
        return None
    side = (
        LedgerEntry.Side.DEBIT
        if transaction_row.investment_direction == LedgerTransaction.InvestmentDirection.OUTFLOW
        else LedgerEntry.Side.CREDIT
    )
    entry = next(
        (row for row in transaction_row.entries.all() if row.side == side),
        None,
    )
    return entry.account if entry is not None else None


def resolve_investment_destination_account(
    transaction_row: LedgerTransaction,
) -> LedgerAccount | None:
    """La posicion que recibe el dinero de una reinversion, y paga la comision de compra.

    Solo una reinversion tiene dos lados que cobran: en un aporte o una retirada el broker
    cobra una vez, contra la cuenta que mueve el dinero.
    """
    if (
        transaction_row.quick_entry_kind != "investment"
        or transaction_row.investment_direction
        != LedgerTransaction.InvestmentDirection.REINVESTMENT
    ):
        return None
    entry = next(
        (row for row in transaction_row.entries.all() if row.side == LedgerEntry.Side.DEBIT),
        None,
    )
    return entry.account if entry is not None else None


@transaction.atomic
def sync_investment_fee(
    *,
    transaction_row: LedgerTransaction,
    fee_amount: Decimal | None,
    destination_fee_amount: Decimal | None = None,
) -> None:
    """Deja cada comision del movimiento en el importe indicado, sea cual sea su estado.

    Omitir un importe no toca nada: quien edita un movimiento sin hablar de comision no
    esta pidiendo que desaparezca. Cero la borra, y un importe nuevo la crea o la corrige
    en el sitio, conservando su identidad para que la operacion de cartera que la apunta no
    se quede sin referencia.
    """
    _sync_one_fee(
        transaction_row=transaction_row,
        account=resolve_investment_funding_account(transaction_row),
        amount=fee_amount,
        field="fee_amount",
    )
    _sync_one_fee(
        transaction_row=transaction_row,
        account=resolve_investment_destination_account(transaction_row),
        amount=destination_fee_amount,
        field="destination_fee_amount",
    )


def _sync_one_fee(
    *,
    transaction_row: LedgerTransaction,
    account: LedgerAccount | None,
    amount: Decimal | None,
    field: str,
) -> None:
    if amount is None:
        return
    existing = _fee_charged_to(transaction_row, account)
    if amount <= ZERO:
        if existing is not None:
            existing.delete()
        return
    if account is None:
        raise ValidationError(
            {
                field: (
                    "La comision de compra solo aplica a una reinversion."
                    if field == "destination_fee_amount"
                    else "Solo los movimientos de inversion admiten comision."
                )
            }
        )
    if existing is None:
        create_investment_fee_transaction(
            user=transaction_row.user,
            investment_transaction=transaction_row,
            account=account,
            fee_amount=amount,
        )
        return
    fee_account = get_or_create_system_account(
        user_id=transaction_row.user_id,
        account_type=cast(str, LedgerAccount.AccountType.EXPENSE),
        currency=account.currency,
        name=INVESTMENT_FEE_ACCOUNT_NAME,
    )
    existing.booking_date = transaction_row.booking_date
    existing.value_date = transaction_row.value_date
    existing.description = _fee_description(transaction_row=transaction_row, account=account)
    existing.ownership = transaction_row.ownership
    existing.save(
        update_fields=["booking_date", "value_date", "description", "ownership", "updated_at"]
    )
    existing.entries.all().delete()
    for entry_data in _build_quick_entry_payload(
        movement_type="expense",
        amount=amount,
        account=account,
        counterparty_account=fee_account,
        flow_family=cast(str, LedgerEntry.FlowFamily.EXPENSE),
        category_key=INVESTMENT_FEE_CATEGORY_KEY,
        subcategory_key=INVESTMENT_FEE_SUBCATEGORY_KEY,
    ):
        LedgerEntry.objects.create(transaction=existing, **entry_data)


def _fee_description(*, transaction_row: LedgerTransaction, account: LedgerAccount) -> str:
    """Un traspaso entre fondos deja dos comisiones en la lista: hay que poder leerlas."""
    destination = resolve_investment_destination_account(transaction_row)
    if destination is None:
        prefix = "Comisión"
    elif destination.id == account.id:
        prefix = "Comisión de compra"
    else:
        prefix = "Comisión de venta"
    return f"{prefix} · {transaction_row.description}"[:240]


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
    la cuenta que la paga, y queda enlazada para que borrar la inversión se lleve sus
    comisiones y para que la cartera pueda copiarlas a su operación.
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
        description=_fee_description(transaction_row=investment_transaction, account=account),
        amount=fee_amount,
        account=account,
        counterparty_account=fee_account,
        status=investment_transaction.status,
        origin=investment_transaction.origin,
        import_source=investment_transaction.import_source,
        # El fingerprint es único por usuario y origen, y una reinversión deja dos
        # comisiones, así que cada una lleva la cuenta que la paga en el suyo.
        import_fingerprint=f"{fingerprint[:55]}:fee:{account.id}"[:64] if fingerprint else "",
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
