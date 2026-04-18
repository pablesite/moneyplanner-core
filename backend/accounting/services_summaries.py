from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Min
from rest_framework.exceptions import ValidationError

from accounts.models import UserSettings
from core.services import build_fx_cache, convert_currency_cached

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .services_ledger import (
    LedgerBalanceTotals,
    ZERO,
    compute_account_balance_from_totals,
    serialize_decimal,
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

    from .services_budget import _resolve_budget_classification

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
        transaction__user_id=user_id,
    ).select_related("transaction", "account")
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

    current_entries = list(current_entries_queryset)
    period_entries = list(period_entries_queryset)

    current_totals_by_account = _group_balance_totals_by_account(current_entries)
    period_totals_by_account = _group_balance_totals_by_account(period_entries)
    investment_contributed_totals = _group_investment_contributed_by_account(current_entries)

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
        inflow_total, outflow_total = investment_contributed_totals.get(account.id, (ZERO, ZERO))
        net_contributed = inflow_total - outflow_total
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
                "investment_inflow_total": serialize_decimal(inflow_total),
                "investment_outflow_total": serialize_decimal(outflow_total),
                "investment_net_contributed": serialize_decimal(net_contributed),
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


def build_daily_balance_series(
    *,
    user_id: int,
    date_from: date | None,
    date_to: date,
    status: str = LedgerTransaction.Status.POSTED,
) -> dict:
    account_rows = list(
        LedgerAccount.objects.filter(
            user_id=user_id,
            is_active=True,
            account_type__in=[LedgerAccount.AccountType.ASSET, LedgerAccount.AccountType.LIABILITY],
        )
        .values("id", "account_type", "currency")
        .order_by("id")
    )
    account_data_by_id = {
        int(row["id"]): {"account_type": str(row["account_type"]), "currency": str(row["currency"])}
        for row in account_rows
    }
    account_ids = list(account_data_by_id.keys())
    base_currency = (
        (
            UserSettings.objects.filter(user_id=user_id)
            .values_list("base_currency", flat=True)
            .first()
            or "EUR"
        )
        .strip()
        .upper()
    )
    fx_pivot = (os.getenv("FX_PIVOT", "USD") or "USD").strip().upper()
    currencies_for_fx = {base_currency, *{meta["currency"] for meta in account_data_by_id.values()}}
    if fx_pivot:
        currencies_for_fx.add(fx_pivot)
    fx_cache = build_fx_cache(currencies_for_fx)

    if date_from is None and account_ids:
        date_from = (
            LedgerEntry.objects.filter(
                transaction__user_id=user_id,
                account_id__in=account_ids,
                transaction__status=status,
            ).aggregate(min_booking_date=Min("transaction__booking_date"))["min_booking_date"]
            or date_to
        )
    if date_from is None:
        date_from = date_to
    if date_from > date_to:
        raise ValidationError({"date_from": "'date_from' no puede ser posterior a 'date_to'."})

    if not account_ids:
        return {
            "filters": {
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "status": status,
                "base_currency": base_currency,
            },
            "rows": _build_empty_daily_rows(date_from=date_from, date_to=date_to),
            "base_currency": base_currency,
        }

    historical_entries = LedgerEntry.objects.filter(
        transaction__user_id=user_id,
        account_id__in=account_ids,
        transaction__booking_date__lt=date_from,
        transaction__status=status,
    ).select_related("transaction")
    ranged_entries = LedgerEntry.objects.filter(
        transaction__user_id=user_id,
        account_id__in=account_ids,
        transaction__booking_date__gte=date_from,
        transaction__booking_date__lte=date_to,
        transaction__status=status,
    ).select_related("transaction")

    assets_total = ZERO
    liabilities_total = ZERO
    for entry in historical_entries:
        account_data = account_data_by_id.get(entry.account_id)
        if account_data is None:
            continue
        account_type = account_data["account_type"]
        entry_amount_base = _convert_entry_amount_to_base_currency(
            amount=entry.amount,
            currency=entry.currency,
            booking_date=entry.transaction.booking_date,
            base_currency=base_currency,
            fx_cache=fx_cache,
        )
        signed_impact = _entry_balance_impact(
            account_type=account_type,
            side=entry.side,
            amount=entry_amount_base,
        )
        if account_type == LedgerAccount.AccountType.ASSET:
            assets_total += signed_impact
        else:
            liabilities_total += signed_impact

    deltas_by_date: dict[date, dict[str, Decimal]] = defaultdict(
        lambda: {"assets": ZERO, "liabilities": ZERO}
    )
    for entry in ranged_entries:
        account_data = account_data_by_id.get(entry.account_id)
        if account_data is None:
            continue
        account_type = account_data["account_type"]
        entry_amount_base = _convert_entry_amount_to_base_currency(
            amount=entry.amount,
            currency=entry.currency,
            booking_date=entry.transaction.booking_date,
            base_currency=base_currency,
            fx_cache=fx_cache,
        )
        signed_impact = _entry_balance_impact(
            account_type=account_type,
            side=entry.side,
            amount=entry_amount_base,
        )
        booking_date = entry.transaction.booking_date
        if account_type == LedgerAccount.AccountType.ASSET:
            deltas_by_date[booking_date]["assets"] += signed_impact
        else:
            deltas_by_date[booking_date]["liabilities"] += signed_impact

    rows: list[dict] = []
    cursor = date_from
    while cursor <= date_to:
        delta = deltas_by_date.get(cursor)
        if delta:
            assets_total += delta["assets"]
            liabilities_total += delta["liabilities"]
        net_balance = assets_total - liabilities_total
        rows.append(
            {
                "date": cursor.isoformat(),
                "assets_total": serialize_decimal(assets_total),
                "liabilities_total": serialize_decimal(liabilities_total),
                "net_balance": serialize_decimal(net_balance),
            }
        )
        cursor += timedelta(days=1)

    return {
        "filters": {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "status": status,
            "base_currency": base_currency,
        },
        "rows": rows,
        "base_currency": base_currency,
    }


def validate_budget_suggestion_filters(*, lookback_years: int) -> None:
    if lookback_years < 1 or lookback_years > 5:
        raise ValidationError({"lookback_years": "Query param 'lookback_years' invalido."})


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


def _group_investment_contributed_by_account(
    entries: list[LedgerEntry],
) -> dict[int, tuple[Decimal, Decimal]]:
    totals: dict[int, tuple[Decimal, Decimal]] = defaultdict(lambda: (ZERO, ZERO))
    for entry in entries:
        if entry.account.asset_id is None:
            continue
        tx_kind = str(getattr(entry.transaction, "quick_entry_kind", "") or "").strip()
        if tx_kind and tx_kind != "investment":
            continue
        inflow_total, outflow_total = totals[entry.account_id]
        if entry.side == LedgerEntry.Side.DEBIT:
            inflow_total += entry.amount
        elif entry.side == LedgerEntry.Side.CREDIT:
            outflow_total += entry.amount
        totals[entry.account_id] = (inflow_total, outflow_total)
    return totals


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


def _entry_balance_impact(*, account_type: str, side: str, amount: Decimal) -> Decimal:
    if account_type == LedgerAccount.AccountType.ASSET:
        return amount if side == LedgerEntry.Side.DEBIT else -amount
    if account_type == LedgerAccount.AccountType.LIABILITY:
        return amount if side == LedgerEntry.Side.CREDIT else -amount
    return ZERO


def _convert_entry_amount_to_base_currency(
    *,
    amount: Decimal,
    currency: str,
    booking_date: date,
    base_currency: str,
    fx_cache: dict[tuple[str, str], list[tuple[date, Decimal]]],
) -> Decimal:
    normalized_currency = str(currency or "").strip().upper() or base_currency
    if normalized_currency == base_currency:
        return amount
    try:
        return convert_currency_cached(
            amount,
            normalized_currency,
            base_currency,
            rate_date=booking_date,
            fx_cache=fx_cache,
        )
    except DjangoValidationError as exc:
        raise ValidationError(
            {
                "fx": (
                    "No se pudo convertir importes de "
                    f"{normalized_currency} a {base_currency} para {booking_date.isoformat()}."
                )
            }
        ) from exc


def _build_empty_daily_rows(*, date_from: date, date_to: date) -> list[dict]:
    rows: list[dict] = []
    cursor = date_from
    while cursor <= date_to:
        rows.append(
            {
                "date": cursor.isoformat(),
                "assets_total": serialize_decimal(ZERO),
                "liabilities_total": serialize_decimal(ZERO),
                "net_balance": serialize_decimal(ZERO),
            }
        )
        cursor += timedelta(days=1)
    return rows
