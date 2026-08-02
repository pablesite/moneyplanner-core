from __future__ import annotations

from decimal import Decimal
from typing import Any

from .models import FinancialPlan, Recommendation
from .services_findings import FindingService
from .services_foundations import FoundationService
from .services_projection import (
    ProjectionService,
    build_projection_inputs,
    earliest_sustainable_retirement_year,
    get_assumption_set,
    serialize_assumptions,
)
from .services_recommendations import RecommendationService
from .services_recommendations import adjusted_scenario_event, projection_event_payload
from .services_scenarios import comparison_delta


SCENARIOS = ("prudent", "expected", "favorable")


def metric_value(projection: dict[str, Any], key: str) -> Any:
    return projection["summary"][key]["value"]


def guidance_action(recommendation: Recommendation | None) -> dict[str, Any] | None:
    if recommendation is None:
        return None
    action = recommendation.action_json
    impact = recommendation.impact_json
    event = action.get("scenario_event") or {}
    return {
        "recommendation_id": recommendation.id,
        "code": recommendation.code,
        "title": action.get("title"),
        "summary": action.get("summary"),
        "reason": action.get("reason"),
        "action_type": action.get("action_type", "preview_scenario"),
        "destination": action.get("destination")
        or event.get("monthly_contribution_destination")
        or "productive",
        "monthly_commitment": impact.get("monthly_action")
        or event.get("monthly_contribution_delta"),
        "confidence": "estimated",
    }


class PlanOverviewService:
    def build(self, *, plan: FinancialPlan, scenario_name: str) -> dict[str, Any]:
        scenario = scenario_name if scenario_name in SCENARIOS else "expected"

        # La jubilación sostenible más temprana por escenario: primer año en que
        # se puede dejar de trabajar sin que el capital productivo baje del
        # patrimonio a preservar. Reusa unos mismos inputs (una consulta a BD).
        inputs, _, _ = build_projection_inputs(plan=plan)
        sustainable_by_scenario = {
            name: earliest_sustainable_retirement_year(
                inputs=inputs,
                assumptions=serialize_assumptions(get_assumption_set(name=name)),
            )
            for name in SCENARIOS
        }
        sustainable_year = sustainable_by_scenario[scenario]
        desired_year = plan.target_date.year
        sustainable_range = {
            "prudent_year": sustainable_by_scenario["prudent"],
            "central_year": sustainable_by_scenario["expected"],
            "favorable_year": sustainable_by_scenario["favorable"],
        }

        # La proyección mostrada usa el retiro sostenible: la trayectoria refleja
        # un plan que no se desploma, coherente con el titular.
        selected = ProjectionService().calculate(
            plan=plan,
            assumption_set=get_assumption_set(name=scenario),
            retirement_year=sustainable_year,
        )
        foundations = FoundationService().calculate(plan=plan)
        # El resumen ya necesita los cimientos detallados. Se comparten con los
        # hallazgos y recomendaciones para no repetir varias veces el diagnóstico
        # completo durante la carga inicial de Mi Plan.
        findings = FindingService().evaluate(plan=plan, foundations=foundations)
        recommendations = RecommendationService().refresh(
            plan=plan,
            findings=findings,
            foundations=foundations,
        )
        next_recommendation = min(
            (item for item in recommendations if item.status == Recommendation.Status.OPEN),
            key=lambda item: item.priority,
            default=None,
        )

        if selected["quality_level"] in {"initial", "needs_review"}:
            status = "incomplete"
        elif sustainable_year is None:
            status = "unreachable"
        elif sustainable_year <= desired_year:
            status = "on_track"
        else:
            status = "off_track"

        return {
            "status": status,
            "scenario": selected["scenario"],
            "target_date": plan.target_date.isoformat(),
            "desired_year": desired_year,
            "sustainable_year": sustainable_year,
            "sustainable_range": sustainable_range,
            "gap_years": (
                sustainable_year - desired_year if sustainable_year is not None else None
            ),
            "projection": selected,
            # Compat: `range` pasa a llevar los años de jubilación sostenible.
            "range": sustainable_range,
            "quality": {
                "level": selected["quality_level"],
                "factors": selected["quality_factors"],
                "confidence": (
                    "low" if selected["quality_level"] in {"initial", "needs_review"} else "medium"
                ),
            },
            # El Resumen pinta los cimientos completos. Entregarlos aquí evita una
            # segunda petición y un segundo cálculo idéntico al cargar la pantalla.
            "foundations": foundations,
            "next_action": guidance_action(next_recommendation),
            "input_hash": selected["input_hash"],
        }


class RecommendationPreviewService:
    def build(
        self,
        *,
        recommendation: Recommendation,
        scenario_name: str,
        adjustments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan = recommendation.finding.plan
        assumption_set = get_assumption_set(name=scenario_name)
        assumptions = serialize_assumptions(assumption_set)
        # Entradas compartidas entre la trayectoria y la búsqueda del retiro sostenible.
        current_prepared = build_projection_inputs(plan=plan)
        current = ProjectionService().calculate(
            plan=plan, assumption_set=assumption_set, prepared=current_prepared
        )
        current_sustainable = earliest_sustainable_retirement_year(
            inputs=current_prepared[0], assumptions=assumptions
        )
        action = recommendation.action_json
        event = adjusted_scenario_event(
            recommendation=recommendation,
            adjustments=adjustments,
        )
        if not event:
            return {
                "recommendation_id": recommendation.id,
                "actionable": False,
                "action_type": action.get("action_type"),
                "destination": action.get("destination"),
                "before": projection_metrics(current, sustainable_year=current_sustainable),
                "after": None,
                "delta": None,
            }

        payload = projection_event_payload(event)
        simulated_prepared = build_projection_inputs(plan=plan, extra_events=[payload])
        simulated = ProjectionService().calculate(
            plan=plan,
            assumption_set=assumption_set,
            extra_events=[payload],
            prepared=simulated_prepared,
        )
        # Los años que gana la mejora se miden sobre la fecha que titula el plan —el
        # primer año en que dejar de trabajar es sostenible—, no sobre
        # `summary.projected_year`, que responde a desde cuándo cubre la pensión y no
        # se mueve al simular capital.
        simulated_sustainable = earliest_sustainable_retirement_year(
            inputs=simulated_prepared[0], assumptions=assumptions
        )
        sustainable_year = {"current": current_sustainable, "simulated": simulated_sustainable}
        years_gained = (
            current_sustainable - simulated_sustainable
            if current_sustainable is not None and simulated_sustainable is not None
            else None
        )
        monthly_commitment = Decimal(
            str(
                event.get("monthly_contribution_delta")
                or recommendation.impact_json.get("monthly_action")
                or "0"
            )
        )
        duration_months = None
        target_gap = Decimal(str(recommendation.impact_json.get("target_gap") or "0"))
        if monthly_commitment > 0 and target_gap > 0:
            duration_months = int(
                (target_gap / monthly_commitment).to_integral_value(rounding="ROUND_CEILING")
            )
        available_monthly_margin = recommendation.impact_json.get("available_monthly_margin")
        minimum_start_date = recommendation.impact_json.get("deferred_until")
        is_affordable = (
            available_monthly_margin is None
            or monthly_commitment <= Decimal(str(available_monthly_margin))
        ) and (minimum_start_date is None or payload["start_date"] >= minimum_start_date)
        return {
            "recommendation_id": recommendation.id,
            "actionable": True,
            "action_type": action.get("action_type", "preview_scenario"),
            "destination": event.get("monthly_contribution_destination", "productive"),
            "monthly_commitment": str(monthly_commitment),
            "start_date": payload["start_date"],
            "available_monthly_margin": available_monthly_margin,
            "minimum_start_date": minimum_start_date,
            "is_affordable": is_affordable,
            "funding_source": recommendation.impact_json.get("funding_source"),
            "duration_months": duration_months,
            "before": projection_metrics(current, sustainable_year=current_sustainable),
            "after": projection_metrics(simulated, sustainable_year=simulated_sustainable),
            "years_gained": years_gained,
            "reaches_target": (
                simulated_sustainable is not None and simulated_sustainable <= plan.target_date.year
            ),
            "delta": comparison_delta(
                current=current, simulated=simulated, sustainable_year=sustainable_year
            ),
            "confidence": (
                "low" if simulated["quality_level"] in {"initial", "needs_review"} else "medium"
            ),
        }


def projection_metrics(
    projection: dict[str, Any], *, sustainable_year: int | None = None
) -> dict[str, Any]:
    return {
        "sustainable_year": sustainable_year,
        "projected_year": metric_value(projection, "projected_year"),
        "monthly_sustainable_income": metric_value(projection, "monthly_sustainable_income"),
        "productive_capital": metric_value(projection, "productive_capital"),
        "net_worth": metric_value(projection, "net_worth"),
        "target_capital": metric_value(projection, "target_capital"),
        "progress_percent": metric_value(projection, "progress_percent"),
    }
