from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from django.db.models import Q
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


@dataclass(frozen=True)
class LedgerClassificationBackfillResult:
    scanned: int
    updated: int
    already_classified: int
    ambiguous: int
    ambiguous_reasons: dict[str, int]
    dry_run: bool


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
            flow_family, _category_key, _subcategory_key = _resolve_budget_classification(entry)
            if flow_family == LedgerEntry.FlowFamily.INCOME:
                if entry.side == LedgerEntry.Side.CREDIT:
                    income_total += entry.amount
                else:
                    income_total -= entry.amount
                continue
            if flow_family == LedgerEntry.FlowFamily.EXPENSE:
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


def build_budget_derived_suggestions(
    *,
    user_id: int,
    fiscal_year: int,
    lookback_years: int = 2,
) -> dict:
    start_year = fiscal_year - lookback_years + 1
    period_keys = _build_period_keys(start_year=start_year, end_year=fiscal_year)

    income_payload = _build_budget_suggestion_section(
        user_id=user_id,
        period_keys=period_keys,
        flow_family=cast(str, LedgerEntry.FlowFamily.INCOME),
        positive_side=cast(str, LedgerEntry.Side.CREDIT),
    )
    expense_payload = _build_budget_suggestion_section(
        user_id=user_id,
        period_keys=period_keys,
        flow_family=cast(str, LedgerEntry.FlowFamily.EXPENSE),
        positive_side=cast(str, LedgerEntry.Side.DEBIT),
    )
    return {
        "fiscal_year": fiscal_year,
        "lookback_years": lookback_years,
        "window_months": len(period_keys),
        "income": income_payload,
        "expense": expense_payload,
        "method_note": (
            "Sugerencia orientativa: promedio mensual del historico "
            "de la ventana * 12. No reemplaza el criterio del plan anual."
        ),
    }


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


def validate_budget_suggestion_filters(*, lookback_years: int) -> None:
    if lookback_years < 1 or lookback_years > 5:
        raise ValidationError({"lookback_years": "Query param 'lookback_years' invalido."})


@transaction.atomic
def backfill_ledger_entry_classification(
    *,
    user_id: int | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> LedgerClassificationBackfillResult:
    queryset = (
        LedgerEntry.objects.filter(
            Q(annual_income_entry__isnull=False) | Q(annual_expense_entry__isnull=False)
        )
        .select_related("annual_income_entry", "annual_expense_entry")
        .order_by("id")
    )
    if user_id is not None:
        queryset = queryset.filter(transaction__user_id=user_id)
    if limit is not None:
        queryset = queryset[:limit]

    scanned = 0
    updated = 0
    already_classified = 0
    ambiguous_reasons: dict[str, int] = defaultdict(int)
    rows_to_update: list[LedgerEntry] = []

    for entry in queryset:
        scanned += 1
        if entry.flow_family and entry.category_key and entry.subcategory_key:
            already_classified += 1
            continue

        if entry.flow_family or entry.category_key or entry.subcategory_key:
            ambiguous_reasons["partial_new_classification"] += 1
            continue

        has_income_link = (
            entry.annual_income_entry_id is not None and entry.annual_income_entry is not None
        )
        has_expense_link = (
            entry.annual_expense_entry_id is not None and entry.annual_expense_entry is not None
        )
        if has_income_link and has_expense_link:
            ambiguous_reasons["conflicting_legacy_references"] += 1
            continue
        resolution = _resolve_backfill_classification(entry)
        if resolution is None:
            ambiguous_reasons["missing_legacy_reference"] += 1
            continue

        flow_family, category_key, subcategory_key = resolution
        entry.flow_family = flow_family
        entry.category_key = category_key
        entry.subcategory_key = subcategory_key
        rows_to_update.append(entry)

    updated = len(rows_to_update)
    if updated and not dry_run:
        LedgerEntry.objects.bulk_update(
            rows_to_update,
            ["flow_family", "category_key", "subcategory_key"],
        )

    return LedgerClassificationBackfillResult(
        scanned=scanned,
        updated=updated,
        already_classified=already_classified,
        ambiguous=sum(ambiguous_reasons.values()),
        ambiguous_reasons=dict(sorted(ambiguous_reasons.items())),
        dry_run=dry_run,
    )


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
    flow_family: str = "",
    category_key: str = "",
    subcategory_key: str = "",
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
            flow_family=flow_family,
            category_key=category_key,
            subcategory_key=subcategory_key,
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
        flow_family=flow_family,
        category_key=category_key,
        subcategory_key=subcategory_key,
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
    flow_family: str = "",
    category_key: str = "",
    subcategory_key: str = "",
    principal_amount: Decimal | None = None,
    interest_amount: Decimal | None = None,
    liability_account: LedgerAccount | None = None,
    interest_account: LedgerAccount | None = None,
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


def _build_period_keys(*, start_year: int, end_year: int) -> list[tuple[int, int]]:
    return [(year, month) for year in range(start_year, end_year + 1) for month in range(1, 13)]


def _build_budget_suggestion_section(
    *,
    user_id: int,
    period_keys: list[tuple[int, int]],
    flow_family: str,
    positive_side: str,
) -> dict:
    start_year = period_keys[0][0]
    end_year = period_keys[-1][0]
    queryset = (
        LedgerEntry.objects.filter(
            transaction__user_id=user_id,
            transaction__status=LedgerTransaction.Status.POSTED,
            transaction__booking_date__year__gte=start_year,
            transaction__booking_date__year__lte=end_year,
        )
        .filter(
            Q(flow_family=flow_family)
            | Q(annual_income_entry__isnull=False)
            | Q(annual_expense_entry__isnull=False)
        )
        .select_related("transaction", "annual_income_entry", "annual_expense_entry")
        .only(
            "side",
            "amount",
            "flow_family",
            "category_key",
            "subcategory_key",
            "annual_income_entry_id",
            "annual_expense_entry_id",
            "transaction__booking_date",
            "annual_income_entry__category",
            "annual_income_entry__subcategory",
            "annual_expense_entry__category",
            "annual_expense_entry__subcategory",
        )
    )

    total_by_period: dict[tuple[int, int], Decimal] = defaultdict(lambda: ZERO)
    totals_by_category: dict[str, dict[tuple[int, int], Decimal]] = defaultdict(
        lambda: defaultdict(lambda: ZERO)
    )
    totals_by_subcategory: dict[tuple[str, str], dict[tuple[int, int], Decimal]] = defaultdict(
        lambda: defaultdict(lambda: ZERO)
    )

    for row in queryset:
        period_key = (row.transaction.booking_date.year, row.transaction.booking_date.month)
        if period_key not in period_keys:
            continue
        resolved_flow_family, category_key, subcategory_key = _resolve_budget_classification(row)
        if resolved_flow_family != flow_family or not category_key or not subcategory_key:
            continue
        signed_amount = row.amount if row.side == positive_side else -row.amount
        total_by_period[period_key] += signed_amount
        totals_by_category[category_key][period_key] += signed_amount
        totals_by_subcategory[(category_key, subcategory_key)][period_key] += signed_amount

    return {
        "series": _serialize_series(period_keys=period_keys, totals_by_period=total_by_period),
        "categories": _serialize_categorized_suggestions(
            period_keys=period_keys,
            totals_by_key=totals_by_category,
            include_subcategory=False,
        ),
        "subcategories": _serialize_categorized_suggestions(
            period_keys=period_keys,
            totals_by_key=totals_by_subcategory,
            include_subcategory=True,
        ),
    }


def _serialize_series(
    *, period_keys: list[tuple[int, int]], totals_by_period: dict[tuple[int, int], Decimal]
) -> list[dict]:
    return [
        {
            "year": year,
            "month": month,
            "executed_total": serialize_decimal(totals_by_period.get((year, month), ZERO)),
        }
        for year, month in period_keys
    ]


def _serialize_categorized_suggestions(
    *,
    period_keys: list[tuple[int, int]],
    totals_by_key: dict,
    include_subcategory: bool,
) -> list[dict]:
    window_months = Decimal(len(period_keys))
    rows: list[dict] = []
    for key, totals_by_period in sorted(totals_by_key.items(), key=lambda item: item[0]):
        month_points = _serialize_series(period_keys=period_keys, totals_by_period=totals_by_period)
        total = sum((totals_by_period.get(period_key, ZERO) for period_key in period_keys), ZERO)
        observed_months = sum(
            1 for period_key in period_keys if totals_by_period.get(period_key, ZERO) != ZERO
        )
        average_monthly = total / window_months if window_months > 0 else ZERO
        row = {
            "category": key[0] if include_subcategory else key,
            "months": month_points,
            "window_total": serialize_decimal(total),
            "observed_months": observed_months,
            "average_monthly": serialize_decimal(average_monthly),
            "suggested_annual": serialize_decimal(average_monthly * Decimal("12")),
        }
        if include_subcategory:
            row["subcategory"] = key[1]
        rows.append(row)
    return rows


def _resolve_budget_classification(entry: LedgerEntry) -> tuple[str, str, str]:
    if entry.flow_family and entry.category_key and entry.subcategory_key:
        return entry.flow_family, entry.category_key, entry.subcategory_key
    if entry.annual_income_entry_id is not None and entry.annual_income_entry is not None:
        return (
            cast(str, LedgerEntry.FlowFamily.INCOME),
            entry.annual_income_entry.category,
            entry.annual_income_entry.subcategory,
        )
    if entry.annual_expense_entry_id is not None and entry.annual_expense_entry is not None:
        return (
            cast(str, LedgerEntry.FlowFamily.EXPENSE),
            entry.annual_expense_entry.category,
            entry.annual_expense_entry.subcategory,
        )
    return "", "", ""


def _resolve_backfill_classification(
    entry: LedgerEntry,
) -> tuple[str, str, str] | None:
    has_income_link = (
        entry.annual_income_entry_id is not None and entry.annual_income_entry is not None
    )
    has_expense_link = (
        entry.annual_expense_entry_id is not None and entry.annual_expense_entry is not None
    )
    if has_income_link:
        return (
            cast(str, LedgerEntry.FlowFamily.INCOME),
            entry.annual_income_entry.category,
            entry.annual_income_entry.subcategory,
        )
    if has_expense_link:
        return (
            cast(str, LedgerEntry.FlowFamily.EXPENSE),
            entry.annual_expense_entry.category,
            entry.annual_expense_entry.subcategory,
        )
    return None
