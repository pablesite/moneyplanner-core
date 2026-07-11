from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry

from .models import FinancialPlan


class ExpenseBucket(StrEnum):
    OPERATING = "operating"
    TEMPORARY_COMMITMENT = "temporary_commitment"
    CONTRIBUTION = "contribution"
    ASSET_PURCHASE = "asset_purchase"
    TAX_OTHER = "tax_other"
    UNCLASSIFIABLE = "unclassifiable"


@dataclass(frozen=True)
class ExpenseBuckets:
    operating: Decimal = Decimal("0")
    temporary_commitment: Decimal = Decimal("0")
    contribution: Decimal = Decimal("0")
    asset_purchase: Decimal = Decimal("0")
    tax_other: Decimal = Decimal("0")
    unclassifiable: Decimal = Decimal("0")


def plan_fiscal_year(plan: FinancialPlan | None = None) -> int:
    """Return the single active fiscal-year window used by the plan engine."""
    del plan
    return date.today().year


def annual_income_entries(plan: FinancialPlan):
    return AnnualIncomeEntry.objects.filter(
        user=plan.user,
        is_active=True,
        fiscal_year=plan_fiscal_year(plan),
    )


def annual_expense_entries(plan: FinancialPlan):
    return AnnualExpenseEntry.objects.filter(
        user=plan.user,
        is_active=True,
        fiscal_year=plan_fiscal_year(plan),
    )


def structural_income_entries(plan: FinancialPlan):
    return annual_income_entries(plan).exclude(time_profile=AnnualIncomeEntry.TimeProfile.ONE_OFF)


def structural_income(plan: FinancialPlan) -> Decimal:
    return sum(
        (Decimal(entry.amount_annual) for entry in structural_income_entries(plan)),
        Decimal("0"),
    )


def expense_bucket(entry: AnnualExpenseEntry) -> ExpenseBucket:
    role = entry.cashflow_role
    if role == AnnualExpenseEntry.CashflowRole.OPERATING:
        return ExpenseBucket.OPERATING
    if role == AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT:
        return ExpenseBucket.TEMPORARY_COMMITMENT
    if role in {
        AnnualExpenseEntry.CashflowRole.SAVINGS,
        AnnualExpenseEntry.CashflowRole.INVESTMENT,
    }:
        return ExpenseBucket.CONTRIBUTION
    if role == AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE:
        return ExpenseBucket.ASSET_PURCHASE
    if role in {
        AnnualExpenseEntry.CashflowRole.TAX_FEE,
        AnnualExpenseEntry.CashflowRole.TRANSFER,
        AnnualExpenseEntry.CashflowRole.OTHER,
    }:
        return ExpenseBucket.TAX_OTHER
    return ExpenseBucket.UNCLASSIFIABLE


def expense_buckets(entries: Iterable[AnnualExpenseEntry]) -> ExpenseBuckets:
    totals = {bucket: Decimal("0") for bucket in ExpenseBucket}
    for entry in entries:
        bucket = expense_bucket(entry)
        totals[bucket] += Decimal(entry.amount_annual)
    return ExpenseBuckets(**{bucket.value: totals[bucket] for bucket in ExpenseBucket})
