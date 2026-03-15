from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError

from .models import LedgerAccount, LedgerEntry, LedgerTransaction

ZERO = Decimal("0")
TWO_DECIMAL_PLACES = Decimal("0.01")


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


def get_account_balance(*, account: LedgerAccount) -> Decimal:
    totals = compute_entry_balance_totals(account.entries.all(), account_id=account.id)
    if account.account_type in {LedgerAccount.AccountType.ASSET, LedgerAccount.AccountType.EXPENSE}:
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


def validate_transaction_entries(*, entries_data: list[dict], user_id: int) -> None:
    if len(entries_data) < 2:
        raise ValidationError({"entries": "Una transaccion debe incluir al menos dos apuntes."})

    totals_by_currency: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"debit": ZERO, "credit": ZERO}
    )
    for index, entry_data in enumerate(entries_data):
        account = entry_data["account"]
        if account.user_id != user_id:
            raise ValidationError(
                {
                    "entries": {
                        index: {"account_id": "La cuenta no pertenece al usuario autenticado."}
                    }
                }
            )

        currency = normalize_currency_code(entry_data.get("currency") or account.currency)
        if len(currency) != 3:
            raise ValidationError({"entries": {index: {"currency": "Moneda invalida."}}})
        if currency != account.currency:
            raise ValidationError(
                {
                    "entries": {
                        index: {
                            "currency": "La moneda del apunte debe coincidir con la moneda de la cuenta."
                        }
                    }
                }
            )

        amount = entry_data["amount"]
        if amount <= ZERO:
            raise ValidationError(
                {"entries": {index: {"amount": "El importe del apunte debe ser mayor que cero."}}}
            )
        totals_by_currency[currency][entry_data["side"]] += amount

    for currency, totals in totals_by_currency.items():
        if totals["debit"] != totals["credit"]:
            raise ValidationError(
                {
                    "entries": (
                        "La transaccion no esta balanceada para la moneda "
                        f"{currency}: debe={totals['debit']} haber={totals['credit']}."
                    )
                }
            )


def build_monthly_accounting_summary(*, user_id: int, fiscal_year: int) -> dict:
    queryset = list(
        LedgerEntry.objects.filter(
            transaction__user_id=user_id,
            transaction__booking_date__year=fiscal_year,
        )
        .select_related("transaction", "annual_income_entry", "annual_expense_entry")
        .order_by("transaction__booking_date", "id")
    )

    months: list[dict] = []
    for month in range(1, 13):
        income_total = ZERO
        expense_total = ZERO
        uncategorized_total = ZERO
        month_entries = [
            entry for entry in queryset if entry.transaction.booking_date.month == month
        ]
        for entry in month_entries:
            if entry.annual_income_entry_id is not None:
                if entry.side == LedgerEntry.Side.CREDIT:
                    income_total += entry.amount
                else:
                    income_total -= entry.amount
                continue
            if entry.annual_expense_entry_id is not None:
                if entry.side == LedgerEntry.Side.DEBIT:
                    expense_total += entry.amount
                else:
                    expense_total -= entry.amount
                continue
            uncategorized_total += entry.amount
        months.append(
            {
                "month": month,
                "income_total": serialize_decimal(income_total),
                "expense_total": serialize_decimal(expense_total),
                "uncategorized_total": serialize_decimal(uncategorized_total),
            }
        )
    return {"fiscal_year": fiscal_year, "months": months}


def validate_booking_and_value_dates(*, booking_date: date, value_date: date) -> None:
    if value_date < booking_date:
        raise ValidationError(
            {"value_date": "La fecha valor no puede ser anterior a la fecha de contabilizacion."}
        )


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
    account, _created = LedgerAccount.objects.get_or_create(
        user_id=user_id,
        account_type=account_type,
        currency=normalized_currency,
        origin=LedgerAccount.Origin.SYSTEM,
        name=name,
        defaults={"is_active": True},
    )
    return account


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
    annual_income_entry=None,
    annual_expense_entry=None,
) -> LedgerTransaction:
    validate_booking_and_value_dates(booking_date=booking_date, value_date=value_date)
    validate_transaction_entries(
        entries_data=_build_quick_entry_payload(
            movement_type=movement_type,
            amount=amount,
            account=account,
            counterparty_account=counterparty_account,
            annual_income_entry=annual_income_entry,
            annual_expense_entry=annual_expense_entry,
        ),
        user_id=user.id,
    )

    transaction_row = LedgerTransaction.objects.create(
        user=user,
        booking_date=booking_date,
        value_date=value_date,
        description=description,
        status=status,
        origin=origin,
        notes=notes,
    )
    for entry_data in _build_quick_entry_payload(
        movement_type=movement_type,
        amount=amount,
        account=account,
        counterparty_account=counterparty_account,
        annual_income_entry=annual_income_entry,
        annual_expense_entry=annual_expense_entry,
    ):
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
) -> list[dict]:
    base_amount = Decimal(amount)
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
            },
            {
                "account": account,
                "side": LedgerEntry.Side.CREDIT,
                "amount": base_amount,
                "currency": account.currency,
            },
        ]
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
