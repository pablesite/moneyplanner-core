from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Finding, FinancialPlan, Recommendation, Scenario, ScenarioEvent
from .services_findings import FindingService
from .services_foundations import FoundationService
from .services_projection import (
    ProjectionService,
    build_projection_inputs,
    earliest_sustainable_retirement_year,
    get_assumption_set,
    serialize_assumptions,
)


PROFILE_PRIORITY_SHIFT: dict[str, dict[str, int]] = {
    "security": {
        "REBUILD_EMERGENCY_FUND": -20,
        "REDUCE_HIGH_COST_DEBT": -10,
    },
    "balanced": {},
    "growth": {
        "INCREASE_CONTRIBUTION": -15,
        "REBUILD_EMERGENCY_FUND": 10,
    },
}


def dec(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


class RecommendationService:
    def refresh(self, *, plan: FinancialPlan) -> list[Recommendation]:
        findings = FindingService().evaluate(plan=plan)
        foundations = FoundationService().calculate(plan=plan)
        recommendations: list[Recommendation] = []
        with transaction.atomic():
            for finding in findings:
                spec = self._recommendation_spec(
                    plan=plan,
                    finding=finding,
                    foundations=foundations,
                )
                if spec is None:
                    continue
                if (
                    spec["code"] == Recommendation.Code.INCREASE_CONTRIBUTION
                    and not scenario_event_changes_projection(
                        plan=plan,
                        event=spec["action"]["scenario_event"],
                    )
                ):
                    continue
                recommendation, _created = Recommendation.objects.update_or_create(
                    finding=finding,
                    code=spec["code"],
                    defaults={
                        "priority": spec["priority"],
                        "action_json": spec["action"],
                        "impact_json": spec["impact"],
                        "alternatives_json": spec["alternatives"],
                    },
                )
                if (
                    recommendation.status == Recommendation.Status.SNOOZED
                    and recommendation.snoozed_until
                    and recommendation.snoozed_until <= timezone.localdate()
                ):
                    recommendation.status = Recommendation.Status.OPEN
                    recommendation.snoozed_until = None
                    recommendation.save(update_fields=["status", "snoozed_until", "updated_at"])
                recommendations.append(recommendation)
        return recommendations

    def accept(self, *, recommendation: Recommendation) -> Recommendation:
        recommendation.status = Recommendation.Status.ACCEPTED
        recommendation.save(update_fields=["status", "updated_at"])
        return recommendation

    def dismiss(self, *, recommendation: Recommendation) -> Recommendation:
        recommendation.status = Recommendation.Status.DISMISSED
        recommendation.save(update_fields=["status", "updated_at"])
        return recommendation

    def simulate(
        self,
        *,
        recommendation: Recommendation,
        adjustments: dict[str, Any] | None = None,
    ) -> Scenario:
        plan = recommendation.finding.plan
        event_payload = adjusted_scenario_event(
            recommendation=recommendation,
            adjustments=adjustments,
        )
        if not event_payload:
            raise ValidationError(
                "This recommendation must be completed in its destination module."
            )
        validate_affordable_adjustment(
            recommendation=recommendation,
            event=event_payload,
        )
        scenario = Scenario.objects.create(
            plan=plan,
            source_recommendation=recommendation,
            name=recommendation.action_json.get("title", "Simulación recomendada"),
            template_type=recommendation.action_json.get(
                "scenario_template", Scenario.TemplateType.GENERIC
            ),
        )
        ScenarioEvent.objects.create(
            scenario=scenario,
            start_date=event_payload.get("start_date") or timezone.localdate(),
            end_date=event_payload.get("end_date"),
            initial_outflow=event_payload.get("initial_outflow", "0.00"),
            monthly_expense_delta=event_payload.get("monthly_expense_delta", "0.00"),
            monthly_income_delta=event_payload.get("monthly_income_delta", "0.00"),
            monthly_contribution_delta=event_payload.get("monthly_contribution_delta", "0.00"),
            monthly_contribution_destination=event_payload.get(
                "monthly_contribution_destination",
                ScenarioEvent.ContributionDestination.PRODUCTIVE,
            ),
            new_asset_value=event_payload.get("new_asset_value", "0.00"),
            new_asset_type=event_payload.get("new_asset_type"),
            new_debt_principal=event_payload.get("new_debt_principal", "0.00"),
            new_debt_interest_rate=event_payload.get("new_debt_interest_rate"),
            new_debt_term_months=event_payload.get("new_debt_term_months"),
            metadata_json={"source_recommendation": recommendation.id},
        )
        return scenario

    def _priority(self, *, plan: FinancialPlan, code: str, base: int) -> int:
        return max(1, base + PROFILE_PRIORITY_SHIFT.get(plan.profile, {}).get(code, 0))

    def _recommendation_spec(
        self,
        *,
        plan: FinancialPlan,
        finding: Finding,
        foundations: dict[str, Any],
    ) -> dict[str, Any] | None:
        evidence = finding.evidence_json
        today = timezone.localdate()
        if finding.code == Finding.Code.EMERGENCY_FUND_BELOW_TARGET:
            monthly_expense = Decimal("0")
            coverage = dec(evidence.get("coverage_months_base"))
            liquidity = dec(evidence.get("eligible_liquidity"))
            if coverage > 0:
                monthly_expense = liquidity / coverage
            target = monthly_expense * Decimal("6")
            gap = max(Decimal("0"), target - liquidity)
            monthly_action = max(Decimal("50"), (gap / Decimal("12")).quantize(Decimal("0.01")))
            return {
                "code": Recommendation.Code.REBUILD_EMERGENCY_FUND,
                "priority": self._priority(plan=plan, code="REBUILD_EMERGENCY_FUND", base=20),
                "action": {
                    "title": "Reforzar el fondo de emergencia",
                    "summary": "Reservar una aportación mensual temporal hasta acercarse a 6 meses de gasto.",
                    "reason": "La liquidez elegible no cubre todavía el objetivo de seguridad.",
                    "rule": "EMERGENCY_FUND_BELOW_TARGET",
                    "scenario_template": Scenario.TemplateType.GENERIC,
                    "scenario_event": {
                        "start_date": date(today.year, today.month, 1).isoformat(),
                        "monthly_contribution_delta": str(monthly_action),
                        "monthly_contribution_destination": (
                            ScenarioEvent.ContributionDestination.SECURITY
                        ),
                    },
                },
                "impact": {"target_gap": str(gap), "monthly_action": str(monthly_action)},
                "alternatives": ["Reducir gasto operativo", "Usar ingresos extraordinarios"],
            }
        if finding.code == Finding.Code.HIGH_COST_DEBT:
            debt = dec(evidence.get("high_cost_debt"))
            payoff = min(debt, Decimal("1000.00")) if debt > 0 else Decimal("0.00")
            return {
                "code": Recommendation.Code.REDUCE_HIGH_COST_DEBT,
                "priority": self._priority(plan=plan, code="REDUCE_HIGH_COST_DEBT", base=30),
                "action": {
                    "title": "Amortizar deuda cara",
                    "summary": "Simular una amortización parcial de la deuda con TAE alta.",
                    "reason": "Hay deuda con coste superior al umbral MVP del 8%.",
                    "rule": "HIGH_COST_DEBT",
                    "scenario_template": Scenario.TemplateType.DEBT_PAYOFF,
                    "scenario_event": {
                        "start_date": date(today.year, today.month, 1).isoformat(),
                        "initial_outflow": str(payoff),
                    },
                },
                "impact": {"candidate_payoff": str(payoff), "high_cost_debt": str(debt)},
                "alternatives": ["Renegociar tipo", "Priorizar la deuda con TAE más alta"],
            }
        if finding.code == Finding.Code.NEGATIVE_CASH_FLOW:
            # Esfuerzo temporal: no toca recortar compromisos finitos; el consejo
            # es sostener liquidez hasta que venzan y el superávit vuelva a positivo.
            if evidence.get("committed_status") == "transient":
                recovery = evidence.get("committed_recovery_year")
                until = f"hasta {recovery}" if recovery else "hasta que venzan los compromisos"
                return {
                    "code": Recommendation.Code.RESTORE_CASH_FLOW,
                    "priority": self._priority(plan=plan, code="RESTORE_CASH_FLOW", base=25),
                    "action": {
                        "title": "Sostener liquidez durante el esfuerzo",
                        "summary": (
                            f"Es un esfuerzo temporal: mantén colchón {until}, cuando venzan "
                            "los compromisos y el superávit comprometido vuelva a positivo."
                        ),
                        "reason": (
                            "Tu base recurrente es positiva; el déficit viene solo de "
                            "compromisos temporales que vencen."
                        ),
                        "rule": finding.code,
                        "action_type": "review_budget",
                        "destination": "budget",
                    },
                    "impact": {"committed_recovery_year": recovery},
                    "alternatives": [
                        "Mantener el fondo de emergencia",
                        "Revisar el calendario de compromisos",
                    ],
                }
            deficit = abs(dec(evidence.get("committed_surplus")))
            monthly_action = max(
                Decimal("50.00"), (deficit / Decimal("12")).quantize(Decimal("0.01"))
            )
            return {
                "code": Recommendation.Code.RESTORE_CASH_FLOW,
                "priority": self._priority(plan=plan, code="RESTORE_CASH_FLOW", base=10),
                "action": {
                    "title": "Recuperar margen mensual",
                    "summary": "Cerrar el déficit comprometido antes de aumentar la inversión.",
                    "reason": "Los compromisos actuales superan los ingresos estructurales.",
                    "rule": finding.code,
                    "action_type": "review_budget",
                    "destination": "budget",
                },
                "impact": {"monthly_action": str(monthly_action)},
                "alternatives": ["Reducir compromisos", "Aumentar ingresos recurrentes"],
            }
        if finding.code in {
            Finding.Code.RETIREMENT_TARGET_OFF_TRACK,
            Finding.Code.PRODUCTIVE_CAPITAL_STAGNANT,
        }:
            cash_flow = foundations["cash_flow"]
            committed_status = cash_flow["committed_status"]
            if committed_status == "structural":
                return None

            start_date = date(today.year, today.month, 1)
            available_annual = dec(cash_flow["committed_surplus"])
            deferred_until = None
            if committed_status == "transient":
                recovery_year = cash_flow.get("committed_recovery_year")
                if recovery_year is None:
                    return None
                start_date = date(int(recovery_year), 1, 1)
                deferred_until = start_date.isoformat()
                operating_surplus = dec(cash_flow["operating_surplus"])
                active_commitments = sum(
                    (
                        dec(item["amount"])
                        for item in cash_flow.get("temporary_commitments", [])
                        if item.get("end_year") is None
                        or int(item["end_year"]) >= int(recovery_year)
                    ),
                    Decimal("0"),
                )
                available_annual = operating_surplus - active_commitments

            available_monthly = max(
                Decimal("0"),
                (available_annual / Decimal("12")).quantize(Decimal("0.01")),
            )
            if available_monthly <= 0:
                return None
            monthly_action = min(Decimal("100.00"), available_monthly)
            if deferred_until:
                summary = (
                    f"Probar una aportación de hasta {monthly_action} € al mes desde "
                    f"{start_date.strftime('%m/%Y')}, cuando se recupere el margen."
                )
                funding_source = (
                    "Del margen estimado que quedará cuando finalicen los compromisos temporales; "
                    "no se descuenta del presupuesto actual."
                )
            else:
                summary = (
                    f"Probar una aportación de hasta {monthly_action} € al mes usando "
                    "el margen disponible."
                )
                funding_source = (
                    "Del margen mensual previsto después de ingresos, gasto operativo y "
                    "compromisos registrados."
                )
            return {
                "code": Recommendation.Code.INCREASE_CONTRIBUTION,
                "priority": self._priority(plan=plan, code="INCREASE_CONTRIBUTION", base=40),
                "action": {
                    "title": "Aumentar aportación planificada",
                    "summary": summary,
                    "reason": "La trayectoria estimada no llega al objetivo con suficiente holgura.",
                    "rule": finding.code,
                    "scenario_template": Scenario.TemplateType.GENERIC,
                    "scenario_event": {
                        "start_date": start_date.isoformat(),
                        "monthly_contribution_delta": str(monthly_action),
                        "monthly_contribution_destination": (
                            ScenarioEvent.ContributionDestination.PRODUCTIVE
                        ),
                    },
                },
                "impact": {
                    "monthly_action": str(monthly_action),
                    "available_monthly_margin": str(available_monthly),
                    "current_committed_surplus": cash_flow["committed_surplus"],
                    "deferred_until": deferred_until,
                    "funding_source": funding_source,
                },
                "alternatives": ["Retrasar fecha objetivo", "Reducir nivel de vida objetivo"],
            }
        if finding.code == Finding.Code.DATA_INCOMPLETE:
            return {
                "code": Recommendation.Code.COMPLETE_DATA,
                "priority": 90,
                "action": {
                    "title": "Completar datos clave",
                    "summary": "Revisar ingresos, gastos, activos y tipos de deuda para mejorar el diagnóstico.",
                    "reason": "La calidad de datos limita la precisión del plan.",
                    "rule": "DATA_INCOMPLETE",
                    "action_type": "complete_data",
                    "destination": "plan_setup",
                },
                "impact": {"data_quality_score": evidence.get("score")},
                "alternatives": ["Completar solo deudas", "Completar solo presupuesto operativo"],
            }
        return None


def adjusted_scenario_event(
    *,
    recommendation: Recommendation,
    adjustments: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    source = recommendation.action_json.get("scenario_event")
    if not source:
        return None
    event = dict(source)
    values = adjustments or {}
    if "monthly_contribution_delta" in values:
        if "monthly_contribution_delta" not in event:
            raise ValidationError("This recommendation does not support a monthly amount.")
        event["monthly_contribution_delta"] = str(values["monthly_contribution_delta"])
    if "start_date" in values:
        event["start_date"] = values["start_date"].isoformat()
    return event


def projection_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    start_date = event.get("start_date") or date.today().isoformat()
    end_date = event.get("end_date")
    return {
        "start_date": start_date,
        "start_year": date.fromisoformat(start_date).year,
        "end_date": end_date,
        "end_year": date.fromisoformat(end_date).year if end_date else None,
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


def scenario_event_changes_projection(*, plan: FinancialPlan, event: dict[str, Any]) -> bool:
    scenario_name = {
        FinancialPlan.Profile.SECURITY: "prudent",
        FinancialPlan.Profile.BALANCED: "expected",
        FinancialPlan.Profile.GROWTH: "favorable",
    }[plan.profile]
    assumption_set = get_assumption_set(name=scenario_name)
    assumptions = serialize_assumptions(assumption_set)
    current_prepared = build_projection_inputs(plan=plan)
    current = ProjectionService().calculate(
        plan=plan,
        assumption_set=assumption_set,
        prepared=current_prepared,
    )
    current_sustainable = earliest_sustainable_retirement_year(
        inputs=current_prepared[0], assumptions=assumptions
    )
    payload = projection_event_payload(event)
    simulated_prepared = build_projection_inputs(plan=plan, extra_events=[payload])
    simulated = ProjectionService().calculate(
        plan=plan,
        assumption_set=assumption_set,
        extra_events=[payload],
        prepared=simulated_prepared,
    )
    simulated_sustainable = earliest_sustainable_retirement_year(
        inputs=simulated_prepared[0], assumptions=assumptions
    )
    current_summary = current["summary"]
    simulated_summary = simulated["summary"]
    return current_sustainable != simulated_sustainable or any(
        current_summary[key]["value"] != simulated_summary[key]["value"]
        for key in ("projected_year", "productive_capital", "net_worth", "progress_percent")
    )


def validate_affordable_adjustment(
    *, recommendation: Recommendation, event: dict[str, Any]
) -> None:
    available_margin = recommendation.impact_json.get("available_monthly_margin")
    if available_margin is not None and dec(event.get("monthly_contribution_delta")) > dec(
        available_margin
    ):
        raise ValidationError(
            {
                "monthly_contribution_delta": (
                    "La aportación supera el margen mensual estimado para esa mejora."
                )
            }
        )
    minimum_start = recommendation.impact_json.get("deferred_until")
    if minimum_start and date.fromisoformat(event["start_date"]) < date.fromisoformat(
        minimum_start
    ):
        raise ValidationError(
            {"start_date": ("La aportación no puede empezar antes de que se recupere el margen.")}
        )
