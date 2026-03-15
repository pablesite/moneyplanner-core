from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError

from .models import LedgerAccount, LedgerEntry

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
