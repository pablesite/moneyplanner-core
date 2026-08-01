from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.utils import timezone

from budget.models import MonthlyClose

from .models import Finding, FinancialPlan, ProjectionSnapshot, Recommendation
from .services_findings import FindingService
from .services_projection import (
    ProjectionService,
    build_projection_inputs,
    earliest_sustainable_retirement_year,
    get_assumption_set,
    serialize_assumptions,
)
from .services_recommendations import RecommendationService

logger = logging.getLogger(__name__)


class MonthlyClosePlanService:
    def on_monthly_close_finalized(self, *, monthly_close: MonthlyClose) -> None:
        plan = FinancialPlan.objects.filter(user=monthly_close.user).first()
        if plan is None:
            return
        try:
            ProjectionService().recalculate(plan=plan, assumption_name="expected")
            FindingService().evaluate(
                plan=plan,
                period=f"{monthly_close.fiscal_year}-{monthly_close.month:02d}",
            )
            RecommendationService().refresh(plan=plan)
        except Exception:
            logger.exception(
                "Could not update financial plan after monthly close %s",
                monthly_close.pk,
            )

    def impact(self, *, monthly_close: MonthlyClose) -> dict[str, Any] | None:
        plan = FinancialPlan.objects.filter(user=monthly_close.user).first()
        if plan is None:
            return None

        assumption_set = get_assumption_set(name="expected")
        prepared = build_projection_inputs(plan=plan)
        current_projection = ProjectionService().calculate(
            plan=plan,
            assumption_set=assumption_set,
            prepared=prepared,
        )
        snapshots = list(
            ProjectionSnapshot.objects.filter(plan=plan, is_official=True).order_by(
                "-calculated_at", "-id"
            )[:2]
        )
        current_snapshot = snapshots[0] if snapshots else None
        previous_snapshot = snapshots[1] if len(snapshots) > 1 else None
        if current_snapshot is not None:
            current_projection = current_snapshot.result_json

        current_summary = current_projection["summary"]
        previous_summary = (
            previous_snapshot.result_json.get("summary") if previous_snapshot is not None else None
        )

        productive_delta = money_delta(previous_summary, current_summary, "productive_capital")
        net_worth_delta = money_delta(previous_summary, current_summary, "net_worth")
        # El cierre mide el cambio sobre la fecha que titula el plan. `recalculate` la
        # guarda en cada snapshot oficial porque aquí no se puede recalcular la de un
        # snapshot pasado: sus entradas ya no existen. Los snapshots anteriores a ese
        # campo no la traen y entonces no hay delta que enseñar.
        current_sustainable = current_projection.get("sustainable_year")
        if current_sustainable is None:
            current_sustainable = earliest_sustainable_retirement_year(
                inputs=prepared[0], assumptions=serialize_assumptions(assumption_set)
            )
        previous_sustainable = (
            previous_snapshot.result_json.get("sustainable_year")
            if previous_snapshot is not None
            else None
        )
        sustainable_delta = (
            current_sustainable - previous_sustainable
            if current_sustainable is not None and previous_sustainable is not None
            else None
        )

        period = f"{monthly_close.fiscal_year}-{monthly_close.month:02d}"
        findings = list(
            Finding.objects.filter(plan=plan, period=period, status=Finding.Status.OPEN).order_by(
                severity_order_expression(), "-updated_at"
            )[:2]
        )
        if not findings:
            findings = FindingService().evaluate(plan=plan, period=period)[:2]
        recommendations = RecommendationService().refresh(plan=plan)
        action = next(
            (item for item in recommendations if item.status == Recommendation.Status.OPEN),
            None,
        )

        return {
            "monthly_close": {
                "id": monthly_close.id,
                "fiscal_year": monthly_close.fiscal_year,
                "month": monthly_close.month,
                "status": monthly_close.status,
            },
            "calculated_at": timezone.now().isoformat(),
            "trajectory": {
                "status": trajectory_status(
                    sustainable_year=current_sustainable,
                    target_year=current_summary["target_year"]["value"],
                ),
                "sustainable_year": current_sustainable,
                "projected_year": current_summary["projected_year"]["value"],
                "target_year": current_summary["target_year"]["value"],
                "sustainable_year_delta": sustainable_delta
                if sustainable_delta is not None and abs(sustainable_delta) >= 1
                else None,
            },
            "capital": {
                "productive_capital": current_summary["productive_capital"]["value"],
                "productive_capital_delta": productive_delta,
                "net_worth": current_summary["net_worth"]["value"],
                "net_worth_delta": net_worth_delta,
            },
            "data_quality": current_projection.get("quality_level"),
            "findings": [finding_payload(item) for item in findings[:2]],
            "recommended_action": recommendation_payload(action) if action else None,
        }


def severity_order_expression():
    from django.db.models import Case, IntegerField, Value, When

    return Case(
        When(severity=Finding.Severity.CRITICAL, then=Value(0)),
        When(severity=Finding.Severity.WARNING, then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )


def money_delta(previous_summary: dict[str, Any] | None, current_summary: dict[str, Any], key: str):
    if previous_summary is None:
        return None
    current = Decimal(str(current_summary[key]["value"]))
    previous = Decimal(str(previous_summary[key]["value"]))
    return str((current - previous).quantize(Decimal("0.01")))


def trajectory_status(*, sustainable_year: int | None, target_year: Any) -> str:
    """Mismo criterio que el titular del plan: se compara la jubilación sostenible más
    temprana con el año objetivo."""
    if sustainable_year is None:
        return "off_track"
    if int(sustainable_year) <= int(target_year):
        return "on_track"
    return "delayed"


def finding_payload(finding: Finding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "code": finding.code,
        "severity": finding.severity,
        "period": finding.period,
        "evidence_json": finding.evidence_json,
        "status": finding.status,
    }


def recommendation_payload(recommendation: Recommendation) -> dict[str, Any]:
    return {
        "id": recommendation.id,
        "finding": recommendation.finding_id,
        "code": recommendation.code,
        "priority": recommendation.priority,
        "action_json": recommendation.action_json,
        "impact_json": recommendation.impact_json,
        "alternatives_json": recommendation.alternatives_json,
        "status": recommendation.status,
    }
