from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from budget.serializers import ownership_compatibility_name
from memberships.models import Ownership
from budget.plan_lineage import parse_plan_event_id
from net_worth.models import Asset, Liability

from .models import FinancialPlan, PlanEvent, Scenario
from .services_projection import (
    ProjectionService,
    build_projection_inputs,
    debt_annual_payment,
    earliest_sustainable_retirement_year,
    get_assumption_set,
    serialize_assumptions,
)
from .services_scenarios import (
    default_debt_budget_mapping,
    end_date_from_term,
    recurring_year_slots,
)
from .services_scenarios import comparison_delta

MONEY = Decimal("0.01")
PLANNED_DECISION_FINANCING_NOTE = "Generado automaticamente desde Mi Plan: financiacion prevista."

BudgetEntryModel = type[AnnualExpenseEntry] | type[AnnualIncomeEntry]

BUDGET_MODELS: dict[str, BudgetEntryModel] = {
    "AnnualExpenseEntry": AnnualExpenseEntry,
    "AnnualIncomeEntry": AnnualIncomeEntry,
}


def assign_event_budget_ownership(*, event: PlanEvent, ownership: Ownership | None) -> None:
    """Keep the event and every plan-managed budget line on the same ownership."""
    owner_name = ownership_compatibility_name(ownership) if ownership else ""
    event_group = f"plan_event:{event.id}"
    for model in (AnnualIncomeEntry, AnnualExpenseEntry):
        model.objects.filter(user=event.plan.user, event_group=event_group).update(
            ownership=ownership, owner_name=owner_name
        )


def preview_planned_decision(
    *,
    plan: FinancialPlan,
    event_type: str,
    transaction_year: int,
    transaction_month: int,
    impact: dict[str, Any],
    assumption_name: str,
    replaced_event: PlanEvent | None = None,
    expense_entry_ids: list[int] | None = None,
    income_entry_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Compara una decisión candidata sin persistir ningún efecto en el plan."""
    assumption_set = get_assumption_set(name=assumption_name)
    assumptions = serialize_assumptions(assumption_set)
    current_prepared = build_projection_inputs(plan=plan)
    payload = _decision_impact_event(
        start_year=transaction_year,
        start_month=transaction_month,
        end_year=None,
        impact=impact,
    ) | {
        "event_type": event_type,
        "baseline_absorbed": transaction_year <= date.today().year,
    }
    simulated_prepared = build_projection_inputs(
        plan=plan,
        extra_events=[payload],
        excluded_plan_event_ids={replaced_event.id} if replaced_event else None,
        excluded_one_off_expense_ids=set(expense_entry_ids or []),
        excluded_one_off_income_ids=set(income_entry_ids or []),
    )
    service = ProjectionService()
    current = service.calculate(plan=plan, assumption_set=assumption_set, prepared=current_prepared)
    simulated = service.calculate(
        plan=plan,
        assumption_set=assumption_set,
        extra_events=[payload],
        prepared=simulated_prepared,
    )
    sustainable_year = {
        "current": earliest_sustainable_retirement_year(
            inputs=current_prepared[0], assumptions=assumptions
        ),
        "simulated": earliest_sustainable_retirement_year(
            inputs=simulated_prepared[0], assumptions=assumptions
        ),
    }
    return {
        "current": current,
        "simulated": simulated,
        "sustainable_year": sustainable_year,
        "delta": comparison_delta(
            current=current,
            simulated=simulated,
            sustainable_year=sustainable_year,
        ),
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
    ownership: Ownership | None = None,
    expense_entry_ids: list[int] | None = None,
    income_entry_ids: list[int] | None = None,
    asset_ids: list[int] | None = None,
    liability_ids: list[int] | None = None,
    note: str = "",
) -> PlanEvent:
    """Registra una decision ya tomada: adopta sus lineas manuales y apunta a lo real.

    A diferencia de aceptar un escenario, aquí no se crea nada en el presupuesto: las
    lineas ya existen. El evento nace en estado ``occurred``, que la proyección excluye
    (``plan_event_payloads`` solo lee eventos ``planned``), porque sus efectos ya están
    en el patrimonio y en el presupuesto actuales: volver a aplicarlos los contaría dos
    veces.

    Los activos y pasivos se *enlazan*, no se adoptan: Patrimonio sigue siendo su dueño
    y quien genera sus lineas de presupuesto. Enlazar es lo que permite que la decisión
    cuente su impacto completo (desembolso + deuda contraída) sin robarle el linaje.
    """
    if decision_date > date.today():
        raise ValidationError(
            {"decision_date": "Una decisión ya tomada no puede tener fecha futura."}
        )

    event = PlanEvent.objects.create(
        plan=plan,
        name=name.strip(),
        event_type=event_type,
        ownership=ownership,
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
    assign_event_budget_ownership(event=event, ownership=ownership)
    linked = _link_net_worth(
        event=event, asset_ids=asset_ids or [], liability_ids=liability_ids or []
    )
    event.actual_impact_json = {
        "registration": {
            "decision_date": decision_date.isoformat(),
            "note": note.strip(),
            "adopted_lines": adopted,
            "linked": linked,
        }
    }
    event.save(update_fields=["actual_impact_json", "updated_at"])
    return event


def _decision_impact_event(
    *, start_year: int, start_month: int, end_year: int | None, impact: dict[str, Any]
) -> dict[str, Any]:
    """Construye el payload de impacto de una Decisión planificada, con las mismas
    claves que `scenario_event_payload` para que la proyección lo aplique en su año
    (compra: `new_asset_*`/`new_debt_*`/`initial_outflow`; venta: `disposed_*`/`proceeds`)."""

    def money(key: str) -> str:
        value = impact.get(key)
        return str(value) if value is not None else "0"

    term = impact.get("new_debt_term_years")
    term_years = int(term) if term else None
    debt_end_year = (
        start_year + max(0, term_years - 1) + (1 if start_month > 1 else 0) if term_years else None
    )
    return {
        "start_year": int(start_year),
        "start_month": int(start_month),
        "start_date": date(int(start_year), int(start_month), 1).isoformat(),
        "end_year": int(end_year) if end_year else None,
        "initial_outflow": money("initial_outflow"),
        "monthly_expense_delta": money("monthly_expense_delta"),
        "monthly_income_delta": "0",
        "monthly_contribution_delta": "0",
        "monthly_contribution_destination": "productive",
        "new_asset_value": money("new_asset_value"),
        "new_asset_type": impact.get("new_asset_type"),
        "new_debt_principal": money("new_debt_principal"),
        "new_debt_interest_rate": money("new_debt_interest_rate"),
        "new_debt_term_years": term_years,
        "debt_end_year": debt_end_year,
        "disposed_asset_value": money("disposed_asset_value"),
        "disposed_asset_type": impact.get("disposed_asset_type"),
        "proceeds": money("proceeds"),
        "disposed_liability_value": money("disposed_liability_value"),
    }


def _replace_planned_decision_financing_entries(
    *, event: PlanEvent, payload: dict[str, Any]
) -> int:
    """Mantiene en Presupuesto la cuota que el motor ya proyecta para la decisión."""
    event_group = f"plan_event:{event.id}"
    AnnualExpenseEntry.objects.filter(
        user=event.plan.user,
        event_group=event_group,
        is_system_generated=True,
        notes=PLANNED_DECISION_FINANCING_NOTE,
    ).delete()

    principal = Decimal(str(payload.get("new_debt_principal") or "0"))
    term_years = int(str(payload.get("new_debt_term_years") or "0"))
    if principal <= 0 or term_years <= 0:
        return 0

    start = date(int(payload["start_year"]), int(payload.get("start_month") or 1), 1)
    term_months = term_years * 12
    annual_payment = debt_annual_payment(
        principal=principal,
        annual_rate=Decimal(str(payload.get("new_debt_interest_rate") or "0")),
        term_years=term_years,
    )
    monthly_payment = annual_payment / Decimal("12")
    category, subcategory, cashflow_role = default_debt_budget_mapping(event.event_type)
    created = 0
    for slot in recurring_year_slots(
        start=start,
        end=end_date_from_term(start, term_months),
    ):
        AnnualExpenseEntry.objects.create(
            user=event.plan.user,
            is_system_generated=True,
            name=f"{event.name} - financiacion",
            category=category,
            subcategory=subcategory,
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=slot.time_profile,
            cashflow_role=cashflow_role,
            event_group=event_group,
            ownership=event.ownership,
            owner_name=ownership_compatibility_name(event.ownership) if event.ownership else "",
            term_start_month=slot.term_start_month,
            term_end_year=slot.term_end_year,
            term_end_month=slot.term_end_month,
            amount_annual=slot.amount(monthly_payment),
            fiscal_year=slot.fiscal_year,
            currency="EUR",
            notes=PLANNED_DECISION_FINANCING_NOTE,
        )
        created += 1
    return created


@transaction.atomic
def register_planned_decision(
    *,
    plan: FinancialPlan,
    name: str,
    event_type: str,
    decision_date: date,
    ownership: Ownership | None = None,
    transaction_year: int,
    transaction_month: int = 1,
    expense_entry_ids: list[int] | None = None,
    income_entry_ids: list[int] | None = None,
    asset_ids: list[int] | None = None,
    liability_ids: list[int] | None = None,
    impact: dict[str, Any] | None = None,
    end_year: int | None = None,
    note: str = "",
) -> PlanEvent:
    """Agrupa partidas puntuales existentes en una Decisión *planificada* con impacto
    en la proyección (compra o venta de activo), en su ``transaction_year``.

    Adopta las líneas seleccionadas (salen de la vía de flujos puntuales de Fase 1 y
    pasan a gobernarse por la Decisión) y enlaza el activo/pasivo real. A diferencia de
    ``register_occurred_event``, nace ``planned`` y **sí** aporta impacto proyectado.
    """
    payload = _decision_impact_event(
        start_year=transaction_year,
        start_month=transaction_month,
        end_year=end_year,
        impact=impact or {},
    )
    event = PlanEvent.objects.create(
        plan=plan,
        name=name.strip(),
        event_type=event_type,
        ownership=ownership,
        planned_date=decision_date,
        status=PlanEvent.Status.PLANNED,
        planned_impact_json={"events": [payload]},
    )
    adopted = _adopt_budget_entries(
        event=event,
        expense_entry_ids=expense_entry_ids or [],
        income_entry_ids=income_entry_ids or [],
    )
    assign_event_budget_ownership(event=event, ownership=ownership)
    linked = _link_net_worth(
        event=event, asset_ids=asset_ids or [], liability_ids=liability_ids or []
    )
    _replace_planned_decision_financing_entries(event=event, payload=payload)
    event.actual_impact_json = {
        "registration": {
            "decision_date": decision_date.isoformat(),
            "transaction_year": int(transaction_year),
            "transaction_month": int(transaction_month),
            "note": note.strip(),
            "adopted_lines": adopted,
            "linked": linked,
        }
    }
    event.save(update_fields=["actual_impact_json", "updated_at"])
    ProjectionService().recalculate(plan=plan)
    return event


@transaction.atomic
def update_planned_decision(
    *,
    event: PlanEvent,
    name: str,
    event_type: str,
    decision_date: date,
    ownership: Ownership | None = None,
    transaction_year: int,
    transaction_month: int,
    impact: dict[str, Any],
    end_year: int | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Corrige una Decisión futura y mantiene sincronizado su único origen de presupuesto."""
    locked = PlanEvent.objects.select_for_update().select_related("plan").get(pk=event.pk)
    registration = deepcopy(locked.actual_impact_json.get("registration") or {})
    if locked.status != PlanEvent.Status.PLANNED:
        raise ValidationError(
            {"event": "Solo se pueden editar las decisiones que siguen previstas."}
        )

    if locked.source_scenario_id:
        scenario = Scenario.objects.select_for_update().get(pk=locked.source_scenario_id)
        return _update_scenario_backed_decision(
            event=locked,
            scenario=scenario,
            name=name,
            event_type=event_type,
            ownership=ownership,
            decision_date=decision_date,
            transaction_year=transaction_year,
            transaction_month=transaction_month,
            impact=impact,
        )

    if "adopted_lines" not in registration:
        raise ValidationError(
            {"event": "La decisión no tiene partidas agrupadas que se puedan editar."}
        )

    locked.name = name.strip()
    locked.event_type = event_type
    if ownership is not None:
        locked.ownership = ownership
    locked.planned_date = decision_date
    payload = _decision_impact_event(
        start_year=transaction_year,
        start_month=transaction_month,
        end_year=end_year,
        impact=impact,
    )
    locked.planned_impact_json = {"events": [payload]}
    registration.update(
        {
            "decision_date": decision_date.isoformat(),
            "transaction_year": int(transaction_year),
            "transaction_month": int(transaction_month),
            "note": note.strip(),
        }
    )
    locked.actual_impact_json = {
        **deepcopy(locked.actual_impact_json),
        "registration": registration,
    }
    locked.save(
        update_fields=[
            "name",
            "event_type",
            "ownership",
            "planned_date",
            "planned_impact_json",
            "actual_impact_json",
            "updated_at",
        ]
    )
    _replace_planned_decision_financing_entries(event=locked, payload=payload)
    assign_event_budget_ownership(event=locked, ownership=locked.ownership)
    projection = ProjectionService().recalculate(plan=locked.plan)
    return {"event": locked, "projection": projection}


def _update_scenario_backed_decision(
    *,
    event: PlanEvent,
    scenario: Scenario,
    name: str,
    event_type: str,
    ownership: Ownership | None,
    decision_date: date,
    transaction_year: int,
    transaction_month: int,
    impact: dict[str, Any],
) -> dict[str, Any]:
    """Edita una simulación ya incorporada y reconstruye solo sus líneas gestionadas."""
    from .services_scenarios import (
        budget_lines_for_scenario,
        create_budget_entries_for_scenario,
        scenario_event_payloads,
    )

    scenario_events = list(scenario.events.select_for_update().order_by("start_date", "id"))
    if len(scenario_events) != 1:
        raise ValidationError(
            {"event": "Solo se pueden editar simulaciones con un único acontecimiento."}
        )

    scenario_event = scenario_events[0]
    original_outflow = Decimal(scenario_event.initial_outflow)
    one_off_items = list(scenario_event.metadata_json.get("one_off_items", []))
    new_outflow = Decimal(impact.get("initial_outflow", original_outflow))
    if len(one_off_items) > 1 and new_outflow != original_outflow:
        raise ValidationError(
            {"impact": "Edita los desembolsos con detalle antes de cambiar su total."}
        )

    scenario.name = name.strip()
    scenario.template_type = event_type
    scenario.save(update_fields=["name", "template_type"])

    scenario_event.start_date = date(transaction_year, transaction_month, 1)
    scenario_event.initial_outflow = new_outflow
    scenario_event.monthly_expense_delta = Decimal(
        impact.get("monthly_expense_delta", scenario_event.monthly_expense_delta)
    )
    scenario_event.new_asset_value = Decimal(
        impact.get("new_asset_value", scenario_event.new_asset_value)
    )
    scenario_event.new_asset_type = impact.get("new_asset_type", scenario_event.new_asset_type)
    scenario_event.new_debt_principal = Decimal(
        impact.get("new_debt_principal", scenario_event.new_debt_principal)
    )
    scenario_event.new_debt_interest_rate = impact.get(
        "new_debt_interest_rate", scenario_event.new_debt_interest_rate
    )
    term_years = impact.get("new_debt_term_years")
    if term_years:
        scenario_event.new_debt_term_months = int(term_years) * 12
    elif "new_debt_principal" in impact and not impact["new_debt_principal"]:
        scenario_event.new_debt_term_months = None
    if len(one_off_items) == 1:
        metadata = deepcopy(scenario_event.metadata_json)
        metadata["one_off_items"][0]["amount"] = str(new_outflow)
        scenario_event.metadata_json = metadata
    scenario_event.save()

    event.name = scenario.name
    event.event_type = scenario.template_type
    if ownership is not None:
        event.ownership = ownership
    event.planned_date = decision_date
    event.planned_impact_json = {
        "events": scenario_event_payloads(scenario=scenario),
        "budget_lines": [
            line.__dict__ | {"amount": str(line.amount)}
            for line in budget_lines_for_scenario(scenario)
        ],
    }
    event.save(
        update_fields=[
            "name",
            "event_type",
            "ownership",
            "planned_date",
            "planned_impact_json",
            "updated_at",
        ]
    )

    event_group = f"plan_event:{event.id}"
    AnnualIncomeEntry.objects.filter(user=event.plan.user, event_group=event_group).delete()
    AnnualExpenseEntry.objects.filter(user=event.plan.user, event_group=event_group).delete()
    create_budget_entries_for_scenario(scenario=scenario, plan_event=event)
    assign_event_budget_ownership(event=event, ownership=event.ownership)
    projection = ProjectionService().recalculate(plan=event.plan)
    return {"event": event, "projection": projection}


def _link_net_worth(
    *, event: PlanEvent, asset_ids: list[int], liability_ids: list[int]
) -> dict[str, list[dict[str, Any]]]:
    assets = list(Asset.objects.filter(user=event.plan.user, id__in=asset_ids))
    liabilities = list(Liability.objects.filter(user=event.plan.user, id__in=liability_ids))
    missing_assets = sorted(set(asset_ids) - {asset.id for asset in assets})
    missing_liabilities = sorted(set(liability_ids) - {liability.id for liability in liabilities})
    if missing_assets or missing_liabilities:
        raise ValidationError(
            {
                "linked": (
                    "Activos o pasivos inexistentes o de otro usuario: "
                    f"{missing_assets + missing_liabilities}."
                )
            }
        )
    event.linked_assets.set(assets)
    event.linked_liabilities.set(liabilities)
    return {
        "assets": [{"id": asset.id, "name": asset.name} for asset in assets],
        "liabilities": [{"id": liability.id, "name": liability.name} for liability in liabilities],
    }


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
