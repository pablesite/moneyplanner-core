from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Callable

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    AnnualExpenseEntry,
    AnnualExpenseMonthlyCheckin,
    AnnualIncomeEntry,
    AnnualIncomeMonthlyCheckin,
    MonthlyClose,
)
from .services import (
    _build_ledger_monthly_execution_maps,
    _get_base_currency,
    _round_money,
    build_expense_monthly_plan_vs_executed_summary,
    build_income_monthly_plan_vs_executed_summary,
    normalize_annual_expense_taxonomy_keys,
    planned_expense_monthly_distribution,
    planned_income_monthly_distribution,
)

if TYPE_CHECKING:
    pass

from accounting.models import LedgerEntry, LedgerTransaction

logger = logging.getLogger(__name__)

MonthlyExecutionSlot = tuple[str, str, Decimal]
MonthlyExecutionSegment = tuple[str, str, str, Decimal]


def _prev_year_month(fiscal_year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return fiscal_year - 1, 12
    return fiscal_year, month - 1


def _get_previous_month_liquidity_total(*, user, fiscal_year: int, month: int) -> Decimal | None:
    """
    Fallback chain:
    1. MonthlyClose FINALIZED/LOCKED for prev month → liquidity_total_snapshot
    2. build_liquidity_monthly_summary executed_total
    3. None if no data available
    """
    from net_worth.services_liquidity import build_liquidity_monthly_summary

    prev_year, prev_month = _prev_year_month(fiscal_year, month)

    try:
        prev_close = MonthlyClose.objects.get(
            user=user,
            fiscal_year=prev_year,
            month=prev_month,
            status__in=[MonthlyClose.Status.FINALIZED, MonthlyClose.Status.LOCKED],
        )
        if prev_close.liquidity_total_snapshot is not None:
            return Decimal(prev_close.liquidity_total_snapshot)
    except MonthlyClose.DoesNotExist:
        pass

    try:
        summary = build_liquidity_monthly_summary(
            user=user,
            fiscal_year=prev_year,
            month=prev_month,
        )
        executed = summary.get("executed_total")
        if executed is not None:
            return Decimal(str(executed))
    except Exception:
        logger.exception(
            "Could not compute previous liquidity for user %s (%d/%d); using None",
            user,
            prev_year,
            prev_month,
        )

    return None


def _get_liquidity_adjustments_for_month(
    *, user, fiscal_year: int, month: int, base_currency: str
) -> tuple[Decimal, list[dict[str, str | int]]]:
    """Return explicit balance adjustments that explain the monthly liquidity delta."""
    from net_worth.services import (
        get_liquid_liability_queryset_for_user,
        get_liquidity_asset_queryset_for_user,
    )

    liquid_asset_ids = set(
        get_liquidity_asset_queryset_for_user(user=user).values_list("id", flat=True)
    )
    liquid_liability_ids = set(
        get_liquid_liability_queryset_for_user(user=user).values_list("id", flat=True)
    )
    if not liquid_asset_ids and not liquid_liability_ids:
        return Decimal("0"), []

    entries = list(
        LedgerEntry.objects.filter(
            transaction__user=user,
            transaction__status=LedgerTransaction.Status.POSTED,
            transaction__quick_entry_kind=LedgerTransaction.QuickEntryKind.ADJUSTMENT,
            transaction__booking_date__year=fiscal_year,
            transaction__booking_date__month=month,
        )
        .select_related("transaction", "account")
        .only(
            "id",
            "side",
            "amount",
            "currency",
            "account__name",
            "account__asset_id",
            "account__liability_id",
            "transaction__id",
            "transaction__booking_date",
            "transaction__description",
        )
    )
    relevant_entries = [
        entry
        for entry in entries
        if entry.account.asset_id in liquid_asset_ids
        or entry.account.liability_id in liquid_liability_ids
    ]
    if not relevant_entries:
        return Decimal("0"), []

    from .services import _convert_to_base, build_fx_cache

    fx_cache = build_fx_cache(
        {(entry.currency or base_currency).upper().strip() for entry in relevant_entries}
        | {base_currency}
    )
    total = Decimal("0")
    details: list[dict[str, str | int]] = []
    for entry in relevant_entries:
        amount = _convert_to_base(
            Decimal(entry.amount),
            entry.currency,
            base_currency,
            entry.transaction.booking_date,
            fx_cache,
        )
        signed_amount = amount if entry.side == LedgerEntry.Side.DEBIT else -amount
        total += signed_amount
        details.append(
            {
                "transaction_id": entry.transaction_id,
                "booking_date": entry.transaction.booking_date.isoformat(),
                "description": entry.transaction.description,
                "account_name": entry.account.name,
                "amount": str(_round_money(signed_amount)),
            }
        )

    return _round_money(total), details


def _monthly_execution_slots(
    *, summary: dict, breakdown_key: str, month: int
) -> list[MonthlyExecutionSlot]:
    slots: list[MonthlyExecutionSlot] = []
    breakdown = summary.get(breakdown_key) or {}
    for category in breakdown.get("categories", []):
        category_key = str(category.get("category") or "")
        for subcategory in category.get("subcategories", []):
            subcategory_key = str(subcategory.get("subcategory") or "")
            month_row = next(
                (row for row in subcategory.get("months", []) if row.get("month") == month),
                None,
            )
            amount = (
                Decimal(str(month_row.get("executed_total") or "0")) if month_row else Decimal("0")
            )
            if amount:
                slots.append((category_key, subcategory_key, amount))
    return slots


def _role_weights_for_month(
    *, summary: dict, month: int
) -> dict[tuple[str, str], dict[str, Decimal]]:
    weights: dict[tuple[str, str], dict[str, Decimal]] = {}
    for slot, slot_weights in (summary.get("_cashflow_role_weights") or {}).items():
        category, subcategory, slot_month = slot
        if slot_month == month:
            weights[(category, subcategory)] = slot_weights
    return weights


def _default_expense_role(category: str, subcategory: str) -> str:
    if category == AnnualExpenseEntry.Category.SAVINGS_ALLOCATION:
        return str(AnnualExpenseEntry.CashflowRole.SAVINGS)
    if category == AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS:
        return str(AnnualExpenseEntry.CashflowRole.INVESTMENT)
    if category in {
        AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS,
        AnnualExpenseEntry.Category.TANGIBLE_ASSETS,
    }:
        if subcategory == "real_estate_fees_taxes":
            return str(AnnualExpenseEntry.CashflowRole.TAX_FEE)
        return str(AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE)
    return str(AnnualExpenseEntry.CashflowRole.OPERATING)


def _default_income_role(category: str, _subcategory: str) -> str:
    if category == AnnualIncomeEntry.Category.CAPITAL_GAINS:
        return str(AnnualIncomeEntry.CashflowRole.ASSET_SALE)
    if category in {
        AnnualIncomeEntry.Category.TRANSFERS_SUPPORT,
        AnnualIncomeEntry.Category.PUBLIC_BENEFITS,
    }:
        return str(AnnualIncomeEntry.CashflowRole.TRANSFER)
    if category == AnnualIncomeEntry.Category.OTHER_INCOME:
        return str(AnnualIncomeEntry.CashflowRole.OTHER)
    return str(AnnualIncomeEntry.CashflowRole.OPERATING)


def _split_execution_slots_by_role(
    *,
    slots: list[MonthlyExecutionSlot],
    role_weights: dict[tuple[str, str], dict[str, Decimal]],
    default_role: Callable[[str, str], str],
) -> list[MonthlyExecutionSegment]:
    segments: list[MonthlyExecutionSegment] = []
    for category, subcategory, amount in slots:
        weights = role_weights.get((category, subcategory)) or {}
        weight_total = sum(weights.values(), Decimal("0"))
        if weight_total <= 0:
            segments.append((category, subcategory, default_role(category, subcategory), amount))
            continue
        for role, weight in weights.items():
            segments.append((category, subcategory, role, amount * weight / weight_total))
    return segments


def _build_monthly_financial_result(
    *,
    month: int,
    income_summary: dict,
    expense_summary: dict,
    income_executed: Decimal,
    expense_executed: Decimal,
) -> dict[str, str | None]:
    income_segments = _split_execution_slots_by_role(
        slots=_monthly_execution_slots(
            summary=income_summary,
            breakdown_key="income_execution_breakdown",
            month=month,
        ),
        role_weights=_role_weights_for_month(summary=income_summary, month=month),
        default_role=_default_income_role,
    )
    expense_segments = _split_execution_slots_by_role(
        slots=_monthly_execution_slots(
            summary=expense_summary,
            breakdown_key="expense_execution_breakdown",
            month=month,
        ),
        role_weights=_role_weights_for_month(summary=expense_summary, month=month),
        default_role=_default_expense_role,
    )

    classified_income = sum((segment[3] for segment in income_segments), Decimal("0"))
    eligible_income = sum(
        (
            amount
            for _category, _subcategory, role, amount in income_segments
            if role != AnnualIncomeEntry.CashflowRole.ASSET_SALE
        ),
        Decimal("0"),
    )
    if not income_segments:
        eligible_income = income_executed
    elif classified_income != income_executed:
        eligible_income += income_executed - classified_income

    contribution_roles = {
        AnnualExpenseEntry.CashflowRole.SAVINGS,
        AnnualExpenseEntry.CashflowRole.INVESTMENT,
    }
    living_roles = {
        AnnualExpenseEntry.CashflowRole.OPERATING,
        AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
        AnnualExpenseEntry.CashflowRole.TAX_FEE,
        AnnualExpenseEntry.CashflowRole.OTHER,
    }
    financial_contributions = sum(
        (
            amount
            for _category, _subcategory, role, amount in expense_segments
            if role in contribution_roles
        ),
        Decimal("0"),
    )
    living_expense = sum(
        (
            amount
            for _category, _subcategory, role, amount in expense_segments
            if role in living_roles
        ),
        Decimal("0"),
    )
    real_estate_formation = sum(
        (
            amount
            for category, _subcategory, role, amount in expense_segments
            if category == AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS
            and role == AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE
        ),
        Decimal("0"),
    )
    tangible_asset_purchases = sum(
        (
            amount
            for category, _subcategory, role, amount in expense_segments
            if category == AnnualExpenseEntry.Category.TANGIBLE_ASSETS
            and role == AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE
        ),
        Decimal("0"),
    )
    financial_savings = eligible_income - (expense_executed - financial_contributions)
    savings_rate = financial_savings / eligible_income if eligible_income > Decimal("0") else None
    other_outflows = max(
        Decimal("0"),
        expense_executed
        - financial_contributions
        - living_expense
        - real_estate_formation
        - tangible_asset_purchases,
    )

    return {
        "eligible_income": str(_round_money(eligible_income)),
        "total_outflows": str(_round_money(expense_executed)),
        "living_expense": str(_round_money(living_expense)),
        "financial_contributions": str(_round_money(financial_contributions)),
        "financial_savings": str(_round_money(financial_savings)),
        "savings_rate": (
            str(savings_rate.quantize(Decimal("0.0001"))) if savings_rate is not None else None
        ),
        "real_estate_formation": str(_round_money(real_estate_formation)),
        "tangible_asset_purchases": str(_round_money(tangible_asset_purchases)),
        "other_outflows": str(_round_money(other_outflows)),
    }


def _get_uncovered_income_entries_for_month(
    *, user, fiscal_year: int, month: int
) -> list[tuple[AnnualIncomeEntry, Decimal]]:
    """Returns (entry, planned_amount) pairs not covered by ledger or checkin."""
    entries = list(AnnualIncomeEntry.objects.filter(user=user, is_active=True))

    categorized_ledger = _build_ledger_monthly_execution_maps(
        user=user,
        fiscal_year=fiscal_year,
        flow_family=str(LedgerEntry.FlowFamily.INCOME),
        positive_side=str(LedgerEntry.Side.CREDIT),
        base_currency=_get_base_currency(user),
    )

    existing_checkins = set(
        AnnualIncomeMonthlyCheckin.objects.filter(
            user=user, fiscal_year=fiscal_year, month=month
        ).values_list("annual_income_entry_id", flat=True)
    )

    result = []
    for entry in entries:
        distribution = planned_income_monthly_distribution(entry=entry, fiscal_year=fiscal_year)
        planned_amount = distribution.get(month)
        if not planned_amount or planned_amount <= Decimal("0"):
            continue
        if (entry.category, entry.subcategory, month) in categorized_ledger:
            continue
        if entry.id in existing_checkins:
            continue
        result.append((entry, planned_amount))

    return result


def _get_uncovered_expense_entries_for_month(
    *, user, fiscal_year: int, month: int
) -> list[tuple[AnnualExpenseEntry, Decimal]]:
    """Returns (entry, planned_amount) pairs not covered by ledger or checkin."""
    entries = list(AnnualExpenseEntry.objects.filter(user=user, is_active=True))

    categorized_ledger = _build_ledger_monthly_execution_maps(
        user=user,
        fiscal_year=fiscal_year,
        flow_family=str(LedgerEntry.FlowFamily.EXPENSE),
        positive_side=str(LedgerEntry.Side.DEBIT),
        base_currency=_get_base_currency(user),
    )

    existing_checkins = set(
        AnnualExpenseMonthlyCheckin.objects.filter(
            user=user, fiscal_year=fiscal_year, month=month
        ).values_list("annual_expense_entry_id", flat=True)
    )

    result = []
    for entry in entries:
        distribution = planned_expense_monthly_distribution(entry=entry, fiscal_year=fiscal_year)
        planned_amount = distribution.get(month)
        if not planned_amount or planned_amount <= Decimal("0"):
            continue
        category, subcategory = normalize_annual_expense_taxonomy_keys(
            category=entry.category,
            subcategory=entry.subcategory,
        )
        if (category, subcategory, month) in categorized_ledger:
            continue
        if entry.id in existing_checkins:
            continue
        result.append((entry, planned_amount))

    return result


def compute_smart_distribution(
    *,
    uncovered_income: list[tuple[int, Decimal]],
    uncovered_expense: list[tuple[int, Decimal]],
    residual_net: Decimal | None = None,
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """
    Computes suggested amounts for uncovered income/expense entries.

    Uses budget amounts as prior. If residual_net is provided and planned net != 0,
    scales proportionally so that (sum_income - sum_expense) ≈ residual_net.
    The last item in each group absorbs any rounding delta.

    Returns (income_distribution, expense_distribution) as {entry_id: amount}.
    """
    if not uncovered_income and not uncovered_expense:
        return {}, {}

    planned_income_total = sum((amt for _, amt in uncovered_income), Decimal("0"))
    planned_expense_total = sum((amt for _, amt in uncovered_expense), Decimal("0"))
    planned_net = planned_income_total - planned_expense_total

    income_amounts: dict[int, Decimal] = {eid: amt for eid, amt in uncovered_income}
    expense_amounts: dict[int, Decimal] = {eid: amt for eid, amt in uncovered_expense}

    if residual_net is not None and planned_net != Decimal("0"):
        scale = residual_net / planned_net

        income_amounts = {
            eid: max(Decimal("0"), _round_money(amt * scale)) for eid, amt in uncovered_income
        }
        expense_amounts = {
            eid: max(Decimal("0"), _round_money(amt * scale)) for eid, amt in uncovered_expense
        }

        # Rounding adjustment: last item absorbs the delta
        if income_amounts and uncovered_income:
            target = _round_money(planned_income_total * scale)
            actual = sum(income_amounts.values(), Decimal("0"))
            delta = _round_money(target - actual)
            if delta:
                last_id = uncovered_income[-1][0]
                income_amounts[last_id] = max(
                    Decimal("0"), _round_money(income_amounts[last_id] + delta)
                )

        if expense_amounts and uncovered_expense:
            target = _round_money(planned_expense_total * scale)
            actual = sum(expense_amounts.values(), Decimal("0"))
            delta = _round_money(target - actual)
            if delta:
                last_id = uncovered_expense[-1][0]
                expense_amounts[last_id] = max(
                    Decimal("0"), _round_money(expense_amounts[last_id] + delta)
                )

    return income_amounts, expense_amounts


def apply_distribution_to_checkins(
    *,
    user,
    fiscal_year: int,
    month: int,
    income_distribution: dict[int, Decimal],
    expense_distribution: dict[int, Decimal],
) -> tuple[int, int]:
    """
    Creates AnnualIncomeMonthlyCheckin and AnnualExpenseMonthlyCheckin with
    status=estimated for each entry in the distribution, skipping existing ones.

    Returns (income_created_count, expense_created_count).
    """
    now = timezone.now()
    income_created = 0
    expense_created = 0

    for entry_id, amount in income_distribution.items():
        _, created = AnnualIncomeMonthlyCheckin.objects.get_or_create(
            user=user,
            annual_income_entry_id=entry_id,
            fiscal_year=fiscal_year,
            month=month,
            defaults={
                "status": AnnualIncomeMonthlyCheckin.Status.ESTIMATED,
                "executed_amount": amount,
                "confirmed_at": now,
            },
        )
        if created:
            income_created += 1

    for entry_id, amount in expense_distribution.items():
        _, created = AnnualExpenseMonthlyCheckin.objects.get_or_create(
            user=user,
            annual_expense_entry_id=entry_id,
            fiscal_year=fiscal_year,
            month=month,
            defaults={
                "status": AnnualExpenseMonthlyCheckin.Status.ESTIMATED,
                "executed_amount": amount,
                "confirmed_at": now,
            },
        )
        if created:
            expense_created += 1

    return income_created, expense_created


def compute_monthly_close_state(*, user, fiscal_year: int, month: int) -> dict:
    """
    Returns the full state of a monthly close for the given user/year/month.

    Computes income, expense and liquidity summaries, detects coverage level,
    calculates delta liquidity, and generates smart distribution suggestions
    for any uncovered entries.
    """
    from net_worth.services_liquidity import build_liquidity_monthly_summary

    monthly_close, _ = MonthlyClose.objects.get_or_create(
        user=user,
        fiscal_year=fiscal_year,
        month=month,
        defaults={"status": MonthlyClose.Status.DRAFT},
    )

    base_currency = _get_base_currency(user)
    income_summary = build_income_monthly_plan_vs_executed_summary(
        user=user,
        fiscal_year=fiscal_year,
        include_role_weights=True,
        base_currency=base_currency,
    )
    expense_summary = build_expense_monthly_plan_vs_executed_summary(
        user=user,
        fiscal_year=fiscal_year,
        include_role_weights=True,
        base_currency=base_currency,
    )
    liquidity_summary = build_liquidity_monthly_summary(
        user=user, fiscal_year=fiscal_year, month=month
    )
    income_month_data = next(
        (m for m in income_summary.get("months", []) if m["month"] == month), None
    )
    expense_month_data = next(
        (m for m in expense_summary.get("months", []) if m["month"] == month), None
    )

    income_executed = Decimal(income_month_data["executed"] if income_month_data else "0")
    expense_executed = Decimal(expense_month_data["executed"] if expense_month_data else "0")
    perimeter_internal_expense = Decimal(
        str(liquidity_summary.get("perimeter_internal_expense_total") or "0")
    )
    external_expense_executed = max(Decimal("0"), expense_executed - perimeter_internal_expense)

    liquidity_executed_raw = liquidity_summary.get("executed_total")
    liquidity_executed = (
        Decimal(str(liquidity_executed_raw)) if liquidity_executed_raw is not None else None
    )

    income_coverage = (
        income_month_data.get("coverage_mode", "none") if income_month_data else "none"
    )
    expense_coverage = (
        expense_month_data.get("coverage_mode", "none") if expense_month_data else "none"
    )
    _liq_ratio = liquidity_summary.get("completion_ratio")
    liquidity_completion_ratio = float(_liq_ratio) if isinstance(_liq_ratio, (int, float)) else 0.0

    prev_liquidity = _get_previous_month_liquidity_total(
        user=user, fiscal_year=fiscal_year, month=month
    )

    delta_liquidity: Decimal | None = None
    if liquidity_executed is not None and prev_liquidity is not None:
        delta_liquidity = liquidity_executed - prev_liquidity

    liquidity_adjustments_total, liquidity_adjustments = _get_liquidity_adjustments_for_month(
        user=user,
        fiscal_year=fiscal_year,
        month=month,
        base_currency=base_currency,
    )
    financial_result = _build_monthly_financial_result(
        month=month,
        income_summary=income_summary,
        expense_summary=expense_summary,
        income_executed=income_executed,
        expense_executed=expense_executed,
    )

    uncovered_income = _get_uncovered_income_entries_for_month(
        user=user, fiscal_year=fiscal_year, month=month
    )
    uncovered_expense = _get_uncovered_expense_entries_for_month(
        user=user, fiscal_year=fiscal_year, month=month
    )

    has_gaps = bool(uncovered_income or uncovered_expense)
    suggestions_income: dict[str, str] = {}
    suggestions_expense: dict[str, str] = {}

    if has_gaps:
        residual_net: Decimal | None = None
        if delta_liquidity is not None:
            known_net = income_executed - external_expense_executed
            residual_net = delta_liquidity - known_net - liquidity_adjustments_total

        income_dist, expense_dist = compute_smart_distribution(
            uncovered_income=[(e.id, amt) for e, amt in uncovered_income],
            uncovered_expense=[(e.id, amt) for e, amt in uncovered_expense],
            residual_net=residual_net,
        )
        suggestions_income = {str(k): str(v) for k, v in income_dist.items()}
        suggestions_expense = {str(k): str(v) for k, v in expense_dist.items()}

    from .services_settlement_preview import compute_monthly_close_settlement

    return {
        "monthly_close": {
            "id": monthly_close.id,
            "fiscal_year": monthly_close.fiscal_year,
            "month": monthly_close.month,
            "status": monthly_close.status,
            "finalized_at": (
                monthly_close.finalized_at.isoformat() if monthly_close.finalized_at else None
            ),
            "locked_at": (monthly_close.locked_at.isoformat() if monthly_close.locked_at else None),
            "income_total_snapshot": (
                str(monthly_close.income_total_snapshot)
                if monthly_close.income_total_snapshot is not None
                else None
            ),
            "expense_total_snapshot": (
                str(monthly_close.expense_total_snapshot)
                if monthly_close.expense_total_snapshot is not None
                else None
            ),
            "liquidity_total_snapshot": (
                str(monthly_close.liquidity_total_snapshot)
                if monthly_close.liquidity_total_snapshot is not None
                else None
            ),
            "opening_liquidity_snapshot": (
                str(monthly_close.opening_liquidity_snapshot)
                if monthly_close.opening_liquidity_snapshot is not None
                else None
            ),
            "expected_liquidity_total_snapshot": (
                str(monthly_close.expected_liquidity_total_snapshot)
                if monthly_close.expected_liquidity_total_snapshot is not None
                else None
            ),
            "residual_snapshot": (
                str(monthly_close.residual_snapshot)
                if monthly_close.residual_snapshot is not None
                else None
            ),
            "notes": monthly_close.notes,
        },
        "income": {
            "executed": str(income_executed),
            "planned": str(
                Decimal(income_month_data["planned"]) if income_month_data else Decimal("0")
            ),
            "coverage_mode": income_coverage,
            "completion_ratio": (
                float(income_month_data["completion_ratio"]) if income_month_data else 0.0
            ),
        },
        "expense": {
            "executed": str(expense_executed),
            "external_executed": str(external_expense_executed),
            "perimeter_internal_executed": str(perimeter_internal_expense),
            "planned": str(
                Decimal(expense_month_data["planned"]) if expense_month_data else Decimal("0")
            ),
            "coverage_mode": expense_coverage,
            "completion_ratio": (
                float(expense_month_data["completion_ratio"]) if expense_month_data else 0.0
            ),
        },
        "liquidity": {
            "current_total": str(liquidity_executed) if liquidity_executed is not None else None,
            "previous_total": str(prev_liquidity) if prev_liquidity is not None else None,
            "delta": str(delta_liquidity) if delta_liquidity is not None else None,
            "completion_ratio": liquidity_completion_ratio,
            "has_checkins": liquidity_completion_ratio > 0,
        },
        "liquidity_adjustments": {
            "total": str(liquidity_adjustments_total),
            "count": len(liquidity_adjustments),
            "entries": liquidity_adjustments,
        },
        "financial_result": financial_result,
        "has_gaps": has_gaps,
        "suggestions": {
            "income": suggestions_income,
            "expense": suggestions_expense,
        },
        "ownership_settlement": compute_monthly_close_settlement(
            user=user,
            fiscal_year=fiscal_year,
            month=month,
        ),
    }


def finalize_monthly_close(*, monthly_close: MonthlyClose, user) -> MonthlyClose:
    """DRAFT → FINALIZED. Freezes the reconciliation boundary for the next month."""
    with transaction.atomic():
        mc = MonthlyClose.objects.select_for_update().get(pk=monthly_close.pk)
        if mc.status != MonthlyClose.Status.DRAFT:
            raise ValueError(f"No se puede finalizar un cierre en estado '{mc.status}'.")

        state = compute_monthly_close_state(
            user=user,
            fiscal_year=mc.fiscal_year,
            month=mc.month,
        )

        mc.status = MonthlyClose.Status.FINALIZED
        mc.finalized_at = timezone.now()
        mc.income_total_snapshot = Decimal(state["income"]["executed"])
        mc.expense_total_snapshot = Decimal(state["expense"]["executed"])
        opening = state["liquidity"].get("previous_total")
        liq = state["liquidity"].get("current_total")
        external_expense = Decimal(state["expense"]["external_executed"])
        income = Decimal(state["income"]["executed"])
        liquidity_adjustments = Decimal(state.get("liquidity_adjustments", {}).get("total", "0"))
        mc.opening_liquidity_snapshot = Decimal(opening) if opening is not None else None
        mc.liquidity_total_snapshot = Decimal(liq) if liq is not None else None
        mc.expected_liquidity_total_snapshot = (
            _round_money(
                mc.opening_liquidity_snapshot + income - external_expense + liquidity_adjustments
            )
            if mc.opening_liquidity_snapshot is not None
            else None
        )
        mc.residual_snapshot = (
            _round_money(mc.liquidity_total_snapshot - mc.expected_liquidity_total_snapshot)
            if mc.liquidity_total_snapshot is not None
            and mc.expected_liquidity_total_snapshot is not None
            else None
        )
        from .services_settlement_preview import freeze_monthly_close_settlement

        freeze_monthly_close_settlement(monthly_close=mc, user=user)
        mc.save()
        try:
            from plan.services_monthly_close import MonthlyClosePlanService

            MonthlyClosePlanService().on_monthly_close_finalized(monthly_close=mc)
        except Exception:
            logger.exception("Could not run plan hook for monthly close %s", mc.pk)
        return mc


def reopen_monthly_close(*, monthly_close: MonthlyClose) -> MonthlyClose:
    """FINALIZED → DRAFT and invalidates every later finalized close."""
    with transaction.atomic():
        mc = MonthlyClose.objects.select_for_update().get(pk=monthly_close.pk)
        if mc.status != MonthlyClose.Status.FINALIZED:
            raise ValueError(
                f"Solo se puede reabrir un cierre finalizado (estado actual: '{mc.status}')."
            )
        later_closes = list(
            MonthlyClose.objects.select_for_update()
            .filter(user=mc.user)
            .filter(
                Q(fiscal_year__gt=mc.fiscal_year)
                | Q(fiscal_year=mc.fiscal_year, month__gt=mc.month)
            )
            .filter(status__in=[MonthlyClose.Status.FINALIZED, MonthlyClose.Status.LOCKED])
            .order_by("fiscal_year", "month")
        )
        closes_to_reopen = [mc, *later_closes]
        for close in closes_to_reopen:
            if close.status == MonthlyClose.Status.LOCKED:
                raise ValueError(
                    "No se puede reabrir porque existe un cierre posterior bloqueado. "
                    "Desbloquea la cadena desde el mes más reciente."
                )
            snapshot = getattr(close, "settlement_snapshot", None)
            if (
                snapshot is not None
                and snapshot.recommendations.filter(ledger_transactions__isnull=False).exists()
            ):
                raise ValueError(
                    "No se puede reabrir un cierre con movimientos de liquidación: "
                    "se conserva como histórico auditable."
                )

        from .services_settlement_preview import clear_monthly_close_settlement

        for close in closes_to_reopen:
            clear_monthly_close_settlement(monthly_close=close)
            close.status = MonthlyClose.Status.DRAFT
            close.finalized_at = None
            close.income_total_snapshot = None
            close.expense_total_snapshot = None
            close.opening_liquidity_snapshot = None
            close.liquidity_total_snapshot = None
            close.expected_liquidity_total_snapshot = None
            close.residual_snapshot = None
            close.save()
        return mc


def lock_monthly_close(*, monthly_close: MonthlyClose) -> MonthlyClose:
    """FINALIZED → LOCKED."""
    with transaction.atomic():
        mc = MonthlyClose.objects.select_for_update().get(pk=monthly_close.pk)
        if mc.status != MonthlyClose.Status.FINALIZED:
            raise ValueError(
                f"Solo se puede bloquear un cierre finalizado (estado actual: '{mc.status}')."
            )

        mc.status = MonthlyClose.Status.LOCKED
        mc.locked_at = timezone.now()
        mc.save()
        return mc
