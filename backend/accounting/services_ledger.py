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
    # Safety boundary: only entries from transactions owned by the same user
    # should contribute to account balances.
    queryset = account.entries.select_related("transaction").filter(
        transaction__user_id=account.user_id
    )
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


def _resolve_opening_balance_sides(
    *, account_type: str, opening_amount: Decimal
) -> tuple[str, str]:
    if account_type == LedgerAccount.AccountType.ASSET:
        position_side = (
            cast(str, LedgerEntry.Side.DEBIT)
            if opening_amount > ZERO
            else cast(str, LedgerEntry.Side.CREDIT)
        )
        equity_side = (
            cast(str, LedgerEntry.Side.CREDIT)
            if opening_amount > ZERO
            else cast(str, LedgerEntry.Side.DEBIT)
        )
        return position_side, equity_side
    if account_type == LedgerAccount.AccountType.LIABILITY:
        position_side = (
            cast(str, LedgerEntry.Side.CREDIT)
            if opening_amount > ZERO
            else cast(str, LedgerEntry.Side.DEBIT)
        )
        equity_side = (
            cast(str, LedgerEntry.Side.DEBIT)
            if opening_amount > ZERO
            else cast(str, LedgerEntry.Side.CREDIT)
        )
        return position_side, equity_side
    raise ValidationError(
        {"detail": ("El saldo de apertura contable solo aplica a cuentas asset o liability.")}
    )


@transaction.atomic
def sync_net_worth_opening_balance_transaction(
    *,
    user,
    account: LedgerAccount,
    amount: Decimal,
    booking_date: date,
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
    position_kind = "asset" if asset is not None else "liability"
    position_id = asset.id if asset is not None else liability.id
    position_label = asset.name if asset is not None else liability.name
    opening_note = build_net_worth_opening_balance_note(
        position_kind=position_kind,
        position_id=position_id,
    )
    normalized_currency = normalize_currency_code(account.currency)
    posted_status = cast(str, LedgerTransaction.Status.POSTED)

    existing_transaction = (
        LedgerTransaction.objects.filter(
            user_id=user.id,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=opening_note,
            entries__account_id=account.id,
        )
        .distinct()
        .order_by("-booking_date", "-id")
        .first()
    )

    if opening_amount == ZERO:
        if existing_transaction is not None:
            existing_transaction.delete()
        return None

    amount_abs = abs(opening_amount)
    position_side, equity_side = _resolve_opening_balance_sides(
        account_type=account.account_type,
        opening_amount=opening_amount,
    )
    equity_account = get_or_create_system_equity_account(
        user_id=user.id,
        currency=normalized_currency,
    )

    if existing_transaction is None:
        existing_transaction = LedgerTransaction.objects.create(
            user=user,
            booking_date=booking_date,
            value_date=booking_date,
            description=f"Saldo inicial contable: {position_label}"[:240],
            status=posted_status,
            origin=LedgerTransaction.Origin.SYSTEM,
            notes=opening_note,
        )
        LedgerEntry.objects.create(
            transaction=existing_transaction,
            account=account,
            side=position_side,
            amount=amount_abs,
            currency=normalized_currency,
            asset=asset,
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=existing_transaction,
            account=equity_account,
            side=equity_side,
            amount=amount_abs,
            currency=normalized_currency,
        )
        return existing_transaction

    existing_transaction.booking_date = booking_date
    existing_transaction.value_date = booking_date
    existing_transaction.description = f"Saldo inicial contable: {position_label}"[:240]
    existing_transaction.status = posted_status
    existing_transaction.origin = LedgerTransaction.Origin.SYSTEM
    existing_transaction.notes = opening_note
    existing_transaction.save(
        update_fields=[
            "booking_date",
            "value_date",
            "description",
            "status",
            "origin",
            "notes",
            "updated_at",
        ]
    )

    entries_by_account = {entry.account_id: entry for entry in existing_transaction.entries.all()}
    position_entry = entries_by_account.get(account.id)
    equity_entry = entries_by_account.get(equity_account.id)

    if position_entry is None or equity_entry is None:
        existing_transaction.entries.all().delete()
        LedgerEntry.objects.create(
            transaction=existing_transaction,
            account=account,
            side=position_side,
            amount=amount_abs,
            currency=normalized_currency,
            asset=asset,
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=existing_transaction,
            account=equity_account,
            side=equity_side,
            amount=amount_abs,
            currency=normalized_currency,
        )
        return existing_transaction

    position_entry.account = account
    position_entry.side = position_side
    position_entry.amount = amount_abs
    position_entry.currency = normalized_currency
    position_entry.asset = asset
    position_entry.liability = liability
    position_entry.save(
        update_fields=[
            "account",
            "side",
            "amount",
            "currency",
            "asset",
            "liability",
            "updated_at",
        ]
    )

    equity_entry.account = equity_account
    equity_entry.side = equity_side
    equity_entry.amount = amount_abs
    equity_entry.currency = normalized_currency
    equity_entry.asset = None
    equity_entry.liability = None
    equity_entry.save(
        update_fields=[
            "account",
            "side",
            "amount",
            "currency",
            "asset",
            "liability",
            "updated_at",
        ]
    )
    return existing_transaction


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
    position_side, equity_side = _resolve_opening_balance_sides(
        account_type=account.account_type,
        opening_amount=opening_amount,
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
