from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction

from .models import Finding, FinancialPlan
from .services_foundations import FoundationService
from .services_projection import ProjectionService, get_assumption_set


def dec(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


class FindingService:
    def evaluate(self, *, plan: FinancialPlan, period: str = "current") -> list[Finding]:
        foundations = FoundationService().calculate(plan=plan)
        projection = ProjectionService().calculate(
            plan=plan,
            assumption_set=get_assumption_set(name="expected"),
        )
        specs = self._finding_specs(plan=plan, foundations=foundations, projection=projection)
        active_codes = {spec["code"] for spec in specs}

        with transaction.atomic():
            findings = []
            for spec in specs:
                finding, _created = Finding.objects.update_or_create(
                    plan=plan,
                    code=spec["code"],
                    period=period,
                    defaults={
                        "severity": spec["severity"],
                        "evidence_json": spec["evidence"],
                        "status": Finding.Status.OPEN,
                    },
                )
                findings.append(finding)
            Finding.objects.filter(plan=plan, period=period, status=Finding.Status.OPEN).exclude(
                code__in=active_codes
            ).update(status=Finding.Status.RESOLVED)
        return findings

    def _finding_specs(
        self, *, plan: FinancialPlan, foundations: dict[str, Any], projection: dict[str, Any]
    ) -> list[dict[str, Any]]:
        specs = []
        emergency_months = dec(foundations["emergency_fund"]["coverage_months_base"])
        if emergency_months < Decimal("3"):
            specs.append(
                {
                    "code": Finding.Code.EMERGENCY_FUND_BELOW_TARGET,
                    "severity": Finding.Severity.CRITICAL,
                    "evidence": foundations["emergency_fund"],
                }
            )
        elif emergency_months < Decimal("6"):
            specs.append(
                {
                    "code": Finding.Code.EMERGENCY_FUND_BELOW_TARGET,
                    "severity": Finding.Severity.WARNING,
                    "evidence": foundations["emergency_fund"],
                }
            )

        if dec(foundations["cash_flow"]["committed_surplus"]) < 0:
            specs.append(
                {
                    "code": Finding.Code.NEGATIVE_CASH_FLOW,
                    "severity": Finding.Severity.CRITICAL,
                    "evidence": foundations["cash_flow"],
                }
            )

        if dec(foundations["debt"]["high_cost_debt"]) > 0:
            specs.append(
                {
                    "code": Finding.Code.HIGH_COST_DEBT,
                    "severity": Finding.Severity.WARNING,
                    "evidence": foundations["debt"],
                }
            )

        projected_year = projection["summary"]["projected_year"]["value"]
        target_year = projection["summary"]["target_year"]["value"]
        if projected_year is None or int(projected_year) > int(target_year):
            specs.append(
                {
                    "code": Finding.Code.RETIREMENT_TARGET_OFF_TRACK,
                    "severity": Finding.Severity.WARNING,
                    "evidence": {
                        "projected_year": projected_year,
                        "target_year": target_year,
                        "progress_percent": projection["summary"]["progress_percent"]["value"],
                    },
                }
            )

        productive_capital = dec(projection["summary"]["productive_capital"]["value"])
        planned_contribution = dec(foundations["planned_contribution"]["annual_amount"])
        if productive_capital > 0 and planned_contribution <= 0:
            specs.append(
                {
                    "code": Finding.Code.PRODUCTIVE_CAPITAL_STAGNANT,
                    "severity": Finding.Severity.INFO,
                    "evidence": {
                        "productive_capital": str(productive_capital),
                        "planned_contribution": str(planned_contribution),
                    },
                }
            )

        if int(foundations["data_quality"]["score"]) < 75:
            specs.append(
                {
                    "code": Finding.Code.DATA_INCOMPLETE,
                    "severity": Finding.Severity.INFO,
                    "evidence": foundations["data_quality"],
                }
            )

        return specs
