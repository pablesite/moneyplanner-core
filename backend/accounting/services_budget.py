from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from django.db import transaction
from django.db.models import Q

from .models import LedgerEntry, LedgerTransaction
from .services_ledger import ZERO
from .services_summaries import _build_period_keys, _serialize_series


@dataclass(frozen=True)
class LedgerClassificationBackfillResult:
    scanned: int
    updated: int
    already_classified: int
    ambiguous: int
    ambiguous_reasons: dict[str, int]
    dry_run: bool


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
            "window_total": str(total.quantize(Decimal("0.01"))),
            "observed_months": observed_months,
            "average_monthly": str(average_monthly.quantize(Decimal("0.01"))),
            "suggested_annual": str((average_monthly * Decimal("12")).quantize(Decimal("0.01"))),
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
