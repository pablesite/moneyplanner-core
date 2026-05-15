from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import cast

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Min, Q, QuerySet, Sum
from rest_framework.exceptions import ValidationError

from accounts.models import UserSettings
from core.services import build_fx_cache, convert_currency_cached
from memberships.models import Ownership, OwnershipLink, OwnershipSplit

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .services_ledger import (
    LedgerBalanceTotals,
    ZERO,
    compute_account_balance_from_totals,
    serialize_decimal,
)


@dataclass
class DailyBalanceAccounts:
    account_rows: list[dict]
    account_data_by_id: dict[int, dict[str, str]]
    account_multiplier_by_id: dict[int, Decimal]

    @property
    def account_ids(self) -> list[int]:
        return list(self.account_data_by_id.keys())


@dataclass
class DailyBalanceContext:
    accounts: DailyBalanceAccounts
    date_from: date
    date_to: date
    status: str
    ownership_id: int | None
    ownership_is_null: bool | None
    base_currency: str
    fx_cache: dict[tuple[str, str], list[tuple[date, Decimal]]]


@dataclass(frozen=True)
class DailyBalanceEntryTotal:
    account_id: int
    side: str
    amount: Decimal
    booking_date: date | None = None


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

    current_entries_queryset = _build_account_balance_entries_queryset(
        user_id=user_id,
        account_type=account_type,
        status=status,
    )

    period_entries_queryset = current_entries_queryset
    if fiscal_year is not None:
        period_entries_queryset = period_entries_queryset.filter(
            transaction__booking_date__year=fiscal_year
        )
    if month is not None:
        period_entries_queryset = period_entries_queryset.filter(
            transaction__booking_date__month=month
        )

    current_totals_by_account = _aggregate_balance_totals_by_account(current_entries_queryset)
    period_totals_by_account = _aggregate_balance_totals_by_account(period_entries_queryset)
    investment_contributed_totals = _aggregate_investment_contributed_by_account(
        current_entries_queryset
    )

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
    ownership_id: int | None = None,
    ownership_is_null: bool | None = None,
) -> dict:
    context = _build_daily_balance_context(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        ownership_id=ownership_id,
        ownership_is_null=ownership_is_null,
    )
    rows = (
        _build_daily_balance_rows(user_id=user_id, context=context)
        if context.accounts.account_ids
        else _build_empty_daily_rows(date_from=context.date_from, date_to=context.date_to)
    )
    return {
        "filters": _build_daily_balance_filters(context=context),
        "rows": rows,
        "base_currency": context.base_currency,
    }


def _build_daily_balance_context(
    *,
    user_id: int,
    date_from: date | None,
    date_to: date,
    status: str,
    ownership_id: int | None,
    ownership_is_null: bool | None,
) -> DailyBalanceContext:
    accounts = _load_daily_balance_accounts(
        user_id=user_id,
        ownership_id=ownership_id,
        ownership_is_null=ownership_is_null,
    )
    resolved_date_from = _resolve_daily_balance_start_date(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        account_ids=accounts.account_ids,
    )
    if resolved_date_from > date_to:
        raise ValidationError({"date_from": "'date_from' no puede ser posterior a 'date_to'."})

    base_currency = _get_user_base_currency(user_id=user_id)
    return DailyBalanceContext(
        accounts=accounts,
        date_from=resolved_date_from,
        date_to=date_to,
        status=status,
        ownership_id=ownership_id,
        ownership_is_null=ownership_is_null,
        base_currency=base_currency,
        fx_cache=_build_daily_balance_fx_cache(
            base_currency=base_currency,
            account_data_by_id=accounts.account_data_by_id,
        ),
    )


def _load_daily_balance_accounts(
    *,
    user_id: int,
    ownership_id: int | None,
    ownership_is_null: bool | None,
) -> DailyBalanceAccounts:
    account_rows = _load_active_balance_account_rows(user_id=user_id)
    account_multiplier_by_id = {int(row["id"]): Decimal("1") for row in account_rows}
    if ownership_id is not None or ownership_is_null:
        account_rows = _filter_account_rows_by_ownership(
            user_id=user_id,
            account_rows=account_rows,
            account_multiplier_by_id=account_multiplier_by_id,
            ownership_id=ownership_id,
            ownership_is_null=ownership_is_null,
        )
    account_data_by_id = {
        int(row["id"]): {
            "account_type": str(row["account_type"]),
            "currency": str(row["currency"]),
        }
        for row in account_rows
    }
    return DailyBalanceAccounts(
        account_rows=account_rows,
        account_data_by_id=account_data_by_id,
        account_multiplier_by_id=account_multiplier_by_id,
    )


def _load_active_balance_account_rows(*, user_id: int) -> list[dict]:
    return list(
        LedgerAccount.objects.filter(
            user_id=user_id,
            is_active=True,
            account_type__in=[LedgerAccount.AccountType.ASSET, LedgerAccount.AccountType.LIABILITY],
        )
        .values("id", "account_type", "currency", "asset_id", "liability_id")
        .order_by("id")
    )


def _filter_account_rows_by_ownership(
    *,
    user_id: int,
    account_rows: list[dict],
    account_multiplier_by_id: dict[int, Decimal],
    ownership_id: int | None,
    ownership_is_null: bool | None,
) -> list[dict]:
    ownership_context = _load_daily_balance_ownership_context(
        user_id=user_id,
        ownership_id=ownership_id,
    )
    filtered_rows: list[dict] = []
    for row in account_rows:
        owner_id = _get_account_row_owner_id(row=row, ownership_context=ownership_context)
        if ownership_is_null:
            if owner_id is None:
                filtered_rows.append(row)
            continue
        multiplier = _resolve_account_ownership_multiplier(
            owner_id=owner_id,
            ownership_id=ownership_id,
            shared_ratio_by_ownership_id=ownership_context["shared_ratio_by_ownership_id"],
        )
        if multiplier > ZERO:
            filtered_rows.append(row)
            account_multiplier_by_id[int(row["id"])] = multiplier
    return filtered_rows


def _load_daily_balance_ownership_context(
    *,
    user_id: int,
    ownership_id: int | None,
) -> dict[str, dict]:
    links = list(
        OwnershipLink.objects.filter(
            user_id=user_id,
            target_type__in=[
                OwnershipLink.TargetType.ASSET,
                OwnershipLink.TargetType.LIABILITY,
            ],
        ).values("ownership_id", "target_type", "target_id")
    )
    ownership_ids_in_links = {
        int(link["ownership_id"]) for link in links if link.get("ownership_id") is not None
    }
    if ownership_id is not None:
        ownership_ids_in_links.add(ownership_id)
    ownership_rows = list(
        Ownership.objects.filter(
            user_id=user_id,
            id__in=ownership_ids_in_links,
        ).values("id", "kind", "member_id")
    )
    ownership_by_id = {int(row["id"]): row for row in ownership_rows}
    return {
        "asset_owner_by_target_id": _build_owner_map(
            links=links,
            target_type=cast(str, OwnershipLink.TargetType.ASSET),
        ),
        "liability_owner_by_target_id": _build_owner_map(
            links=links,
            target_type=cast(str, OwnershipLink.TargetType.LIABILITY),
        ),
        "shared_ratio_by_ownership_id": _build_shared_ratio_by_ownership_id(
            user_id=user_id,
            selected_ownership=ownership_by_id.get(ownership_id)
            if ownership_id is not None
            else None,
        ),
    }


def _build_owner_map(*, links: list[dict], target_type: str) -> dict[int, int]:
    return {
        int(link["target_id"]): int(link["ownership_id"])
        for link in links
        if str(link["target_type"]) == target_type
    }


def _build_shared_ratio_by_ownership_id(
    *,
    user_id: int,
    selected_ownership: dict | None,
) -> dict[int, Decimal]:
    selected_member_id = (
        int(selected_ownership["member_id"])
        if selected_ownership
        and str(selected_ownership["kind"]) == Ownership.Kind.INDIVIDUAL
        and selected_ownership.get("member_id") is not None
        else None
    )
    if selected_member_id is None:
        return {}
    split_rows = list(
        OwnershipSplit.objects.filter(
            ownership__user_id=user_id,
            ownership__kind=Ownership.Kind.SHARED,
            member_id=selected_member_id,
        ).values("ownership_id", "percent")
    )
    return {
        int(row["ownership_id"]): Decimal(row["percent"]) / Decimal("100") for row in split_rows
    }


def _get_account_row_owner_id(*, row: dict, ownership_context: dict[str, dict]) -> int | None:
    account_type = str(row["account_type"])
    if account_type == LedgerAccount.AccountType.ASSET:
        target_id = row.get("asset_id")
        return (
            ownership_context["asset_owner_by_target_id"].get(int(target_id))
            if target_id is not None
            else None
        )
    target_id = row.get("liability_id")
    return (
        ownership_context["liability_owner_by_target_id"].get(int(target_id))
        if target_id is not None
        else None
    )


def _resolve_account_ownership_multiplier(
    *,
    owner_id: int | None,
    ownership_id: int | None,
    shared_ratio_by_ownership_id: dict[int, Decimal],
) -> Decimal:
    if ownership_id is None or owner_id is None:
        return ZERO
    if owner_id == ownership_id:
        return Decimal("1")
    return shared_ratio_by_ownership_id.get(owner_id, ZERO)


def _resolve_daily_balance_start_date(
    *,
    user_id: int,
    date_from: date | None,
    date_to: date,
    status: str,
    account_ids: list[int],
) -> date:
    if date_from is not None:
        return date_from
    if not account_ids:
        return date_to
    earliest_entries = LedgerEntry.objects.filter(
        transaction__user_id=user_id,
        account_id__in=account_ids,
        transaction__status=status,
    )
    return (
        earliest_entries.aggregate(min_booking_date=Min("transaction__booking_date"))[
            "min_booking_date"
        ]
        or date_to
    )


def _get_user_base_currency(*, user_id: int) -> str:
    return (
        (
            UserSettings.objects.filter(user_id=user_id)
            .values_list("base_currency", flat=True)
            .first()
            or "EUR"
        )
        .strip()
        .upper()
    )


def _build_daily_balance_fx_cache(
    *,
    base_currency: str,
    account_data_by_id: dict[int, dict[str, str]],
) -> dict[tuple[str, str], list[tuple[date, Decimal]]]:
    fx_pivot = (os.getenv("FX_PIVOT", "USD") or "USD").strip().upper()
    currencies_for_fx = {base_currency, *{meta["currency"] for meta in account_data_by_id.values()}}
    if fx_pivot:
        currencies_for_fx.add(fx_pivot)
    return build_fx_cache(currencies_for_fx)


def _build_daily_balance_filters(*, context: DailyBalanceContext) -> dict:
    return {
        "date_from": context.date_from.isoformat(),
        "date_to": context.date_to.isoformat(),
        "status": context.status,
        "ownership_id": context.ownership_id,
        "ownership_is_null": context.ownership_is_null,
        "base_currency": context.base_currency,
    }


def _build_daily_balance_rows(*, user_id: int, context: DailyBalanceContext) -> list[dict]:
    historical_entries, ranged_entries = _load_daily_balance_entries(
        user_id=user_id,
        context=context,
    )
    running_balance_by_account = _build_opening_running_balance_by_account(
        account_ids=context.accounts.account_ids,
        account_data_by_id=context.accounts.account_data_by_id,
        historical_entries=historical_entries,
    )
    deltas_by_date = _group_daily_balance_deltas_by_date(
        account_data_by_id=context.accounts.account_data_by_id,
        ranged_entries=ranged_entries,
    )
    return _serialize_daily_balance_rows(
        context=context,
        running_balance_by_account=running_balance_by_account,
        deltas_by_date=deltas_by_date,
    )


def _load_daily_balance_entries(
    *,
    user_id: int,
    context: DailyBalanceContext,
) -> tuple[list[DailyBalanceEntryTotal], list[DailyBalanceEntryTotal]]:
    account_ids = context.accounts.account_ids
    historical_rows = (
        LedgerEntry.objects.filter(
            transaction__user_id=user_id,
            account_id__in=account_ids,
            transaction__booking_date__lt=context.date_from,
            transaction__status=context.status,
        )
        .values("account_id", "side")
        .annotate(amount_total=Sum("amount"))
        .order_by("account_id", "side")
    )
    ranged_rows = (
        LedgerEntry.objects.filter(
            transaction__user_id=user_id,
            account_id__in=account_ids,
            transaction__booking_date__gte=context.date_from,
            transaction__booking_date__lte=context.date_to,
            transaction__status=context.status,
        )
        .values("transaction__booking_date", "account_id", "side")
        .annotate(amount_total=Sum("amount"))
        .order_by("transaction__booking_date", "account_id", "side")
    )
    historical_entries = [
        DailyBalanceEntryTotal(
            account_id=int(row["account_id"]),
            side=str(row["side"]),
            amount=Decimal(row["amount_total"] or ZERO),
        )
        for row in historical_rows
    ]
    ranged_entries = [
        DailyBalanceEntryTotal(
            booking_date=cast(date, row["transaction__booking_date"]),
            account_id=int(row["account_id"]),
            side=str(row["side"]),
            amount=Decimal(row["amount_total"] or ZERO),
        )
        for row in ranged_rows
    ]
    return historical_entries, ranged_entries


def _build_opening_running_balance_by_account(
    *,
    account_ids: list[int],
    account_data_by_id: dict[int, dict[str, str]],
    historical_entries: list[DailyBalanceEntryTotal],
) -> dict[int, Decimal]:
    running_balance_by_account = {account_id: ZERO for account_id in account_ids}
    for entry in historical_entries:
        account_id = int(entry.account_id)
        account_data = account_data_by_id.get(account_id)
        if account_data is None:
            continue
        signed_impact = _entry_balance_impact(
            account_type=account_data["account_type"],
            side=entry.side,
            amount=entry.amount,
        )
        running_balance_by_account[account_id] = (
            running_balance_by_account.get(account_id, ZERO) + signed_impact
        )
    return running_balance_by_account


def _group_daily_balance_deltas_by_date(
    *,
    account_data_by_id: dict[int, dict[str, str]],
    ranged_entries: list[DailyBalanceEntryTotal],
) -> dict[date, dict[int, Decimal]]:
    deltas_by_date: dict[date, dict[int, Decimal]] = defaultdict(dict)
    for entry in ranged_entries:
        account_id = int(entry.account_id)
        account_data = account_data_by_id.get(account_id)
        if account_data is None:
            continue
        signed_impact = _entry_balance_impact(
            account_type=account_data["account_type"],
            side=entry.side,
            amount=entry.amount,
        )
        booking_date = entry.booking_date
        if booking_date is None:
            continue
        day_deltas = deltas_by_date[booking_date]
        day_deltas[account_id] = day_deltas.get(account_id, ZERO) + signed_impact
    return deltas_by_date


def _serialize_daily_balance_rows(
    *,
    context: DailyBalanceContext,
    running_balance_by_account: dict[int, Decimal],
    deltas_by_date: dict[date, dict[int, Decimal]],
) -> list[dict]:
    rows: list[dict] = []
    cursor = context.date_from
    while cursor <= context.date_to:
        _apply_daily_balance_deltas(
            running_balance_by_account=running_balance_by_account,
            day_delta_by_account=deltas_by_date.get(cursor),
        )
        rows.append(
            _serialize_daily_balance_row(
                context=context,
                running_balance_by_account=running_balance_by_account,
                cursor=cursor,
            )
        )
        cursor += timedelta(days=1)
    return rows


def _apply_daily_balance_deltas(
    *,
    running_balance_by_account: dict[int, Decimal],
    day_delta_by_account: dict[int, Decimal] | None,
) -> None:
    if not day_delta_by_account:
        return
    for account_id, delta in day_delta_by_account.items():
        running_balance_by_account[account_id] = (
            running_balance_by_account.get(account_id, ZERO) + delta
        )


def _serialize_daily_balance_row(
    *,
    context: DailyBalanceContext,
    running_balance_by_account: dict[int, Decimal],
    cursor: date,
) -> dict:
    assets_total = ZERO
    liabilities_total = ZERO
    for account_id, running_balance in running_balance_by_account.items():
        account_data = context.accounts.account_data_by_id.get(account_id)
        if account_data is None:
            continue
        account_multiplier = context.accounts.account_multiplier_by_id.get(
            account_id,
            Decimal("1"),
        )
        if account_multiplier <= ZERO:
            continue
        amount_base = _convert_entry_amount_to_base_currency(
            amount=running_balance,
            currency=account_data["currency"],
            booking_date=cursor,
            base_currency=context.base_currency,
            fx_cache=context.fx_cache,
        )
        amount_base *= account_multiplier
        if account_data["account_type"] == LedgerAccount.AccountType.ASSET:
            assets_total += amount_base
        else:
            liabilities_total += amount_base

    net_balance = assets_total - liabilities_total
    return {
        "date": cursor.isoformat(),
        "assets_total": serialize_decimal(assets_total),
        "liabilities_total": serialize_decimal(liabilities_total),
        "net_balance": serialize_decimal(net_balance),
    }


def validate_budget_suggestion_filters(*, lookback_years: int) -> None:
    if lookback_years < 1 or lookback_years > 5:
        raise ValidationError({"lookback_years": "Query param 'lookback_years' invalido."})


def _build_account_balance_entries_queryset(
    *,
    user_id: int,
    account_type: str | None,
    status: str | None,
) -> QuerySet[LedgerEntry]:
    queryset = LedgerEntry.objects.filter(transaction__user_id=user_id)
    if account_type:
        queryset = queryset.filter(account__account_type=account_type)
    if status:
        queryset = queryset.filter(transaction__status=status)
    return queryset


def _aggregate_balance_totals_by_account(
    entries_queryset: QuerySet[LedgerEntry],
) -> dict[int, LedgerBalanceTotals]:
    grouped: dict[int, dict[str, Decimal]] = defaultdict(lambda: {"debit": ZERO, "credit": ZERO})
    rows = (
        entries_queryset.values("account_id", "side")
        .annotate(amount_total=Sum("amount"))
        .order_by("account_id", "side")
    )
    for row in rows:
        grouped[int(row["account_id"])][str(row["side"])] += Decimal(row["amount_total"] or ZERO)
    return {
        account_id: LedgerBalanceTotals(
            debit_total=totals["debit"],
            credit_total=totals["credit"],
        )
        for account_id, totals in grouped.items()
    }


def _build_period_keys(*, start_year: int, end_year: int) -> list[tuple[int, int]]:
    return [(year, month) for year in range(start_year, end_year + 1) for month in range(1, 13)]


def _aggregate_investment_contributed_by_account(
    entries_queryset: QuerySet[LedgerEntry],
) -> dict[int, tuple[Decimal, Decimal]]:
    grouped: dict[int, tuple[Decimal, Decimal]] = defaultdict(lambda: (ZERO, ZERO))
    rows = (
        entries_queryset.filter(account__asset_id__isnull=False)
        .filter(
            Q(transaction__quick_entry_kind="")
            | Q(transaction__quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT)
        )
        .values("account_id", "side")
        .annotate(amount_total=Sum("amount"))
        .order_by("account_id", "side")
    )
    for row in rows:
        account_id = int(row["account_id"])
        amount = Decimal(row["amount_total"] or ZERO)
        inflow_total, outflow_total = grouped[account_id]
        if row["side"] == LedgerEntry.Side.DEBIT:
            inflow_total += amount
        elif row["side"] == LedgerEntry.Side.CREDIT:
            outflow_total += amount
        grouped[account_id] = (inflow_total, outflow_total)
    return grouped


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
