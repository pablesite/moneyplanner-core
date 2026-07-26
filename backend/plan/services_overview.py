from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from .models import FinancialPlan, Recommendation
from .services_foundations import FoundationService
from .services_projection import (
    ProjectionService,
    build_projection_inputs,
    earliest_sustainable_retirement_year,
    get_assumption_set,
    serialize_assumptions,
)
from .services_recommendations import RecommendationService
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
        recommendations = RecommendationService().refresh(plan=plan)
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
            "foundations": {
                key: {
                    "status": foundations[key]["status"],
                    "score": foundations[key]["score"],
                }
                for key in (
                    "cash_flow",
                    "emergency_fund",
                    "debt",
                    "net_worth_health",
                    "data_quality",
                )
            },
            "next_action": guidance_action(next_recommendation),
            "input_hash": selected["input_hash"],
        }


class RecommendationPreviewService:
    def build(
        self,
        *,
        recommendation: Recommendation,
        scenario_name: str,
    ) -> dict[str, Any]:
        plan = recommendation.finding.plan
        assumption_set = get_assumption_set(name=scenario_name)
        current = ProjectionService().calculate(plan=plan, assumption_set=assumption_set)
        action = recommendation.action_json
        event = action.get("scenario_event")
        if not event:
            return {
                "recommendation_id": recommendation.id,
                "actionable": False,
                "action_type": action.get("action_type"),
                "destination": action.get("destination"),
                "before": projection_metrics(current),
                "after": None,
                "delta": None,
            }

        payload = {
            "start_date": event.get("start_date") or date.today().isoformat(),
            "start_year": date.fromisoformat(
                event.get("start_date") or date.today().isoformat()
            ).year,
            "end_date": event.get("end_date"),
            "end_year": (
                date.fromisoformat(event["end_date"]).year if event.get("end_date") else None
            ),
            "initial_outflow": event.get("initial_outflow", "0.00"),
            "monthly_expense_delta": event.get("monthly_expense_delta", "0.00"),
            "monthly_income_delta": event.get("monthly_income_delta", "0.00"),
            "monthly_contribution_delta": event.get("monthly_contribution_delta", "0.00"),
            "monthly_contribution_destination": event.get(
                "monthly_contribution_destination", "productive"
            ),
            "new_asset_value": event.get("new_asset_value", "0.00"),
            "new_asset_type": event.get("new_asset_type"),
            "new_debt_principal": event.get("new_debt_principal", "0.00"),
            "new_debt_interest_rate": event.get("new_debt_interest_rate", "0"),
            "new_debt_term_years": max(0, int(event.get("new_debt_term_months") or 0) // 12),
            "debt_end_year": None,
        }
        simulated = ProjectionService().calculate(
            plan=plan,
            assumption_set=assumption_set,
            extra_events=[payload],
        )
        before_year = metric_value(current, "projected_year")
        after_year = metric_value(simulated, "projected_year")
        years_gained = (
            int(before_year) - int(after_year)
            if before_year is not None and after_year is not None
            else None
        )
        monthly_commitment = Decimal(
            str(
                recommendation.impact_json.get("monthly_action")
                or event.get("monthly_contribution_delta")
                or "0"
            )
        )
        duration_months = None
        target_gap = Decimal(str(recommendation.impact_json.get("target_gap") or "0"))
        if monthly_commitment > 0 and target_gap > 0:
            duration_months = int(
                (target_gap / monthly_commitment).to_integral_value(rounding="ROUND_CEILING")
            )
        return {
            "recommendation_id": recommendation.id,
            "actionable": True,
            "action_type": action.get("action_type", "preview_scenario"),
            "destination": event.get("monthly_contribution_destination", "productive"),
            "monthly_commitment": str(monthly_commitment),
            "duration_months": duration_months,
            "before": projection_metrics(current),
            "after": projection_metrics(simulated),
            "years_gained": years_gained,
            "reaches_target": (after_year is not None and int(after_year) <= plan.target_date.year),
            "delta": comparison_delta(current=current, simulated=simulated),
            "confidence": (
                "low" if simulated["quality_level"] in {"initial", "needs_review"} else "medium"
            ),
        }


def projection_metrics(projection: dict[str, Any]) -> dict[str, Any]:
    return {
        "projected_year": metric_value(projection, "projected_year"),
        "monthly_sustainable_income": metric_value(projection, "monthly_sustainable_income"),
        "productive_capital": metric_value(projection, "productive_capital"),
        "net_worth": metric_value(projection, "net_worth"),
        "target_capital": metric_value(projection, "target_capital"),
        "progress_percent": metric_value(projection, "progress_percent"),
    }
