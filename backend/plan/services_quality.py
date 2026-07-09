from __future__ import annotations

from dataclasses import dataclass

from accounting.models import LedgerTransaction
from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from memberships.models import FamilyMember
from net_worth.models import Asset, InvestmentContributionInterval, Liability


@dataclass(frozen=True)
class DataQualityResult:
    level: str
    factors: dict[str, bool]


class DataQualityService:
    def evaluate(self, *, user) -> DataQualityResult:
        factors = {
            "assets": Asset.objects.filter(user=user, is_active=True).exists(),
            "liabilities_reviewed": Liability.objects.filter(user=user, is_active=True).exists(),
            "budget": (
                AnnualIncomeEntry.objects.filter(user=user, is_active=True).exists()
                and AnnualExpenseEntry.objects.filter(user=user, is_active=True).exists()
            ),
            "accounting_history": LedgerTransaction.objects.filter(user=user).exists(),
            "pensions": FamilyMember.objects.filter(
                user=user,
                is_active=True,
                role=FamilyMember.Role.ADULT,
                pension_start_date__isnull=False,
            ).exists(),
            "contributions": (
                InvestmentContributionInterval.objects.filter(asset__user=user).exists()
                or AnnualExpenseEntry.objects.filter(
                    user=user,
                    is_active=True,
                    cashflow_role__in=[
                        AnnualExpenseEntry.CashflowRole.SAVINGS,
                        AnnualExpenseEntry.CashflowRole.INVESTMENT,
                    ],
                ).exists()
            ),
            "fresh_data": Asset.objects.filter(user=user, is_active=True).exists(),
        }
        score = sum(1 for value in factors.values() if value)
        if not factors["assets"]:
            level = "needs_review"
        elif score <= 2:
            level = "initial"
        elif score <= 5:
            level = "medium"
        else:
            level = "high"
        return DataQualityResult(level=level, factors=factors)
