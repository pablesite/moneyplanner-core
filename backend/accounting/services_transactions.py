from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .services_ledger import ZERO, normalize_currency_code


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


def validate_booking_and_value_dates(*, booking_date, value_date) -> None:
    if value_date < booking_date:
        raise ValidationError(
            {"value_date": "La fecha valor no puede ser anterior a la fecha de contabilizacion."}
        )


def validate_balance_summary_filters(*, fiscal_year: int | None, month: int | None) -> None:
    if month is not None and fiscal_year is None:
        raise ValidationError(
            {"year": "Query param 'year' es obligatorio cuando se informa 'month'."}
        )
    if month is not None and (month < 1 or month > 12):
        raise ValidationError({"month": "Query param 'month' invalido."})
