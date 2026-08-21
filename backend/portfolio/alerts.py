"""Alertas deterministas de cartera: hechos accionables, no notificaciones.

No se persisten ni se envian fuera de Cartera. Cada lectura recompone las señales a partir
del mismo estado que publica la pantalla, para que una alerta no sobreviva a la correccion
que la resolvio y para que su accion pueda llevar al sitio concreto que la arregla.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.conf import settings

from memberships.models import Ownership

from .allocation import build_allocation, build_scopes
from .exposure import build_exposure
from .models import ContributionBasket, Portfolio
from .performance import (
    PerformanceContext,
    build_portfolio_quality,
    default_performance_period,
    load_performance_context,
    timeline_context_start,
)


def _threshold(name: str, default: str) -> Decimal:
    """Umbrales configurables sin convertir la politica del usuario en settings.

    Las bandas de asignacion siguen viviendo en la estrategia. Estos limites solo deciden
    cuando una señal estructural merece ocupar el centro de atencion.
    """
    return Decimal(str(getattr(settings, name, default)))


CONCENTRATION_PERCENT = _threshold("PORTFOLIO_ALERT_CONCENTRATION_PERCENT", "35")

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
CATEGORY_ORDER = {"quality": 0, "structure": 1, "execution": 2}


def _alert(
    *,
    code: str,
    category: str,
    severity: str,
    title: str,
    detail: str,
    action: dict[str, Any],
) -> dict[str, Any]:
    return {
        "code": code,
        "category": category,
        "severity": severity,
        "title": title,
        "detail": detail,
        "action": action,
    }


def build_portfolio_alerts(
    *,
    portfolio: Portfolio,
    on_date: date,
    context: PerformanceContext | None = None,
) -> dict[str, Any]:
    """Devuelve incidencias que ya se pueden resolver desde la aplicacion.

    Una alerta no es una recomendacion financiera: habla de calidad, de una politica
    escrita que se esta incumpliendo o de una propuesta que el usuario ya creo y aun no
    termino. Por eso sus acciones son rutas internas tipadas, no texto ejecutable.
    """
    start_date, _ = default_performance_period(portfolio)
    context = context or load_performance_context(
        portfolio=portfolio,
        start_date=timeline_context_start(portfolio=portfolio, start_date=start_date),
        end_date=on_date,
    )
    quality = build_portfolio_quality(
        portfolio=portfolio,
        start_date=start_date,
        end_date=on_date,
        context=context,
    )
    alerts: list[dict[str, Any]] = []

    missing = quality["positions"]["missing"]
    if missing:
        alerts.append(
            _alert(
                code="valuation_missing",
                category="quality",
                severity="critical",
                title=f"{missing} {('posición necesita' if missing == 1 else 'posiciones necesitan')} valoración",
                detail="Sin una valoración no se puede cerrar con precisión el valor ni la rentabilidad.",
                action={"kind": "review_valuations"},
            )
        )
    stale = quality["positions"]["stale"]
    if stale:
        alerts.append(
            _alert(
                code="valuation_stale",
                category="quality",
                severity="warning",
                title=f"{stale} {('valoración está' if stale == 1 else 'valoraciones están')} desactualizada",
                detail="La cartera conserva el último dato conocido, pero no lo trata como un cierre actual.",
                action={"kind": "review_valuations"},
            )
        )
    ownership_missing = quality["ownership_missing"]
    if ownership_missing:
        alerts.append(
            _alert(
                code="ownership_missing",
                category="quality",
                severity="warning",
                title=f"{ownership_missing} {('posición no tiene' if ownership_missing == 1 else 'posiciones no tienen')} titularidad",
                detail="No se pueden asignar a un mandato ni evaluar correctamente sus partes familiares.",
                action={"kind": "configure_positions"},
            )
        )
    if quality["cash_ownership_missing"]:
        alerts.append(
            _alert(
                code="cash_ownership_missing",
                category="quality",
                severity="warning",
                title="Hay efectivo de contenedor sin titularidad",
                detail="Al filtrar por persona ese efectivo no se puede repartir con certeza.",
                action={"kind": "open_net_worth"},
            )
        )
    if quality["fx_issues"]:
        alerts.append(
            _alert(
                code="fx_coverage",
                category="quality",
                severity="warning",
                title="Faltan conversiones de divisa",
                detail="Algunas cifras en moneda base quedan parciales hasta completar esos cambios.",
                action={"kind": "review_valuations"},
            )
        )

    ownerships = {
        ownership.id: ownership
        for ownership in Ownership.objects.filter(user=portfolio.user).prefetch_related(
            "splits__member"
        )
    }
    for scope in build_scopes(portfolio=portfolio, on_date=on_date):
        ownership = ownerships[scope["ownership_id"]]
        allocation = build_allocation(
            portfolio=portfolio,
            ownership=ownership,
            on_date=on_date,
            context=context,
        )
        action = {"kind": "open_allocation", "ownership_id": scope["ownership_id"]}
        if allocation["strategy"] is None:
            alerts.append(
                _alert(
                    code=f"strategy_missing:{scope['ownership_id']}",
                    category="structure",
                    severity="info",
                    title=f"{scope['label']} no tiene una estrategia escrita",
                    detail="Sin objetivos y bandas no se puede dirigir una nueva aportación de este mandato.",
                    action=action,
                )
            )
            continue
        for row in allocation["by_class"]:
            if row["band"] not in {"above", "below"}:
                continue
            direction = "por encima" if row["band"] == "above" else "por debajo"
            alerts.append(
                _alert(
                    code=f"allocation_band:{scope['ownership_id']}:{row['asset_class']}",
                    category="structure",
                    severity="warning",
                    title=f"{scope['label']}: {row['asset_class']} está {direction} de su banda",
                    detail="La aportación inteligente muestra cuánto puede corregirse sin proponer ventas.",
                    action=action,
                )
            )

    exposure = build_exposure(portfolio=portfolio, on_date=on_date, context=context)
    top_positions = exposure["concentration"]["top_positions"]
    if top_positions and Decimal(top_positions[0]["percent"]) >= CONCENTRATION_PERCENT:
        top = top_positions[0]
        alerts.append(
            _alert(
                code=f"concentration:{top['position_id']}",
                category="structure",
                severity="warning",
                title=f"{top['name']} concentra {top['percent']} % de la cartera",
                detail="No implica que debas vender; sirve para comprobar si ese peso sigue siendo intencional.",
                action={"kind": "open_exposure", "position_id": top["position_id"]},
            )
        )
    for dimension in exposure["dimensions"]:
        if dimension["status"] == "ready":
            continue
        alerts.append(
            _alert(
                code=f"exposure_coverage:{dimension['dimension']}",
                category="structure",
                severity="info",
                title=f"Cobertura {dimension['label'].lower()} {dimension['covered_percent']} %",
                detail="La diversificación solo describe la parte de cartera cuya composición se ha declarado.",
                action={"kind": "open_exposure"},
            )
        )

    pending = ContributionBasket.objects.filter(
        portfolio=portfolio,
        status=ContributionBasket.Status.DRAFT,
    ).count()
    if pending:
        alerts.append(
            _alert(
                code="pending_baskets",
                category="execution",
                severity="info",
                title=f"{pending} {('cesta espera' if pending == 1 else 'cestas esperan')} confirmación",
                detail="Una cesta es solo una propuesta hasta que confirmas las operaciones que sí ejecutaste.",
                action={"kind": "open_baskets"},
            )
        )

    alerts.sort(
        key=lambda row: (
            CATEGORY_ORDER[row["category"]],
            SEVERITY_ORDER[row["severity"]],
            row["code"],
        )
    )
    return {
        "on_date": on_date.isoformat(),
        "summary": {
            severity: sum(1 for row in alerts if row["severity"] == severity)
            for severity in ("critical", "warning", "info")
        },
        "alerts": alerts,
    }
