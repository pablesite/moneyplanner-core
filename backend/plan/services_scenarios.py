from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, cast

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from budget.services import validate_annual_expense_taxonomy, validate_annual_income_taxonomy

from .models import PlanEvent, ProjectionSnapshot, Recommendation, Scenario
from .services_projection import ProjectionService, get_assumption_set

MONEY = Decimal("0.01")


@dataclass(frozen=True)
class BudgetLine:
    kind: str
    name: str
    category: str
    subcategory: str
    amount: Decimal
    fiscal_year: int
    target_month: int | None
    term_start_month: int | None
    term_end_year: int | None
    term_end_month: int | None
    cashflow_role: str
    time_profile: str = "one_off"


class ScenarioService:
    def compare(
        self,
        *,
        scenario: Scenario,
        assumption_name: str = "expected",
    ) -> dict[str, Any]:
        assumption_set = get_assumption_set(name=assumption_name)
        service = ProjectionService()
        current = service.calculate(plan=scenario.plan, assumption_set=assumption_set)
        event_payloads = scenario_event_payloads(scenario=scenario)
        simulated = service.calculate(
            plan=scenario.plan,
            assumption_set=assumption_set,
            extra_events=event_payloads,
        )
        snapshot = ProjectionSnapshot.objects.create(
            plan=scenario.plan,
            scenario=scenario,
            assumption_set=assumption_set,
            assumption_values=simulated["assumptions"],
            input_hash=simulated["input_hash"],
            result_json=simulated,
            quality_level=simulated["quality_level"],
            is_official=False,
        )
        return {
            "scenario": ScenarioSummary.from_model(scenario).as_dict(),
            "assumption_set": assumption_set.name,
            "current": current,
            "simulated": simulated,
            "delta": comparison_delta(current=current, simulated=simulated),
            "snapshot_id": snapshot.id,
        }

    @transaction.atomic
    def accept(self, *, scenario: Scenario, assumption_name: str = "expected") -> dict[str, Any]:
        locked = (
            Scenario.objects.select_for_update()
            .select_related("plan")
            .prefetch_related("events")
            .get(pk=scenario.pk)
        )
        if locked.status == Scenario.Status.ACCEPTED:
            raise ValidationError("Scenario is already accepted.")
        if locked.status == Scenario.Status.DISCARDED:
            raise ValidationError("Discarded scenarios cannot be accepted.")

        event_payloads = scenario_event_payloads(scenario=locked)
        comparison = self.compare(scenario=locked, assumption_name=assumption_name)
        plan_event = PlanEvent.objects.create(
            plan=locked.plan,
            source_scenario=locked,
            name=locked.name,
            event_type=locked.template_type,
            planned_date=min(
                (event.start_date for event in locked.events.all()), default=date.today()
            ),
            status=PlanEvent.Status.PLANNED,
            planned_impact_json={
                "events": event_payloads,
                "comparison_delta": comparison["delta"],
                "budget_lines": [
                    line.__dict__ | {"amount": str(line.amount)}
                    for line in budget_lines_for_scenario(locked)
                ],
            },
        )
        created_budget_entries = create_budget_entries_for_scenario(
            scenario=locked, plan_event=plan_event
        )
        locked.status = Scenario.Status.ACCEPTED
        locked.accepted_at = timezone.now()
        locked.save(update_fields=["status", "accepted_at"])
        if locked.source_recommendation_id:
            Recommendation.objects.filter(id=locked.source_recommendation_id).update(
                status=Recommendation.Status.ACCEPTED,
                snoozed_until=None,
            )
        official = ProjectionService().recalculate(
            plan=locked.plan, assumption_name=assumption_name
        )
        return {
            "event": plan_event,
            "projection": official,
            "budget_entries_created": created_budget_entries,
        }

    @transaction.atomic
    def discard(self, *, scenario: Scenario) -> Scenario:
        locked = Scenario.objects.select_for_update().get(pk=scenario.pk)
        if locked.status == Scenario.Status.ACCEPTED:
            raise ValidationError("Accepted scenarios cannot be discarded.")
        locked.status = Scenario.Status.DISCARDED
        locked.save(update_fields=["status"])
        return locked


@dataclass(frozen=True)
class ScenarioSummary:
    id: int
    name: str
    template_type: str
    status: str

    @classmethod
    def from_model(cls, scenario: Scenario) -> ScenarioSummary:
        return cls(
            id=scenario.id,
            name=scenario.name,
            template_type=scenario.template_type,
            status=scenario.status,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "template_type": self.template_type,
            "status": self.status,
        }


def scenario_event_payloads(*, scenario: Scenario) -> list[dict[str, Any]]:
    return [
        scenario_event_payload(event) | {"event_type": scenario.template_type}
        for event in scenario.events.all().order_by("start_date", "id")
    ]


def scenario_event_payload(event) -> dict[str, Any]:
    term_years = term_years_from_months(event.new_debt_term_months)
    debt_end_year = None
    if event.new_debt_term_months:
        debt_end_year = event.start_date.year + max(0, (event.new_debt_term_months - 1) // 12)
    end_year = event.end_date.year if event.end_date else None
    return {
        "id": event.id,
        "start_date": event.start_date.isoformat(),
        "start_year": event.start_date.year,
        "end_date": event.end_date.isoformat() if event.end_date else None,
        "end_year": end_year,
        "initial_outflow": str(event.initial_outflow),
        "monthly_expense_delta": str(event.monthly_expense_delta),
        "monthly_income_delta": str(event.monthly_income_delta),
        "monthly_contribution_delta": str(event.monthly_contribution_delta),
        "monthly_contribution_destination": event.monthly_contribution_destination,
        "new_asset_value": str(event.new_asset_value),
        "new_asset_type": event.new_asset_type,
        "new_debt_principal": str(event.new_debt_principal),
        "new_debt_interest_rate": str(event.new_debt_interest_rate or "0"),
        "new_debt_term_years": term_years,
        "debt_end_year": debt_end_year,
        "metadata_json": event.metadata_json,
    }


def comparison_delta(*, current: dict[str, Any], simulated: dict[str, Any]) -> dict[str, Any]:
    current_summary = current["summary"]
    simulated_summary = simulated["summary"]
    return {
        "projected_year": numeric_delta(
            current_summary["projected_year"]["value"],
            simulated_summary["projected_year"]["value"],
        ),
        "productive_capital": money_delta(current_summary, simulated_summary, "productive_capital"),
        "net_worth": money_delta(current_summary, simulated_summary, "net_worth"),
        "target_capital": money_delta(current_summary, simulated_summary, "target_capital"),
    }


def money_delta(current: dict[str, Any], simulated: dict[str, Any], key: str) -> str:
    return str(q2(Decimal(str(simulated[key]["value"])) - Decimal(str(current[key]["value"]))))


def numeric_delta(current: int | None, simulated: int | None) -> int | None:
    if current is None or simulated is None:
        return None
    return int(simulated) - int(current)


def budget_lines_for_scenario(scenario: Scenario) -> list[BudgetLine]:
    custom_lines = []
    for event in scenario.events.all():
        custom_lines.extend(event.metadata_json.get("budget_lines", []))
    if custom_lines:
        return [line_from_metadata(line) for line in custom_lines]
    return [
        line
        for event in scenario.events.all().order_by("start_date", "id")
        for line in default_budget_lines_for_event(scenario=scenario, event=event)
    ]


def default_budget_lines_for_event(*, scenario: Scenario, event) -> list[BudgetLine]:
    lines: list[BudgetLine] = []
    one_off_items = event.metadata_json.get("one_off_items", [])
    if one_off_items:
        category, subcategory, role = default_purchase_budget_mapping(scenario.template_type)
        for item in one_off_items:
            lines.append(
                BudgetLine(
                    kind="expense",
                    name=f"{scenario.name} - {str(item['name']).strip()}",
                    category=category,
                    subcategory=subcategory,
                    amount=q2(Decimal(str(item["amount"]))),
                    fiscal_year=event.start_date.year,
                    target_month=event.start_date.month,
                    term_start_month=None,
                    term_end_year=None,
                    term_end_month=None,
                    cashflow_role=role,
                )
            )
    elif event.initial_outflow > 0:
        category, subcategory, role = default_purchase_budget_mapping(scenario.template_type)
        lines.append(
            BudgetLine(
                kind="expense",
                name=f"{scenario.name} - entrada",
                category=category,
                subcategory=subcategory,
                amount=q2(Decimal(event.initial_outflow)),
                fiscal_year=event.start_date.year,
                target_month=event.start_date.month,
                term_start_month=None,
                term_end_year=None,
                term_end_month=None,
                cashflow_role=role,
            )
        )
    if event.new_debt_principal > 0 and event.new_debt_term_months:
        monthly_payment = debt_monthly_payment(
            principal=Decimal(event.new_debt_principal),
            annual_rate=Decimal(event.new_debt_interest_rate or 0),
            term_months=event.new_debt_term_months,
        )
        category, subcategory, role = default_debt_budget_mapping(scenario.template_type)
        lines.extend(
            recurring_budget_lines(
                name=f"{scenario.name} - financiación",
                category=category,
                subcategory=subcategory,
                monthly_amount=monthly_payment,
                start=event.start_date,
                end=end_date_from_term(event.start_date, event.new_debt_term_months),
                cashflow_role=role,
            )
        )
    if event.monthly_expense_delta > 0:
        category, subcategory, role = default_recurring_expense_budget_mapping(
            scenario.template_type
        )
        # Sin fecha fin, el gasto recurrente es indefinido (p. ej. el coste de
        # un coche sigue tras amortizar el préstamo); la baja del activo será
        # la que retire el gasto en el futuro.
        lines.extend(
            recurring_budget_lines(
                name=f"{scenario.name} - gasto recurrente",
                category=category,
                subcategory=subcategory,
                monthly_amount=Decimal(event.monthly_expense_delta),
                start=event.start_date,
                end=event.end_date,
                cashflow_role=role,
            )
        )
    if event.monthly_contribution_delta > 0:
        destination = event.monthly_contribution_destination
        category = cast(str, AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS)
        subcategory = "other_financial_investments"
        role = cast(str, AnnualExpenseEntry.CashflowRole.INVESTMENT)
        if destination == event.ContributionDestination.SECURITY:
            role = cast(str, AnnualExpenseEntry.CashflowRole.SAVINGS)
        elif destination == event.ContributionDestination.DEBT:
            category = cast(str, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES)
            subcategory = "financial_commitments"
            role = cast(str, AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT)
        lines.extend(
            recurring_budget_lines(
                name=f"{scenario.name} - aportación",
                category=category,
                subcategory=subcategory,
                monthly_amount=Decimal(event.monthly_contribution_delta),
                start=event.start_date,
                end=event.end_date,
                cashflow_role=role,
            )
        )
    if event.monthly_income_delta > 0:
        lines.extend(
            recurring_income_lines(
                name=f"{scenario.name} - ingreso recurrente",
                monthly_amount=Decimal(event.monthly_income_delta),
                start=event.start_date,
                end=event.end_date,
            )
        )
    return lines


def create_budget_entries_for_scenario(*, scenario: Scenario, plan_event: PlanEvent) -> int:
    created = 0
    for line in budget_lines_for_scenario(scenario):
        if line.amount <= 0:
            continue
        if line.kind == "income":
            validate_annual_income_taxonomy(category=line.category, subcategory=line.subcategory)
            AnnualIncomeEntry.objects.create(
                user=scenario.plan.user,
                name=line.name,
                category=line.category,
                subcategory=line.subcategory,
                income_type=AnnualIncomeEntry.IncomeType.ONE_OFF
                if line.time_profile == "one_off"
                else AnnualIncomeEntry.IncomeType.RECURRENT,
                time_profile=line.time_profile,
                cashflow_role=line.cashflow_role,
                event_group=f"plan_event:{plan_event.id}",
                target_month=line.target_month,
                term_start_month=line.term_start_month,
                term_end_year=line.term_end_year,
                term_end_month=line.term_end_month,
                amount_annual=line.amount,
                fiscal_year=line.fiscal_year,
                currency="EUR",
                notes="Generado automaticamente desde Mi Plan.",
            )
        else:
            validate_annual_expense_taxonomy(category=line.category, subcategory=line.subcategory)
            AnnualExpenseEntry.objects.create(
                user=scenario.plan.user,
                is_system_generated=True,
                name=line.name,
                category=line.category,
                subcategory=line.subcategory,
                expense_type=AnnualExpenseEntry.ExpenseType.ONE_OFF
                if line.time_profile == "one_off"
                else AnnualExpenseEntry.ExpenseType.RECURRENT,
                time_profile=line.time_profile,
                cashflow_role=line.cashflow_role,
                event_group=f"plan_event:{plan_event.id}",
                target_month=line.target_month,
                term_start_month=line.term_start_month,
                term_end_year=line.term_end_year,
                term_end_month=line.term_end_month,
                amount_annual=line.amount,
                fiscal_year=line.fiscal_year,
                currency="EUR",
                notes="Generado automaticamente desde Mi Plan.",
            )
        created += 1
    return created


def line_from_metadata(line: dict[str, Any]) -> BudgetLine:
    default_profile = "term_recurrent" if line.get("term_end_year") else "one_off"
    return BudgetLine(
        kind=line.get("kind", "expense"),
        name=str(line["name"]),
        category=str(line["category"]),
        subcategory=str(line["subcategory"]),
        amount=q2(Decimal(str(line["amount"]))),
        fiscal_year=int(line["fiscal_year"]),
        target_month=line.get("target_month"),
        term_start_month=line.get("term_start_month"),
        term_end_year=line.get("term_end_year"),
        term_end_month=line.get("term_end_month"),
        cashflow_role=str(line.get("cashflow_role") or AnnualExpenseEntry.CashflowRole.OPERATING),
        time_profile=str(line.get("time_profile") or default_profile),
    )


def default_purchase_budget_mapping(template_type: str) -> tuple[str, str, str]:
    if template_type == Scenario.TemplateType.VEHICLE:
        return (
            cast(str, AnnualExpenseEntry.Category.TANGIBLE_ASSETS),
            "vehicle_purchase",
            cast(str, AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE),
        )
    if template_type == Scenario.TemplateType.HOUSING:
        return (
            cast(str, AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS),
            "property_purchase",
            cast(str, AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE),
        )
    if template_type == Scenario.TemplateType.RENOVATION:
        return (
            cast(str, AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS),
            "property_improvements",
            cast(str, AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE),
        )
    return (
        cast(str, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES),
        "other_consumption_expenses",
        cast(str, AnnualExpenseEntry.CashflowRole.OPERATING),
    )


def default_debt_budget_mapping(template_type: str) -> tuple[str, str, str]:
    if template_type == Scenario.TemplateType.HOUSING:
        return (
            cast(str, AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS),
            "mortgage_principal",
            cast(str, AnnualExpenseEntry.CashflowRole.ASSET_PURCHASE),
        )
    return (
        cast(str, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES),
        "personal_loan_repayment",
        cast(str, AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT),
    )


def default_recurring_expense_budget_mapping(template_type: str) -> tuple[str, str, str]:
    if template_type == Scenario.TemplateType.VEHICLE:
        return (
            cast(str, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES),
            "transport_mobility",
            cast(str, AnnualExpenseEntry.CashflowRole.OPERATING),
        )
    if template_type == Scenario.TemplateType.HOUSING:
        return (
            cast(str, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES),
            "housing_home",
            cast(str, AnnualExpenseEntry.CashflowRole.OPERATING),
        )
    if template_type == Scenario.TemplateType.STUDIES:
        return (
            cast(str, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES),
            "education_growth",
            cast(str, AnnualExpenseEntry.CashflowRole.OPERATING),
        )
    return (
        cast(str, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES),
        "other_consumption_expenses",
        cast(str, AnnualExpenseEntry.CashflowRole.OPERATING),
    )


def recurring_budget_lines(
    *,
    name: str,
    category: str,
    subcategory: str,
    monthly_amount: Decimal,
    start: date,
    end: date | None,
    cashflow_role: str,
) -> list[BudgetLine]:
    return [
        BudgetLine(
            kind="expense",
            name=name,
            category=category,
            subcategory=subcategory,
            amount=slot.amount(monthly_amount),
            fiscal_year=slot.fiscal_year,
            target_month=None,
            term_start_month=slot.term_start_month,
            term_end_year=slot.term_end_year,
            term_end_month=slot.term_end_month,
            cashflow_role=cashflow_role,
            time_profile=slot.time_profile,
        )
        for slot in recurring_year_slots(start=start, end=end)
    ]


def recurring_income_lines(
    *, name: str, monthly_amount: Decimal, start: date, end: date | None
) -> list[BudgetLine]:
    return [
        BudgetLine(
            kind="income",
            name=name,
            category=cast(str, AnnualIncomeEntry.Category.OTHER_INCOME),
            subcategory="other",
            amount=slot.amount(monthly_amount),
            fiscal_year=slot.fiscal_year,
            target_month=None,
            term_start_month=slot.term_start_month,
            term_end_year=slot.term_end_year,
            term_end_month=slot.term_end_month,
            cashflow_role=cast(str, AnnualIncomeEntry.CashflowRole.OTHER),
            time_profile=slot.time_profile,
        )
        for slot in recurring_year_slots(start=start, end=end)
    ]


@dataclass(frozen=True)
class RecurringYearSlot:
    fiscal_year: int
    months: int
    term_start_month: int | None
    term_end_year: int | None
    term_end_month: int | None
    time_profile: str

    def amount(self, monthly_amount: Decimal) -> Decimal:
        return q2(monthly_amount * Decimal(self.months))


def recurring_year_slots(*, start: date, end: date | None) -> list[RecurringYearSlot]:
    """Genera un slot por año con el término recortado a ese año.

    Cada línea anual debe declarar solo su propio tramo: si compartieran el
    término global del evento, el filtro anual del presupuesto las contaría
    en todos los años que cubre el término (duplicando importes). Sin fecha
    fin, el gasto es estructural: un slot de término para el año inicial
    parcial (si lo hay) y un slot estructural indefinido desde el siguiente
    año completo.
    """
    if end is None:
        slots = []
        if start.month > 1:
            slots.append(
                RecurringYearSlot(
                    fiscal_year=start.year,
                    months=12 - start.month + 1,
                    term_start_month=start.month,
                    term_end_year=start.year,
                    term_end_month=12,
                    time_profile="term_recurrent",
                )
            )
        slots.append(
            RecurringYearSlot(
                fiscal_year=start.year + 1 if start.month > 1 else start.year,
                months=12,
                term_start_month=None,
                term_end_year=None,
                term_end_month=None,
                time_profile="structural_recurrent",
            )
        )
        return slots
    slots = []
    for year in range(start.year, end.year + 1):
        start_month = start.month if year == start.year else 1
        end_month = end.month if year == end.year else 12
        slots.append(
            RecurringYearSlot(
                fiscal_year=year,
                months=max(1, end_month - start_month + 1),
                term_start_month=start_month,
                term_end_year=year,
                term_end_month=end_month,
                time_profile="term_recurrent",
            )
        )
    return slots


def debt_monthly_payment(*, principal: Decimal, annual_rate: Decimal, term_months: int) -> Decimal:
    months = max(1, term_months)
    monthly_rate = annual_rate / Decimal("12")
    if monthly_rate <= 0:
        return q2(principal / Decimal(months))
    payment = principal * monthly_rate / (Decimal("1") - (Decimal("1") + monthly_rate) ** -months)
    return q2(payment)


def end_date_from_term(start: date, term_months: int) -> date:
    total = start.month - 1 + max(1, term_months) - 1
    year = start.year + total // 12
    month = total % 12 + 1
    return date(year, month, 1)


def term_years_from_months(term_months: int | None) -> int:
    if not term_months:
        return 0
    return max(1, (term_months + 11) // 12)


def q2(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)
