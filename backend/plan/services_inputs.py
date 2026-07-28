from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, Iterable

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry

from .models import FinancialPlan

# Prefijo de `event_group` con el que una Decisión (PlanEvent) marca las partidas de
# presupuesto que gobierna. Los flujos puntuales con este grupo se cuentan por la vía
# de eventos, no por la de caja, para no duplicarlos.
PLAN_EVENT_GROUP_PREFIX = "plan_event:"


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


def one_off_flows(plan: FinancialPlan) -> list[dict[str, Any]]:
    """Flujos puntuales (`one_off`) del presupuesto agregados por año fiscal para
    aplicarlos en la proyección en su año, en todo el horizonte.

    Se excluyen: los años pasados (ya reflejados en el capital actual), las partidas
    gobernadas por una Decisión (`event_group` empieza por `plan_event:`), los gastos
    generados por Patrimonio (`is_system_generated`) y los ingresos por venta de
    activo (`asset_sale`), que se modelan como Decisiones. Los importes van como
    cadenas para que `serialize_inputs`/`stable_hash` sean deterministas.
    """
    today = date.today()
    current_year = today.year
    current_month = today.month
    per_year: dict[int, dict[str, Decimal]] = {}

    def applies(fiscal_year: int, target_month: int | None) -> bool:
        # Años pasados: ya reflejados en el capital actual. Año en curso: solo lo que
        # aún no ha ocurrido (mes objetivo futuro o sin mes), para no contar dos veces
        # lo ya gastado/ingresado. Años futuros: todo.
        if fiscal_year < current_year:
            return False
        if fiscal_year > current_year:
            return True
        return target_month is None or target_month >= current_month

    def bucket(year: int) -> dict[str, Decimal]:
        return per_year.setdefault(
            year,
            {
                "income": Decimal("0"),
                "contribution": Decimal("0"),
                "asset_purchase": Decimal("0"),
                "outflow": Decimal("0"),
            },
        )

    incomes = (
        AnnualIncomeEntry.objects.filter(
            user=plan.user,
            is_active=True,
            time_profile=AnnualIncomeEntry.TimeProfile.ONE_OFF,
            fiscal_year__gte=current_year,
        )
        .exclude(event_group__startswith=PLAN_EVENT_GROUP_PREFIX)
        .exclude(cashflow_role=AnnualIncomeEntry.CashflowRole.ASSET_SALE)
    )
    for entry in incomes:
        if applies(entry.fiscal_year, entry.target_month):
            bucket(entry.fiscal_year)["income"] += Decimal(entry.amount_annual)

    expenses = AnnualExpenseEntry.objects.filter(
        user=plan.user,
        is_active=True,
        time_profile=AnnualExpenseEntry.TimeProfile.ONE_OFF,
        is_system_generated=False,
        fiscal_year__gte=current_year,
    ).exclude(event_group__startswith=PLAN_EVENT_GROUP_PREFIX)
    contribution_roles = {
        AnnualExpenseEntry.CashflowRole.SAVINGS,
        AnnualExpenseEntry.CashflowRole.INVESTMENT,
    }
    for entry in expenses:
        if not applies(entry.fiscal_year, entry.target_month):
            continue
        slot = bucket(entry.fiscal_year)
        amount = Decimal(entry.amount_annual)
        if entry.cashflow_role in contribution_roles:
            slot["contribution"] += amount
        elif entry.cashflow_role == AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE:
            slot["asset_purchase"] += amount
        else:
            slot["outflow"] += amount

    return [
        {"year": year, **{key: str(value) for key, value in slot.items()}}
        for year, slot in sorted(per_year.items())
    ]
