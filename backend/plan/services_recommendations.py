from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import Finding, FinancialPlan, Recommendation, Scenario, ScenarioEvent
from .services_findings import FindingService


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
        recommendations: list[Recommendation] = []
        with transaction.atomic():
            for finding in findings:
                spec = self._recommendation_spec(plan=plan, finding=finding)
                if spec is None:
                    continue
                recommendation, _created = Recommendation.objects.update_or_create(
                    finding=finding,
                    code=spec["code"],
                    defaults={
                        "priority": spec["priority"],
                        "action_json": spec["action"],
                        "impact_json": spec["impact"],
                        "alternatives_json": spec["alternatives"],
                        "status": Recommendation.Status.OPEN,
                    },
                )
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

    def simulate(self, *, recommendation: Recommendation) -> Scenario:
        plan = recommendation.finding.plan
        scenario = Scenario.objects.create(
            plan=plan,
            name=recommendation.action_json.get("title", "Simulacion recomendada"),
            template_type=recommendation.action_json.get(
                "scenario_template", Scenario.TemplateType.GENERIC
            ),
        )
        event_payload = recommendation.action_json.get("scenario_event", {})
        ScenarioEvent.objects.create(
            scenario=scenario,
            start_date=event_payload.get("start_date") or timezone.localdate(),
            end_date=event_payload.get("end_date"),
            initial_outflow=event_payload.get("initial_outflow", "0.00"),
            monthly_expense_delta=event_payload.get("monthly_expense_delta", "0.00"),
            monthly_income_delta=event_payload.get("monthly_income_delta", "0.00"),
            monthly_contribution_delta=event_payload.get("monthly_contribution_delta", "0.00"),
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
        self, *, plan: FinancialPlan, finding: Finding
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
                    "summary": "Reservar una aportacion mensual temporal hasta acercarse a 6 meses de gasto.",
                    "reason": "La liquidez elegible no cubre todavia el objetivo de seguridad.",
                    "rule": "EMERGENCY_FUND_BELOW_TARGET",
                    "scenario_template": Scenario.TemplateType.GENERIC,
                    "scenario_event": {
                        "start_date": date(today.year, today.month, 1).isoformat(),
                        "monthly_contribution_delta": str(monthly_action),
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
                    "summary": "Simular una amortizacion parcial de la deuda con TAE alta.",
                    "reason": "Hay deuda con coste superior al umbral MVP del 8%.",
                    "rule": "HIGH_COST_DEBT",
                    "scenario_template": Scenario.TemplateType.DEBT_PAYOFF,
                    "scenario_event": {
                        "start_date": date(today.year, today.month, 1).isoformat(),
                        "initial_outflow": str(payoff),
                    },
                },
                "impact": {"candidate_payoff": str(payoff), "high_cost_debt": str(debt)},
                "alternatives": ["Renegociar tipo", "Priorizar la deuda con TAE mas alta"],
            }
        if finding.code in {
            Finding.Code.NEGATIVE_CASH_FLOW,
            Finding.Code.RETIREMENT_TARGET_OFF_TRACK,
            Finding.Code.PRODUCTIVE_CAPITAL_STAGNANT,
        }:
            monthly_action = Decimal("100.00")
            return {
                "code": Recommendation.Code.INCREASE_CONTRIBUTION,
                "priority": self._priority(plan=plan, code="INCREASE_CONTRIBUTION", base=40),
                "action": {
                    "title": "Aumentar aportacion planificada",
                    "summary": "Probar una aportacion mensual adicional antes de cambiar el objetivo.",
                    "reason": "La trayectoria estimada no llega al objetivo con suficiente holgura.",
                    "rule": finding.code,
                    "scenario_template": Scenario.TemplateType.GENERIC,
                    "scenario_event": {
                        "start_date": date(today.year, today.month, 1).isoformat(),
                        "monthly_contribution_delta": str(monthly_action),
                    },
                },
                "impact": {"monthly_action": str(monthly_action)},
                "alternatives": ["Retrasar fecha objetivo", "Reducir nivel de vida objetivo"],
            }
        if finding.code == Finding.Code.DATA_INCOMPLETE:
            return {
                "code": Recommendation.Code.COMPLETE_DATA,
                "priority": 90,
                "action": {
                    "title": "Completar datos clave",
                    "summary": "Revisar ingresos, gastos, activos y tipos de deuda para mejorar el diagnostico.",
                    "reason": "La calidad de datos limita la precision del plan.",
                    "rule": "DATA_INCOMPLETE",
                    "scenario_template": Scenario.TemplateType.GENERIC,
                    "scenario_event": {
                        "start_date": date(today.year, today.month, 1).isoformat(),
                    },
                },
                "impact": {"data_quality_score": evidence.get("score")},
                "alternatives": ["Completar solo deudas", "Completar solo presupuesto operativo"],
            }
        return None
