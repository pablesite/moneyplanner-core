from __future__ import annotations

from dataclasses import dataclass

from accounting.models import LedgerTransaction
from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from memberships.models import FamilyMember
from net_worth.models import Asset, InvestmentContributionInterval, Liability

from .models import FinancialPlan
from .services_inputs import annual_expense_entries, expense_buckets, plan_fiscal_year


@dataclass(frozen=True)
class DataQualityResult:
    level: str
    factors: dict[str, bool]


class DataQualityService:
    def evaluate(self, *, user) -> DataQualityResult:
        plan = FinancialPlan.objects.filter(user=user).first()
        active_year = plan_fiscal_year(plan)
        buckets = expense_buckets(annual_expense_entries(plan)) if plan else None
        factors = {
            "assets": Asset.objects.filter(user=user, is_active=True).exists(),
            "liabilities_reviewed": Liability.objects.filter(user=user, is_active=True).exists(),
            "budget": (
                AnnualIncomeEntry.objects.filter(
                    user=user, is_active=True, fiscal_year=active_year
                ).exists()
                and AnnualExpenseEntry.objects.filter(
                    user=user, is_active=True, fiscal_year=active_year
                ).exists()
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
            "employment_income_end_dates": not FamilyMember.objects.filter(
                user=user,
                is_active=True,
                role=FamilyMember.Role.ADULT,
                employment_income_end_date__isnull=True,
            ).exists(),
            "expenses_classified": buckets is None or buckets.unclassifiable == 0,
            "one_off_income_excluded": not AnnualIncomeEntry.objects.filter(
                user=user,
                is_active=True,
                fiscal_year=active_year,
                time_profile=AnnualIncomeEntry.TimeProfile.ONE_OFF,
                amount_annual__gt=0,
            ).exists(),
        }
        score = sum(1 for value in factors.values() if value)
        completeness = score / len(factors)
        if not factors["assets"]:
            level = "needs_review"
        elif completeness <= 2 / 7:
            level = "initial"
        elif completeness <= 5 / 7:
            level = "medium"
        else:
            level = "high"
        return DataQualityResult(level=level, factors=factors)
