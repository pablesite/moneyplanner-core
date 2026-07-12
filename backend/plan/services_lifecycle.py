"""Ciclo de vida de una decision: previsto -> materializado, o previsto -> cancelado.

La frontera es: **el plan es dueño del futuro; Patrimonio, del presente y del
compromiso adquirido.** Mientras una decision es previsión vive solo en el plan
(lineas de presupuesto futuras) y puede borrarse sin tocar la realidad. Cuando se
materializa, la verdad se muda a Patrimonio: nace el activo o el pasivo real, con su
cuadro de amortizacion, y es el quien genera desde entonces las lineas de verdad.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast

from django.db import transaction
from rest_framework.exceptions import ValidationError

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from net_worth.models import Asset, Liability
from net_worth.services_liabilities_budget import (
    sync_generated_budget_commitments_for_liability,
)

from .models import PlanAssetFunction, PlanEvent, Scenario
from .services_projection import ProjectionService
from .services_scenarios import default_debt_budget_mapping

ASSET_TEMPLATE_MAPPING: dict[str, tuple[str, str]] = {
    str(Scenario.TemplateType.VEHICLE): (
        str(Asset.Category.VEHICLE),
        str(Asset.Subcategory.VEHICLES),
    ),
    str(Scenario.TemplateType.HOUSING): (
        str(Asset.Category.REAL_ESTATE),
        str(Asset.Subcategory.SECOND_HOME),
    ),
    str(Scenario.TemplateType.RENOVATION): (
        str(Asset.Category.REAL_ESTATE),
        str(Asset.Subcategory.PRIMARY_HOME),
    ),
    str(Scenario.TemplateType.BUSINESS): (
        str(Asset.Category.INVESTMENTS),
        str(Asset.Subcategory.OTHER),
    ),
}

LIABILITY_TEMPLATE_MAPPING: dict[str, str] = {
    str(Scenario.TemplateType.HOUSING): cast(str, Liability.Category.MORTGAGE),
}


def _event_payloads(event: PlanEvent) -> list[dict[str, Any]]:
    payloads = event.planned_impact_json.get("events", [])
    if not payloads:
        raise ValidationError(
            {"event": "El acontecimiento no guarda el detalle del escenario que lo originó."}
        )
    return payloads


@transaction.atomic
def materialize_plan_event(
    *, event: PlanEvent, actual_date: date, note: str = ""
) -> dict[str, Any]:
    """Convierte una previsión en realidad: crea el activo/pasivo y retira la previsión.

    El pasivo nace precargado con lo que se simuló (principal, interés, plazo) y a partir
    de ahí es él quien genera sus cuotas. Las lineas de financiación que había creado el
    plan se borran, porque el pasivo va a regenerarlas y quedarían duplicadas. El resto
    de lineas (desembolsos ya hechos, gasto recurrente, aportaciones) se devuelven al
    usuario: son suyas, reales, y a partir de ahora las edita en Presupuesto.
    """
    locked = (
        PlanEvent.objects.select_for_update().select_related("plan", "plan__user").get(pk=event.pk)
    )
    if locked.status != PlanEvent.Status.PLANNED:
        raise ValidationError({"status": "Solo se puede materializar una decisión prevista."})
    if actual_date > date.today():
        raise ValidationError({"actual_date": "La fecha real no puede ser futura."})

    payloads = _event_payloads(locked)
    created_assets: list[Asset] = []
    created_liabilities: list[Liability] = []

    for payload in payloads:
        asset = _create_asset(event=locked, payload=payload, actual_date=actual_date)
        if asset is not None:
            created_assets.append(asset)
        liability = _create_liability(
            event=locked,
            payload=payload,
            actual_date=actual_date,
            financed_asset=asset,
        )
        if liability is not None:
            created_liabilities.append(liability)

    budget_changes = _hand_budget_back(event=locked, drop_financing=bool(created_liabilities))

    locked.linked_assets.set(created_assets)
    locked.linked_liabilities.set(created_liabilities)
    locked.status = PlanEvent.Status.OCCURRED
    locked.actual_date = actual_date
    locked.actual_impact_json = {
        **locked.actual_impact_json,
        "materialization": {
            "actual_date": actual_date.isoformat(),
            "note": note.strip(),
            "created_assets": [{"id": item.id, "name": item.name} for item in created_assets],
            "created_liabilities": [
                {"id": item.id, "name": item.name} for item in created_liabilities
            ],
            **budget_changes,
        },
    }
    locked.save(update_fields=["status", "actual_date", "actual_impact_json", "updated_at"])

    projection = ProjectionService().recalculate(plan=locked.plan)
    return {
        "event": locked,
        "projection": projection,
        "created_assets": created_assets,
        "created_liabilities": created_liabilities,
        **budget_changes,
    }


def _create_asset(*, event: PlanEvent, payload: dict[str, Any], actual_date: date) -> Asset | None:
    value = Decimal(str(payload.get("new_asset_value") or "0"))
    if value <= 0:
        return None
    category, subcategory = ASSET_TEMPLATE_MAPPING.get(
        event.event_type, (Asset.Category.OTHER, Asset.Subcategory.OTHER)
    )
    asset = Asset.objects.create(
        user=event.plan.user,
        name=event.name,
        category=category,
        subcategory=subcategory,
        amount=value,
        currency="EUR",
        start_date=actual_date,
        notes="Creado al materializar una decisión de Mi Plan.",
    )
    # La funcion que se simuló manda: si el escenario contaba con un activo productivo,
    # la clasificacion debe verlo asi y no re-inferirlo por su categoria.
    function = payload.get("new_asset_type")
    if function in PlanAssetFunction.Function.values:
        PlanAssetFunction.objects.update_or_create(
            user=event.plan.user, asset=asset, defaults={"function": function}
        )
    return asset


def _create_liability(
    *,
    event: PlanEvent,
    payload: dict[str, Any],
    actual_date: date,
    financed_asset: Asset | None,
) -> Liability | None:
    principal = Decimal(str(payload.get("new_debt_principal") or "0"))
    if principal <= 0:
        return None
    rate = Decimal(str(payload.get("new_debt_interest_rate") or "0"))
    term_years = int(str(payload.get("new_debt_term_years") or "0"))
    liability = Liability.objects.create(
        user=event.plan.user,
        name=event.name,
        category=LIABILITY_TEMPLATE_MAPPING.get(
            event.event_type, cast(str, Liability.Category.PERSONAL_LOAN)
        ),
        amount=principal,
        principal_amount=principal,
        annual_interest_tae=(rate * Decimal("100")).quantize(Decimal("0.01")),
        term_months=term_years * 12 or None,
        start_date=actual_date,
        currency="EUR",
        financed_asset=financed_asset,
        is_asset_backed=financed_asset is not None,
        notes="Creado al materializar una decisión de Mi Plan.",
    )
    # A partir de aqui el pasivo genera sus propias cuotas reales (lineage liability_<id>).
    sync_generated_budget_commitments_for_liability(liability=liability)
    return liability


def _hand_budget_back(*, event: PlanEvent, drop_financing: bool) -> dict[str, list[dict[str, Any]]]:
    """Borra la previsión de financiación y devuelve el resto de lineas al usuario."""
    event_group = f"plan_event:{event.id}"
    category, subcategory, _role = default_debt_budget_mapping(event.event_type)
    dropped: list[dict[str, Any]] = []
    released: list[dict[str, Any]] = []

    for model in (AnnualExpenseEntry, AnnualIncomeEntry):
        for entry in model.objects.filter(user=event.plan.user, event_group=event_group):
            is_financing = (
                model is AnnualExpenseEntry
                and entry.category == category
                and entry.subcategory == subcategory
            )
            record = {
                "model": model.__name__,
                "id": entry.id,
                "name": entry.name,
                "fiscal_year": entry.fiscal_year,
                "amount_annual": str(entry.amount_annual),
            }
            if drop_financing and is_financing:
                entry.delete()
                dropped.append(record)
                continue
            entry.event_group = ""
            entry.save(update_fields=["event_group"])
            released.append(record)
    return {"budget_lines_dropped": dropped, "budget_lines_released": released}


@transaction.atomic
def cancel_plan_event(*, event: PlanEvent) -> dict[str, Any]:
    """Cambio de opinión sobre algo que aún no ha pasado: borra la previsión, no la realidad.

    Solo aplica a decisiones previstas. Sus lineas de presupuesto las creó el plan, así que
    se borran enteras y la proyección vuelve a donde estaba. Nada de esto toca el presente:
    una decisión ya materializada se deshace en Patrimonio, dando de baja su activo o pasivo.
    """
    # `source_scenario` es nullable: incluirlo en select_related haria un outer join y
    # Postgres no admite FOR UPDATE sobre el lado nullable de un outer join.
    locked = (
        PlanEvent.objects.select_for_update().select_related("plan", "plan__user").get(pk=event.pk)
    )
    if locked.status != PlanEvent.Status.PLANNED:
        raise ValidationError(
            {
                "status": (
                    "Solo se puede cancelar una decisión prevista. Lo que ya ocurrió se "
                    "deshace desde Patrimonio."
                )
            }
        )

    event_group = f"plan_event:{locked.id}"
    deleted: list[dict[str, Any]] = []
    for model in (AnnualExpenseEntry, AnnualIncomeEntry):
        for entry in model.objects.filter(user=locked.plan.user, event_group=event_group):
            deleted.append(
                {
                    "model": model.__name__,
                    "id": entry.id,
                    "name": entry.name,
                    "fiscal_year": entry.fiscal_year,
                    "amount_annual": str(entry.amount_annual),
                }
            )
            entry.delete()

    scenario = locked.source_scenario
    plan = locked.plan
    locked.delete()
    if scenario is not None:
        # El escenario vuelve a ser una hipotesis: se puede volver a comparar y aceptar.
        scenario.status = Scenario.Status.DRAFT
        scenario.accepted_at = None
        scenario.save(update_fields=["status", "accepted_at"])

    projection = ProjectionService().recalculate(plan=plan)
    return {"budget_lines_deleted": deleted, "projection": projection}
