from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import LedgerAccount, LedgerEntry, LedgerTransaction

ZERO = Decimal("0")
TWO_DECIMAL_PLACES = Decimal("0.01")
NET_WORTH_OPENING_NOTE_PREFIX = "net_worth_opening_balance"
SYSTEM_EQUITY_ACCOUNT_NAME = "Patrimonio neto"


@dataclass(frozen=True)
class LedgerBalanceTotals:
    debit_total: Decimal
    credit_total: Decimal


def normalize_currency_code(value: str) -> str:
    return (value or "").strip().upper()


def serialize_decimal(value: Decimal, *, places: Decimal = TWO_DECIMAL_PLACES) -> str:
    return str(value.quantize(places))


def get_user_ledger_account(
    *, user_id: int, account_id: int | None, expected_type: str | None = None
) -> LedgerAccount | None:
    if not account_id:
        return None

    queryset = LedgerAccount.objects.filter(user_id=user_id, id=account_id)
    if expected_type is not None:
        queryset = queryset.filter(account_type=expected_type)
    return queryset.first()


def get_account_entries(
    *,
    account: LedgerAccount,
    as_of_date: date | None = None,
    status: str | None = None,
) -> QuerySet[LedgerEntry]:
    queryset = account.entries.select_related("transaction")
    if as_of_date is not None:
        queryset = queryset.filter(transaction__booking_date__lte=as_of_date)
    if status is not None:
        queryset = queryset.filter(transaction__status=status)
    return queryset


def has_account_entries(
    *,
    account: LedgerAccount,
    as_of_date: date | None = None,
    status: str | None = None,
) -> bool:
    return get_account_entries(account=account, as_of_date=as_of_date, status=status).exists()


def compute_account_balance_from_totals(
    *, account_type: str, totals: LedgerBalanceTotals
) -> Decimal:
    if account_type in {LedgerAccount.AccountType.ASSET, LedgerAccount.AccountType.EXPENSE}:
        return totals.debit_total - totals.credit_total
    return totals.credit_total - totals.debit_total


def compute_entry_balance_totals(
    entries: QuerySet[LedgerEntry] | list[LedgerEntry], *, account_id: int | None = None
) -> LedgerBalanceTotals:
    debit_total = ZERO
    credit_total = ZERO
    for entry in entries:
        if account_id is not None and entry.account_id != account_id:
            continue
        if entry.side == LedgerEntry.Side.DEBIT:
            debit_total += entry.amount
        else:
            credit_total += entry.amount
    return LedgerBalanceTotals(debit_total=debit_total, credit_total=credit_total)


def get_account_balance(
    *,
    account: LedgerAccount,
    as_of_date: date | None = None,
    status: str | None = None,
) -> Decimal:
    totals = compute_entry_balance_totals(
        get_account_entries(account=account, as_of_date=as_of_date, status=status),
        account_id=account.id,
    )
    return compute_account_balance_from_totals(account_type=account.account_type, totals=totals)


def validate_liquidity_account(
    *, account: LedgerAccount | None, user_id: int, field_name: str
) -> None:
    if account is None:
        raise ValidationError({field_name: "La cuenta es obligatoria."})
    if account.user_id != user_id:
        raise ValidationError({field_name: "La cuenta no pertenece al usuario autenticado."})
    if account.account_type != LedgerAccount.AccountType.ASSET:
        raise ValidationError({field_name: "La cuenta debe ser de tipo asset."})

    if account.asset_id is None:
        return

    from net_worth.models import Asset

    if account.asset.category != Asset.Category.CASH:
        raise ValidationError(
            {field_name: "La cuenta debe estar ligada a un activo de liquidez o ser operativa."}
        )


def validate_counterparty_account_type(
    *,
    account: LedgerAccount | None,
    user_id: int,
    expected_type: str,
    field_name: str,
) -> None:
    if account is None:
        raise ValidationError({field_name: "La cuenta contrapartida es obligatoria."})
    if account.user_id != user_id:
        raise ValidationError({field_name: "La cuenta no pertenece al usuario autenticado."})
    if account.account_type != expected_type:
        raise ValidationError(
            {field_name: (f"La cuenta contrapartida debe ser de tipo {expected_type}.")}
        )


def get_or_create_system_account(
    *,
    user_id: int,
    account_type: str,
    currency: str,
    name: str,
) -> LedgerAccount:
    normalized_currency = normalize_currency_code(currency)
    lookup = {
        "user_id": user_id,
        "account_type": account_type,
        "currency": normalized_currency,
        "origin": LedgerAccount.Origin.SYSTEM,
        "name": name,
    }
    try:
        account, _created = LedgerAccount.objects.get_or_create(
            **lookup,
            defaults={"is_active": True},
        )
    except LedgerAccount.MultipleObjectsReturned:
        account = LedgerAccount.objects.filter(**lookup).order_by("id").first()
        if account is None:
            raise
    if not account.is_active:
        account.is_active = True
        account.save(update_fields=["is_active", "updated_at"])
    return account


def get_or_create_system_equity_account(*, user_id: int, currency: str) -> LedgerAccount:
    return get_or_create_system_account(
        user_id=user_id,
        account_type=cast(str, LedgerAccount.AccountType.EQUITY),
        currency=currency,
        name=SYSTEM_EQUITY_ACCOUNT_NAME,
    )


def build_net_worth_opening_balance_note(*, position_kind: str, position_id: int) -> str:
    return f"{NET_WORTH_OPENING_NOTE_PREFIX}:{position_kind}:{position_id}"


@transaction.atomic
def ensure_net_worth_opening_balance_transaction(
    *,
    user,
    account: LedgerAccount,
    amount: Decimal,
    booking_date: date | None = None,
    asset=None,
    liability=None,
) -> LedgerTransaction | None:
    if asset is not None and liability is not None:
        raise ValidationError(
            {
                "detail": (
                    "El saldo de apertura contable no puede vincularse a un activo "
                    "y a un pasivo a la vez."
                )
            }
        )
    if asset is None and liability is None:
        raise ValidationError(
            {"detail": "El saldo de apertura contable requiere un activo o un pasivo."}
        )

    opening_amount = Decimal(amount or ZERO)
    if opening_amount == ZERO:
        return None

    position_kind = "asset" if asset is not None else "liability"
    position_id = asset.id if asset is not None else liability.id
    position_label = asset.name if asset is not None else liability.name
    opening_note = build_net_worth_opening_balance_note(
        position_kind=position_kind,
        position_id=position_id,
    )

    existing_transaction = (
        LedgerTransaction.objects.filter(
            user_id=user.id,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=opening_note,
            entries__account_id=account.id,
        )
        .distinct()
        .first()
    )
    if existing_transaction is not None:
        return existing_transaction

    if has_account_entries(
        account=account,
        status=cast(str, LedgerTransaction.Status.POSTED),
    ):
        return None

    normalized_currency = normalize_currency_code(account.currency)
    equity_account = get_or_create_system_equity_account(
        user_id=user.id,
        currency=normalized_currency,
    )
    amount_abs = abs(opening_amount)

    if account.account_type == LedgerAccount.AccountType.ASSET:
        position_side = LedgerEntry.Side.DEBIT if opening_amount > ZERO else LedgerEntry.Side.CREDIT
        equity_side = LedgerEntry.Side.CREDIT if opening_amount > ZERO else LedgerEntry.Side.DEBIT
    elif account.account_type == LedgerAccount.AccountType.LIABILITY:
        position_side = LedgerEntry.Side.CREDIT if opening_amount > ZERO else LedgerEntry.Side.DEBIT
        equity_side = LedgerEntry.Side.DEBIT if opening_amount > ZERO else LedgerEntry.Side.CREDIT
    else:
        raise ValidationError(
            {"detail": ("El saldo de apertura contable solo aplica a cuentas asset o liability.")}
        )

    effective_booking_date = booking_date or timezone.localdate()
    transaction_row = LedgerTransaction.objects.create(
        user=user,
        booking_date=effective_booking_date,
        value_date=effective_booking_date,
        description=f"Saldo inicial contable: {position_label}"[:240],
        status=LedgerTransaction.Status.POSTED,
        origin=LedgerTransaction.Origin.SYSTEM,
        notes=opening_note,
    )
    LedgerEntry.objects.create(
        transaction=transaction_row,
        account=account,
        side=position_side,
        amount=amount_abs,
        currency=normalized_currency,
        asset=asset,
        liability=liability,
    )
    LedgerEntry.objects.create(
        transaction=transaction_row,
        account=equity_account,
        side=equity_side,
        amount=amount_abs,
        currency=normalized_currency,
    )
    return transaction_row
