from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
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

from accounting.models import LedgerEntry


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
        pass

    return None


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

    income_summary = build_income_monthly_plan_vs_executed_summary(
        user=user, fiscal_year=fiscal_year
    )
    expense_summary = build_expense_monthly_plan_vs_executed_summary(
        user=user, fiscal_year=fiscal_year
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
            residual_net = delta_liquidity - known_net

        income_dist, expense_dist = compute_smart_distribution(
            uncovered_income=[(e.id, amt) for e, amt in uncovered_income],
            uncovered_expense=[(e.id, amt) for e, amt in uncovered_expense],
            residual_net=residual_net,
        )
        suggestions_income = {str(k): str(v) for k, v in income_dist.items()}
        suggestions_expense = {str(k): str(v) for k, v in expense_dist.items()}

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
        "has_gaps": has_gaps,
        "suggestions": {
            "income": suggestions_income,
            "expense": suggestions_expense,
        },
    }


def finalize_monthly_close(*, monthly_close: MonthlyClose, user) -> MonthlyClose:
    """DRAFT → FINALIZED. Takes snapshot of current totals."""
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
        liq = state["liquidity"].get("current_total")
        mc.liquidity_total_snapshot = Decimal(liq) if liq is not None else None
        mc.save()
        return mc


def reopen_monthly_close(*, monthly_close: MonthlyClose) -> MonthlyClose:
    """FINALIZED → DRAFT. Clears snapshot fields."""
    with transaction.atomic():
        mc = MonthlyClose.objects.select_for_update().get(pk=monthly_close.pk)
        if mc.status != MonthlyClose.Status.FINALIZED:
            raise ValueError(
                f"Solo se puede reabrir un cierre finalizado (estado actual: '{mc.status}')."
            )

        mc.status = MonthlyClose.Status.DRAFT
        mc.finalized_at = None
        mc.income_total_snapshot = None
        mc.expense_total_snapshot = None
        mc.liquidity_total_snapshot = None
        mc.save()
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
