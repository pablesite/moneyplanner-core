from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry

from .models import PlanEvent
from .services_projection import ProjectionService

MONEY = Decimal("0.01")


def _q2(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _snapshot(entry) -> dict[str, Any]:
    return {
        "model": entry.__class__.__name__,
        "id": entry.id,
        "fiscal_year": entry.fiscal_year,
        "amount_annual": str(entry.amount_annual),
        "time_profile": entry.time_profile,
        "term_start_month": entry.term_start_month,
        "term_end_year": entry.term_end_year,
        "term_end_month": entry.term_end_month,
    }


def _partial_amount(entry, *, end_month: int) -> Decimal:
    start_month = int(entry.term_start_month or 1)
    original_end_month = int(entry.term_end_month or 12)
    original_months = max(1, original_end_month - start_month + 1)
    kept_months = max(0, end_month - start_month + 1)
    return _q2(Decimal(entry.amount_annual) * Decimal(kept_months) / Decimal(original_months))


def _clone_for_partial_year(entry, *, fiscal_year: int, end_month: int):
    clone = entry.__class__.objects.get(pk=entry.pk)
    clone.pk = None
    clone.fiscal_year = fiscal_year
    clone.time_profile = entry.__class__.TimeProfile.TERM_RECURRENT
    clone.term_start_month = 1
    clone.term_end_year = fiscal_year
    clone.term_end_month = end_month
    clone.amount_annual = _q2(Decimal(entry.amount_annual) * Decimal(end_month) / Decimal("12"))
    clone.save()
    return clone


def _retire_budget_entries(*, event: PlanEvent, effective_date: date) -> dict[str, list[dict]]:
    event_group = f"plan_event:{event.id}"
    changed: list[dict] = []
    deleted: list[dict] = []
    end_year = effective_date.year
    end_month = effective_date.month - 1

    for model in (AnnualIncomeEntry, AnnualExpenseEntry):
        entries = list(model.objects.filter(user=event.plan.user, event_group=event_group))
        for entry in entries:
            if entry.time_profile == model.TimeProfile.ONE_OFF:
                continue
            before = _snapshot(entry)
            if entry.fiscal_year > end_year or (entry.fiscal_year == end_year and end_month == 0):
                entry.delete()
                deleted.append(before)
                continue
            if entry.time_profile == model.TimeProfile.STRUCTURAL_RECURRENT:
                if entry.fiscal_year < end_year:
                    entry.time_profile = model.TimeProfile.TERM_RECURRENT
                    entry.term_start_month = entry.term_start_month or 1
                    entry.term_end_year = end_year - 1
                    entry.term_end_month = 12
                    entry.save(
                        update_fields=[
                            "time_profile",
                            "term_start_month",
                            "term_end_year",
                            "term_end_month",
                        ]
                    )
                    changed.append({"before": before, "after": _snapshot(entry)})
                    if end_month > 0:
                        partial = _clone_for_partial_year(
                            entry, fiscal_year=end_year, end_month=end_month
                        )
                        changed.append({"before": None, "after": _snapshot(partial)})
                    continue
                entry.amount_annual = _q2(Decimal(entry.amount_annual) * Decimal(end_month) / 12)
                entry.time_profile = model.TimeProfile.TERM_RECURRENT
                entry.term_start_month = 1
                entry.term_end_year = end_year
                entry.term_end_month = end_month
                entry.save()
                changed.append({"before": before, "after": _snapshot(entry)})
                continue
            if entry.fiscal_year < end_year:
                if entry.term_end_year is not None and entry.term_end_year < end_year:
                    continue
                entry.term_end_year = end_year - 1
                entry.term_end_month = 12
                entry.save(update_fields=["term_end_year", "term_end_month"])
                changed.append({"before": before, "after": _snapshot(entry)})
                if end_month > 0:
                    partial = _clone_for_partial_year(
                        entry, fiscal_year=end_year, end_month=end_month
                    )
                    changed.append({"before": None, "after": _snapshot(partial)})
                continue
            if (
                entry.term_end_year == end_year
                and entry.term_end_month is not None
                and entry.term_end_month <= end_month
            ):
                continue
            if end_month < int(entry.term_start_month or 1):
                entry.delete()
                deleted.append(before)
                continue
            entry.amount_annual = _partial_amount(entry, end_month=end_month)
            entry.term_end_year = end_year
            entry.term_end_month = end_month
            entry.save(update_fields=["amount_annual", "term_end_year", "term_end_month"])
            changed.append({"before": before, "after": _snapshot(entry)})
    return {"changed": changed, "deleted": deleted}


@transaction.atomic
def close_plan_event(
    *, event: PlanEvent, effective_date: date, disposal_note: str = ""
) -> dict[str, Any]:
    locked = (
        PlanEvent.objects.select_for_update().select_related("plan", "plan__user").get(pk=event.pk)
    )
    if locked.effective_end_date is not None:
        raise ValidationError({"effective_date": "El acontecimiento ya está cerrado."})
    if effective_date < locked.planned_date:
        raise ValidationError(
            {"effective_date": "La fecha efectiva no puede ser anterior a la fecha planificada."}
        )

    budget_changes = _retire_budget_entries(event=locked, effective_date=effective_date)
    locked.effective_end_date = effective_date
    locked.actual_impact_json = {
        **locked.actual_impact_json,
        "closure": {
            "effective_date": effective_date.isoformat(),
            "note": disposal_note.strip(),
            "budget_lines_changed": budget_changes["changed"],
            "budget_lines_deleted": budget_changes["deleted"],
        },
    }
    locked.save(update_fields=["effective_end_date", "actual_impact_json", "updated_at"])
    projection = ProjectionService().recalculate(plan=locked.plan)
    return {"event": locked, "projection": projection, "budget_changes": budget_changes}
