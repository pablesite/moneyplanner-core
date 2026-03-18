from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .models import LedgerAccount, LedgerEntry
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
