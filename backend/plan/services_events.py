from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from budget.plan_lineage import parse_plan_event_id

from .models import FinancialPlan, PlanEvent
from .services_projection import ProjectionService

MONEY = Decimal("0.01")

BudgetEntryModel = type[AnnualExpenseEntry] | type[AnnualIncomeEntry]

BUDGET_MODELS: dict[str, BudgetEntryModel] = {
    "AnnualExpenseEntry": AnnualExpenseEntry,
    "AnnualIncomeEntry": AnnualIncomeEntry,
}


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
def register_occurred_event(
    *,
    plan: FinancialPlan,
    name: str,
    event_type: str,
    decision_date: date,
    expense_entry_ids: list[int] | None = None,
    income_entry_ids: list[int] | None = None,
    note: str = "",
) -> PlanEvent:
    """Registra una decision ya tomada y adopta las lineas de presupuesto que generó.

    A diferencia de aceptar un escenario, aquí no se crea nada en el presupuesto: las
    lineas ya existen. El evento nace en estado ``occurred``, que la proyección excluye
    (``plan_event_payloads`` solo lee eventos ``planned``), porque sus efectos ya están
    en el patrimonio y en el presupuesto actuales: volver a aplicarlos los contaría dos
    veces.
    """
    if decision_date > date.today():
        raise ValidationError(
            {"decision_date": "Una decisión ya tomada no puede tener fecha futura."}
        )

    event = PlanEvent.objects.create(
        plan=plan,
        name=name.strip(),
        event_type=event_type,
        planned_date=decision_date,
        actual_date=decision_date,
        status=PlanEvent.Status.OCCURRED,
        planned_impact_json={},
    )
    adopted = _adopt_budget_entries(
        event=event,
        expense_entry_ids=expense_entry_ids or [],
        income_entry_ids=income_entry_ids or [],
    )
    event.actual_impact_json = {
        "registration": {
            "decision_date": decision_date.isoformat(),
            "note": note.strip(),
            "adopted_lines": adopted,
        }
    }
    event.save(update_fields=["actual_impact_json", "updated_at"])
    return event


def _adopt_budget_entries(
    *, event: PlanEvent, expense_entry_ids: list[int], income_entry_ids: list[int]
) -> list[dict[str, Any]]:
    """Reetiqueta lineas existentes al evento, guardando su grupo previo para poder deshacer."""
    adopted: list[dict[str, Any]] = []
    for model_name, entry_ids in (
        ("AnnualExpenseEntry", expense_entry_ids),
        ("AnnualIncomeEntry", income_entry_ids),
    ):
        if not entry_ids:
            continue
        model = BUDGET_MODELS[model_name]
        entries = list(model.objects.filter(user=event.plan.user, id__in=entry_ids))
        missing = sorted(set(entry_ids) - {entry.id for entry in entries})
        if missing:
            raise ValidationError(
                {"budget_lines": f"Partidas inexistentes o de otro usuario: {missing}."}
            )
        for entry in entries:
            previous_group = entry.event_group or ""
            owner_id = parse_plan_event_id(previous_group)
            if owner_id is not None:
                raise ValidationError(
                    {
                        "budget_lines": (
                            f"«{entry.name}» ya pertenece a otro acontecimiento del plan."
                        )
                    }
                )
            # Las lineas derivadas de un activo o pasivo se sincronizan buscando por
            # su propio event_group: si se lo cambiamos, la siguiente sincronizacion
            # no las encontraria y crearia un duplicado. Su linaje ya es el activo.
            if getattr(entry, "source_liability_id", None) or getattr(
                entry, "source_asset_id", None
            ):
                raise ValidationError(
                    {
                        "budget_lines": (
                            f"«{entry.name}» la genera un activo o pasivo de Patrimonio "
                            "y se gestiona desde allí."
                        )
                    }
                )
            entry.event_group = f"plan_event:{event.id}"
            entry.save(update_fields=["event_group"])
            adopted.append(
                {
                    "model": model_name,
                    "id": entry.id,
                    "name": entry.name,
                    "fiscal_year": entry.fiscal_year,
                    "amount_annual": str(entry.amount_annual),
                    "previous_event_group": previous_group,
                }
            )
    return adopted


@transaction.atomic
def release_occurred_event(*, event: PlanEvent) -> dict[str, Any]:
    """Deshace un registro retrospectivo: devuelve cada linea a su grupo previo y borra el evento.

    Necesario porque adoptar una linea la vuelve ``is_plan_managed`` y el presupuesto
    bloquea su edicion: sin marcha atras, un registro erroneo dejaria partidas reales
    congeladas.
    """
    if event.status != PlanEvent.Status.OCCURRED:
        raise ValidationError(
            {"status": "Solo se pueden deshacer los acontecimientos registrados como ocurridos."}
        )

    event_group = f"plan_event:{event.id}"
    released: list[dict[str, Any]] = []
    for line in event.actual_impact_json.get("registration", {}).get("adopted_lines", []):
        model = BUDGET_MODELS.get(str(line.get("model")))
        if model is None:
            continue
        updated = model.objects.filter(
            user=event.plan.user, id=line["id"], event_group=event_group
        ).update(event_group=line.get("previous_event_group") or "")
        if updated:
            released.append(line)
    event.delete()
    return {"released_lines": released}


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
