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


def build_account_balances_summary(
    *,
    user_id: int,
    fiscal_year: int | None = None,
    month: int | None = None,
    account_type: str | None = None,
    status: str | None = None,
) -> dict:
    accounts_queryset = LedgerAccount.objects.filter(user_id=user_id)
    if account_type:
        accounts_queryset = accounts_queryset.filter(account_type=account_type)
    accounts = list(accounts_queryset.order_by("account_type", "name", "id"))

    current_entries_queryset = LedgerEntry.objects.filter(
        transaction__user_id=user_id
    ).select_related("transaction")
    if account_type:
        current_entries_queryset = current_entries_queryset.filter(
            account__account_type=account_type
        )
    if status:
        current_entries_queryset = current_entries_queryset.filter(transaction__status=status)

    period_entries_queryset = current_entries_queryset
    if fiscal_year is not None:
        period_entries_queryset = period_entries_queryset.filter(
            transaction__booking_date__year=fiscal_year
        )
    if month is not None:
        period_entries_queryset = period_entries_queryset.filter(
            transaction__booking_date__month=month
        )

    current_totals_by_account = _group_balance_totals_by_account(list(current_entries_queryset))
    period_totals_by_account = _group_balance_totals_by_account(list(period_entries_queryset))

    items: list[dict] = []
    totals_by_type: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for account in accounts:
        current_totals = current_totals_by_account.get(account.id, LedgerBalanceTotals(ZERO, ZERO))
        period_totals = period_totals_by_account.get(account.id, LedgerBalanceTotals(ZERO, ZERO))
        current_balance = compute_account_balance_from_totals(
            account_type=account.account_type,
            totals=current_totals,
        )
        period_net_change = compute_account_balance_from_totals(
            account_type=account.account_type,
            totals=period_totals,
        )
        totals_by_type[account.account_type] += current_balance
        items.append(
            {
                "account_id": account.id,
                "name": account.name,
                "account_type": account.account_type,
                "currency": account.currency,
                "origin": account.origin,
                "current_balance": str(current_balance),
                "period_debit_total": serialize_decimal(period_totals.debit_total),
                "period_credit_total": serialize_decimal(period_totals.credit_total),
                "period_net_change": serialize_decimal(period_net_change),
            }
        )

    return {
        "filters": {
            "year": fiscal_year,
            "month": month,
            "account_type": account_type,
            "status": status,
        },
        "totals_by_account_type": {
            key: serialize_decimal(value) for key, value in sorted(totals_by_type.items())
        },
        "accounts": items,
    }


def validate_booking_and_value_dates(*, booking_date: date, value_date: date) -> None:
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
    principal_amount: Decimal | None = None,
    interest_amount: Decimal | None = None,
    liability_account: LedgerAccount | None = None,
    interest_account: LedgerAccount | None = None,
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
            principal_amount=principal_amount,
            interest_amount=interest_amount,
            liability_account=liability_account,
            interest_account=interest_account,
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
        principal_amount=principal_amount,
        interest_amount=interest_amount,
        liability_account=liability_account,
        interest_account=interest_account,
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
    principal_amount: Decimal | None = None,
    interest_amount: Decimal | None = None,
    liability_account: LedgerAccount | None = None,
    interest_account: LedgerAccount | None = None,
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
    if movement_type == "investment_purchase":
        return [
            {
                "account": counterparty_account,
                "side": LedgerEntry.Side.DEBIT,
                "amount": base_amount,
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


def _group_balance_totals_by_account(entries: list[LedgerEntry]) -> dict[int, LedgerBalanceTotals]:
    grouped: dict[int, dict[str, Decimal]] = defaultdict(lambda: {"debit": ZERO, "credit": ZERO})
    for entry in entries:
        grouped[entry.account_id][entry.side] += entry.amount
    return {
        account_id: LedgerBalanceTotals(
            debit_total=totals["debit"],
            credit_total=totals["credit"],
        )
        for account_id, totals in grouped.items()
    }
