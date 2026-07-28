from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from accounts.models import UserSettings
from budget.models import AnnualExpenseEntry
from memberships.models import FamilyMember
from net_worth.models import InvestmentContributionInterval, Liability

from .models import AssumptionSet, FinancialPlan, PlanEvent, ProjectionSnapshot
from .services_classification import AssetClassificationService, ClassificationSummary
from .services_quality import DataQualityService
from .services_inputs import one_off_flows, plan_fiscal_year, structural_income


MONEY = Decimal("0.01")


def q2(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def decimal_str(value: Decimal) -> str:
    return str(q2(value))


@dataclass(frozen=True)
class ProjectionInputs:
    plan_id: int
    target_date: date
    target_monthly_income_today_eur: Decimal
    projection_end_date: date
    preservation_target_eur: Decimal | None
    productive_capital: Decimal
    security_capital: Decimal
    family_use_capital: Decimal
    short_term_goal_capital: Decimal
    unknown_capital: Decimal
    total_liabilities: Decimal
    associated_liabilities: Decimal
    net_worth: Decimal
    annual_income: Decimal
    annual_planned_contributions: Decimal
    annual_pension_income_today: Decimal
    annual_other_future_income_today: Decimal
    earliest_pension_start_date: date | None
    employment_income_end_date: date | None
    liability_principal: Decimal
    liability_weighted_rate: Decimal
    liability_max_term_years: int
    plan_events: tuple[dict[str, Any], ...] = ()
    # Flujos puntuales de presupuesto (no gobernados por Decisiones) agregados por
    # año; se aplican en su año en todo el horizonte. Ver services_inputs.one_off_flows.
    one_off_flows: tuple[dict[str, Any], ...] = ()


class ProjectionService:
    def recalculate(
        self, *, plan: FinancialPlan, assumption_name: str = "expected"
    ) -> dict[str, Any]:
        assumption_set = get_assumption_set(name=assumption_name)
        result = self.calculate(plan=plan, assumption_set=assumption_set)
        ProjectionSnapshot.objects.create(
            plan=plan,
            assumption_set=assumption_set,
            assumption_values=result["assumptions"],
            input_hash=result["input_hash"],
            result_json=result,
            quality_level=result["quality_level"],
            is_official=True,
        )
        return result

    def calculate(
        self,
        *,
        plan: FinancialPlan,
        assumption_set: AssumptionSet,
        extra_events: list[dict[str, Any]] | None = None,
        include_plan_events: bool = True,
        retirement_year: int | None = None,
    ) -> dict[str, Any]:
        inputs, classification, quality = build_projection_inputs(
            plan=plan,
            extra_events=extra_events,
            include_plan_events=include_plan_events,
        )
        # Permite proyectar un retiro hipotetico (p. ej. la jubilacion sostenible
        # calculada) sin mutar plan.target_date, que sigue siendo la aspiracion.
        if retirement_year is not None:
            inputs = with_retirement(inputs, retirement_year)
        assumptions = serialize_assumptions(assumption_set)
        input_hash = stable_hash({"inputs": serialize_inputs(inputs), "assumptions": assumptions})
        metrics = calculate_projection(inputs=inputs, assumptions=assumptions)
        calculated_at = None
        return {
            "scenario": assumption_set.name,
            "input_hash": input_hash,
            "calculated_at": calculated_at,
            "quality_level": quality.level,
            "quality_factors": quality.factors,
            "assumptions": assumptions,
            "summary": wrap_metrics(metrics["summary"], assumptions, quality.level, calculated_at),
            "trajectory": metrics["trajectory"],
            "classification": serialize_classification(classification),
        }

    def calculate_all_scenarios(self, *, plan: FinancialPlan) -> dict[str, Any]:
        return {
            assumption.name: self.calculate(plan=plan, assumption_set=assumption)
            for assumption in AssumptionSet.objects.filter(
                name__in=["prudent", "expected", "favorable"]
            ).order_by("name")
        }


def get_assumption_set(*, name: str | None = None) -> AssumptionSet:
    if name:
        found = AssumptionSet.objects.filter(name=name).first()
        if found:
            return found
    return AssumptionSet.objects.filter(is_default=True).first() or AssumptionSet.objects.first()


def build_projection_inputs(
    *,
    plan: FinancialPlan,
    extra_events: list[dict[str, Any]] | None = None,
    include_plan_events: bool = True,
) -> tuple[ProjectionInputs, ClassificationSummary, Any]:
    settings, _ = UserSettings.objects.get_or_create(user=plan.user)
    base_currency = (settings.base_currency or "EUR").upper()
    classification = AssetClassificationService().summarize(
        user=plan.user, base_currency=base_currency
    )
    annual_income = structural_income(plan)
    planned_contributions = planned_contribution_amount(plan=plan)
    members = list(plan.members.filter(role=FamilyMember.Role.ADULT, is_active=True).order_by("id"))
    pension_income = sum(
        (
            Decimal(member.estimated_monthly_pension_today_eur or 0) * Decimal("12")
            for member in members
        ),
        Decimal("0"),
    )
    other_future_income = sum(
        (Decimal(member.other_future_income_today_eur or 0) * Decimal("12") for member in members),
        Decimal("0"),
    )
    pension_dates = [member.pension_start_date for member in members if member.pension_start_date]
    liabilities = list(Liability.objects.filter(user=plan.user, is_active=True))
    liability_principal = sum(
        (Decimal(liability.amount) for liability in liabilities),
        Decimal("0"),
    )
    weighted_rate = weighted_liability_rate(liabilities=liabilities)
    max_term_years = max(
        [liability_term_years(liability) for liability in liabilities],
        default=0,
    )
    quality = DataQualityService().evaluate(user=plan.user)
    event_payloads: list[dict[str, Any]] = []
    if include_plan_events:
        event_payloads.extend(plan_event_payloads(plan=plan))
    if extra_events:
        event_payloads.extend(extra_events)
    return (
        ProjectionInputs(
            plan_id=plan.id,
            target_date=plan.target_date,
            target_monthly_income_today_eur=Decimal(plan.target_monthly_income_today_eur),
            projection_end_date=plan.projection_end_date,
            preservation_target_eur=(
                Decimal(plan.preservation_target_eur)
                if plan.preservation_target_eur is not None
                else None
            ),
            productive_capital=classification.productive_capital,
            security_capital=classification.security_capital,
            family_use_capital=classification.family_use_capital,
            short_term_goal_capital=classification.short_term_goal_capital,
            unknown_capital=classification.unknown_capital,
            total_liabilities=classification.total_liabilities,
            associated_liabilities=classification.associated_liabilities,
            net_worth=classification.net_worth,
            annual_income=annual_income,
            annual_planned_contributions=planned_contributions,
            annual_pension_income_today=pension_income,
            annual_other_future_income_today=other_future_income,
            earliest_pension_start_date=min(pension_dates) if pension_dates else None,
            # La fecha objetivo significa que trabajar pasa a ser opcional.
            employment_income_end_date=plan.target_date,
            liability_principal=liability_principal,
            liability_weighted_rate=weighted_rate,
            liability_max_term_years=max_term_years,
            plan_events=tuple(event_payloads),
            one_off_flows=tuple(one_off_flows(plan=plan)),
        ),
        classification,
        quality,
    )


def calculate_projection(
    *, inputs: ProjectionInputs, assumptions: dict[str, str]
) -> dict[str, Any]:
    inflation = Decimal(assumptions["inflation_rate"])
    productive_return = Decimal(assumptions["productive_return_rate"])
    non_productive_return = Decimal(assumptions["non_productive_appreciation_rate"])
    contribution_growth = Decimal(assumptions["contribution_growth_rate"])
    withdrawal_rate = Decimal(assumptions["withdrawal_rate"])

    start_year = date.today().year
    target_year = inputs.target_date.year
    end_year = inputs.projection_end_date.year
    productive = inputs.productive_capital
    security = inputs.security_capital
    non_productive = (
        inputs.family_use_capital + inputs.short_term_goal_capital + inputs.unknown_capital
    )
    liabilities = inputs.total_liabilities
    base_liabilities = inputs.total_liabilities
    rows: list[dict[str, Any]] = []
    projected_year: int | None = None
    applied_one_off_events: set[int] = set()
    active_event_debts: list[dict[str, Decimal | int]] = []
    debt_contributions = Decimal("0")
    # Pasivos cancelados por una venta de activo (Decisión): se restan del saldo de
    # deuda a partir del año de la venta.
    disposed_liability_total = Decimal("0")

    # El patrimonio a preservar es capital que no se toca: se exige además del
    # capital que sostiene la renta. Antes solo era una comprobación sobre el
    # patrimonio neto total (vivienda incluida) que casi nunca cambiaba nada.
    preservation_extra = inputs.preservation_target_eur or Decimal("0")

    denominator = (
        target_capital_for_year(
            inputs=inputs,
            assumptions=assumptions,
            candidate_year=target_year,
            start_year=start_year,
        )
        + preservation_extra
    )
    sustainable_income = productive * withdrawal_rate / Decimal("12")
    progress = (
        Decimal("100")
        if denominator <= 0
        else min(Decimal("100"), productive / denominator * Decimal("100"))
    )

    for offset, year in enumerate(range(start_year, end_year + 1)):
        event_delta = event_deltas_for_year(
            events=inputs.plan_events,
            year=year,
            start_year=start_year,
        )
        nominal_target_income = (
            inflate(
                inputs.target_monthly_income_today_eur * Decimal("12"),
                inflation,
                max(0, year - start_year),
            )
            + event_delta["annual_expense_delta"]
        )
        future_income = (
            future_income_for_year(
                inputs=inputs,
                assumptions=assumptions,
                year=year,
                start_year=start_year,
            )
            + event_delta["annual_income_delta"]
        )
        withdrawals = (
            max(Decimal("0"), nominal_target_income - future_income)
            if year >= target_year
            else Decimal("0")
        )
        if offset > 0:
            contribution = (
                inflate(
                    inputs.annual_planned_contributions,
                    contribution_growth,
                    offset,
                )
                + event_delta["annual_productive_contribution_delta"]
            )
            productive = max(
                Decimal("0"),
                productive * (Decimal("1") + productive_return) + contribution - withdrawals,
            )
            security += event_delta["annual_security_contribution_delta"]
            debt_contributions += event_delta["annual_debt_contribution_delta"]
            non_productive = non_productive * (Decimal("1") + non_productive_return)
            base_liabilities = projected_liability_balance(
                initial=inputs.total_liabilities,
                current_balance=base_liabilities,
                term_years=inputs.liability_max_term_years,
                year_offset=offset,
            )
        for event_index, event in enumerate(inputs.plan_events):
            if event_index in applied_one_off_events:
                continue
            if int(str(event["start_year"])) != year:
                continue
            productive, security = apply_initial_outflow(
                productive=productive,
                security=security,
                amount=Decimal(str(event.get("initial_outflow") or "0")),
            )
            asset_value = Decimal(str(event.get("new_asset_value") or "0"))
            asset_type = event.get("new_asset_type")
            if asset_value > 0:
                if asset_type == "productive":
                    productive += asset_value
                elif asset_type == "security":
                    security += asset_value
                else:
                    non_productive += asset_value
            debt_principal = Decimal(str(event.get("new_debt_principal") or "0"))
            if debt_principal > 0:
                # Sin plazo (dato incompleto), amortizar en 1 año evaporaría la deuda y
                # falsearía el patrimonio; se usa un plazo largo por defecto. El alta ya
                # exige el plazo cuando hay principal (PlannedDecisionRegisterSerializer).
                term_years = max(1, int(str(event.get("new_debt_term_years") or "30")))
                rate = Decimal(str(event.get("new_debt_interest_rate") or "0"))
                active_event_debts.append(
                    {
                        "start_year": year,
                        "principal": debt_principal,
                        "term_years": term_years,
                        "rate": rate,
                    }
                )
            disposed_value = Decimal(str(event.get("disposed_asset_value") or "0"))
            if disposed_value > 0:
                # Venta de activo: se retira su valor proyectado del bucket (deja de
                # contar y de revalorizarse) y los ingresos netos entran como capital
                # productivo (ya líquido e invertible). Simétrico a `new_asset_value`.
                disposed_type = event.get("disposed_asset_type")
                disposed_rate = {
                    "productive": productive_return,
                    "security": Decimal("0"),
                }.get(disposed_type, non_productive_return)
                grown = inflate(disposed_value, disposed_rate, max(0, year - start_year))
                if disposed_type == "productive":
                    productive = max(Decimal("0"), productive - grown)
                elif disposed_type == "security":
                    security = max(Decimal("0"), security - grown)
                else:
                    non_productive = max(Decimal("0"), non_productive - grown)
            productive += Decimal(str(event.get("proceeds") or "0"))
            disposed_liability_total += Decimal(str(event.get("disposed_liability_value") or "0"))
            applied_one_off_events.add(event_index)
        flow = one_off_flow_for_year(inputs.one_off_flows, year)
        if flow is not None:
            productive += Decimal(str(flow["income"])) + Decimal(str(flow["contribution"]))
            asset_purchase = Decimal(str(flow["asset_purchase"]))
            if asset_purchase > 0:
                # Compra de activo con caja: sale del capital productivo (baja la
                # renta futura) y pasa a no-productivo (conserva patrimonio).
                productive = max(Decimal("0"), productive - asset_purchase)
                non_productive += asset_purchase
            productive, security = apply_initial_outflow(
                productive=productive,
                security=security,
                amount=Decimal(str(flow["outflow"])),
            )
        liabilities = max(
            Decimal("0"),
            base_liabilities
            + event_debt_balance(debts=active_event_debts, year=year)
            - debt_contributions
            - disposed_liability_total,
        )
        required = (
            target_capital_for_year(
                inputs=inputs,
                assumptions=assumptions,
                candidate_year=year,
                start_year=start_year,
            )
            + preservation_extra
        )
        # Los buckets (productive/security/non_productive) ya vienen netos de su
        # deuda asociada; restar `liabilities` (deuda total) la contaría dos veces.
        # Se suma de vuelta la asociada para que el patrimonio reconcilie con el real.
        # Al vender un activo se cancela su deuda asociada: se descuenta de ambos
        # términos a la vez para no descuadrar el patrimonio neto.
        net_worth = (
            productive
            + security
            + non_productive
            - liabilities
            + max(Decimal("0"), inputs.associated_liabilities - disposed_liability_total)
        )
        preservation_ok = (
            inputs.preservation_target_eur is None or net_worth >= inputs.preservation_target_eur
        )
        if projected_year is None and productive >= required and preservation_ok:
            projected_year = year
        rows.append(
            {
                "year": year,
                "productive_capital": decimal_str(productive),
                "security_capital": decimal_str(security),
                "non_productive_assets": decimal_str(non_productive),
                "liabilities": decimal_str(liabilities),
                "net_worth": decimal_str(net_worth),
                "target_capital": decimal_str(required),
                "annual_target_income": decimal_str(nominal_target_income),
                "future_income": decimal_str(future_income),
                "annual_withdrawals": decimal_str(withdrawals),
                "preservation_ok": preservation_ok,
            }
        )

    summary = {
        "target_capital": denominator,
        "target_capital_denominator": denominator,
        "productive_capital": inputs.productive_capital,
        "security_capital": inputs.security_capital,
        "net_worth": inputs.net_worth,
        "monthly_sustainable_income": sustainable_income,
        "progress_percent": progress,
        "projected_year": projected_year,
        "target_year": target_year,
        "preservation_target_eur": inputs.preservation_target_eur,
    }
    return {"summary": summary, "trajectory": rows}


def retirement_date_for_year(*, year: int, reference: date) -> date:
    """Fecha de retiro en `year` conservando mes/dia del objetivo (con guarda 29-feb)."""
    try:
        return date(year, reference.month, reference.day)
    except ValueError:
        return date(year, reference.month, 28)


def with_retirement(inputs: ProjectionInputs, retirement_year: int) -> ProjectionInputs:
    """Reproyecta `inputs` con el retiro (dejar de trabajar y vivir del plan) en `retirement_year`."""
    retirement = retirement_date_for_year(year=retirement_year, reference=inputs.target_date)
    return replace(inputs, target_date=retirement, employment_income_end_date=retirement)


def earliest_sustainable_retirement_year(
    *, inputs: ProjectionInputs, assumptions: dict[str, str]
) -> int | None:
    """Primer año en que retirarse es sostenible: el capital productivo nunca
    baja del patrimonio a preservar entre el retiro y el fin de proyección.

    Retirarse en `R` = dejar de trabajar y vivir del plan desde `R`. La
    factibilidad es monótona (trabajar un año más nunca empeora la foto), así que
    se resuelve por búsqueda binaria reutilizando `calculate_projection`, sin
    volver a consultar la BD (reusa `inputs`).
    """
    floor = inputs.preservation_target_eur or Decimal("0")
    start_year = date.today().year
    end_year = inputs.projection_end_date.year

    def is_sustainable(candidate: int) -> bool:
        candidate_inputs = with_retirement(inputs, candidate)
        metrics = calculate_projection(inputs=candidate_inputs, assumptions=assumptions)
        after = [
            Decimal(row["productive_capital"])
            for row in metrics["trajectory"]
            if row["year"] >= candidate
        ]
        if not after:
            return False
        minimum = min(after)
        return minimum >= floor if floor > 0 else minimum > 0

    if not is_sustainable(end_year):
        return None

    low, high = min(start_year, end_year), end_year
    while low < high:
        mid = (low + high) // 2
        if is_sustainable(mid):
            high = mid
        else:
            low = mid + 1
    return low


def target_capital_for_year(
    *,
    inputs: ProjectionInputs,
    assumptions: dict[str, str],
    candidate_year: int,
    start_year: int,
    annual_need_today: Decimal | None = None,
    include_event_deltas: bool = True,
) -> Decimal:
    """Capital requerido en `candidate_year` para sostener una necesidad anual.

    Por defecto la necesidad es el nivel de vida del plan con los deltas de
    acontecimientos incorporados (el denominador de la proyección). Con
    `annual_need_today` se calcula para otra necesidad (p. ej. un grupo de
    gastos del presupuesto); en ese caso `include_event_deltas=False` evita
    sumar gastos de decisiones que no pertenecen a esa necesidad.
    """
    inflation = Decimal(assumptions["inflation_rate"])
    productive_return = Decimal(assumptions["productive_return_rate"])
    withdrawal_rate = Decimal(assumptions["withdrawal_rate"])
    target_year = max(candidate_year, inputs.target_date.year)
    pension_year = (
        inputs.earliest_pension_start_date.year if inputs.earliest_pension_start_date else None
    )
    base_annual_need = (
        annual_need_today
        if annual_need_today is not None
        else inputs.target_monthly_income_today_eur * Decimal("12")
    )
    zero_delta = {"annual_expense_delta": Decimal("0"), "annual_income_delta": Decimal("0")}

    def deltas(year: int) -> dict[str, Decimal]:
        if not include_event_deltas:
            return zero_delta
        return event_deltas_for_year(
            events=inputs.plan_events,
            year=year,
            start_year=start_year,
        )

    event_delta = deltas(target_year)
    target_income = (
        inflate(
            base_annual_need,
            inflation,
            max(0, target_year - start_year),
        )
        + event_delta["annual_expense_delta"]
    )
    post_pension_income = (
        inflate(
            inputs.annual_pension_income_today + inputs.annual_other_future_income_today,
            inflation,
            max(0, target_year - start_year),
        )
        + event_delta["annual_income_delta"]
    )
    if pension_year is None or target_year >= pension_year:
        return q2(max(Decimal("0"), target_income - post_pension_income) / withdrawal_rate)

    bridge = Decimal("0")
    for year in range(target_year, pension_year):
        nominal_need = (
            inflate(
                base_annual_need,
                inflation,
                max(0, year - start_year),
            )
            + deltas(year)["annual_expense_delta"]
        )
        other_income = (
            inflate(
                inputs.annual_other_future_income_today,
                inflation,
                max(0, year - start_year),
            )
            + deltas(year)["annual_income_delta"]
        )
        gap = max(Decimal("0"), nominal_need - other_income)
        discount_years = year - target_year
        bridge += gap / ((Decimal("1") + productive_return) ** discount_years)
    pension_need = (
        inflate(
            base_annual_need,
            inflation,
            max(0, pension_year - start_year),
        )
        + deltas(pension_year)["annual_expense_delta"]
    )
    pension_income = (
        inflate(
            inputs.annual_pension_income_today + inputs.annual_other_future_income_today,
            inflation,
            max(0, pension_year - start_year),
        )
        + deltas(pension_year)["annual_income_delta"]
    )
    post_pension_capital = max(Decimal("0"), pension_need - pension_income) / withdrawal_rate
    bridge += post_pension_capital / (
        (Decimal("1") + productive_return) ** max(0, pension_year - target_year)
    )
    return q2(bridge)


def capital_requirements(
    *,
    plan: FinancialPlan,
    assumption_name: str | None = None,
    monthly_amounts: list[Decimal],
) -> dict[str, Any]:
    """Capital requerido en la fecha objetivo para sostener cada gasto mensual dado.

    Misma matemática que el denominador de la proyección (inflación, pensiones
    como offset, periodo puente y tasa de retirada), con la necesidad anual
    sustituida por cada importe (en euros de hoy) y sin deltas de
    acontecimientos: el importe pedido ya define el gasto a cubrir.
    """
    assumption_set = get_assumption_set(name=assumption_name)
    assumptions = serialize_assumptions(assumption_set)
    inputs, _, _ = build_projection_inputs(plan=plan)
    start_year = date.today().year
    target_year = inputs.target_date.year
    requirements = [
        {
            "monthly_amount_today_eur": decimal_str(q2(amount)),
            "capital_required_eur": decimal_str(
                target_capital_for_year(
                    inputs=inputs,
                    assumptions=assumptions,
                    candidate_year=target_year,
                    start_year=start_year,
                    annual_need_today=amount * Decimal("12"),
                    include_event_deltas=False,
                )
            ),
        }
        for amount in monthly_amounts
    ]
    return {
        "scenario": assumption_set.name,
        "target_year": target_year,
        "assumptions": assumptions,
        "requirements": requirements,
    }


def future_income_for_year(
    *,
    inputs: ProjectionInputs,
    assumptions: dict[str, str],
    year: int,
    start_year: int,
) -> Decimal:
    inflation = Decimal(assumptions["inflation_rate"])
    income_growth = Decimal(assumptions["income_growth_rate"])
    labor_income = Decimal("0")
    if inputs.employment_income_end_date is None or year < inputs.employment_income_end_date.year:
        labor_income = inflate(inputs.annual_income, income_growth, max(0, year - start_year))
    pension_income = Decimal("0")
    if inputs.earliest_pension_start_date and year >= inputs.earliest_pension_start_date.year:
        pension_income = inflate(
            inputs.annual_pension_income_today,
            inflation,
            max(0, year - start_year),
        )
    other = inflate(
        inputs.annual_other_future_income_today,
        inflation,
        max(0, year - start_year),
    )
    return labor_income + pension_income + other


def inflate(amount: Decimal, rate: Decimal, years: int) -> Decimal:
    return amount * ((Decimal("1") + rate) ** years)


def projected_liability_balance(
    *,
    initial: Decimal,
    current_balance: Decimal,
    term_years: int,
    year_offset: int,
) -> Decimal:
    if initial <= 0 or term_years <= 0:
        return Decimal("0")
    annual_principal = initial / Decimal(term_years)
    return max(Decimal("0"), current_balance - annual_principal)


def sum_active_amounts(queryset) -> Decimal:
    return sum((Decimal(row.amount_annual) for row in queryset), Decimal("0"))


def planned_contribution_amount(*, plan: FinancialPlan) -> Decimal:
    user = plan.user
    budgeted = sum_active_amounts(
        AnnualExpenseEntry.objects.filter(
            user=user,
            is_active=True,
            fiscal_year=plan_fiscal_year(plan),
            cashflow_role__in=[
                AnnualExpenseEntry.CashflowRole.SAVINGS,
                AnnualExpenseEntry.CashflowRole.INVESTMENT,
            ],
        )
        # Solo las aportaciones generadas *desde un activo* son el espejo de los
        # InvestmentContributionInterval que se suman debajo: contarlas aqui las
        # duplicaria. Las generadas por escenarios aceptados (sin source_asset)
        # si son aportacion real y deben contar.
        .exclude(is_system_generated=True, source_asset__isnull=False)
    )
    intervals = Decimal("0")
    for interval in InvestmentContributionInterval.objects.filter(
        asset__user=user,
        asset__is_active=True,
    ):
        if interval.frequency == "weekly":
            intervals += Decimal(interval.amount) * Decimal("52")
        else:
            intervals += Decimal(interval.amount) * Decimal("12")
    return budgeted + intervals


def weighted_liability_rate(*, liabilities: list[Liability]) -> Decimal:
    total = sum((Decimal(liability.amount) for liability in liabilities), Decimal("0"))
    if total <= 0:
        return Decimal("0")
    weighted = Decimal("0")
    for liability in liabilities:
        rate = Decimal(liability.annual_interest_tae or 0) / Decimal("100")
        weighted += Decimal(liability.amount) / total * rate
    return weighted


def liability_term_years(liability: Liability) -> int:
    if liability.term_months:
        return max(1, int((liability.term_months + 11) // 12))
    if liability.expected_end_date:
        return max(1, liability.expected_end_date.year - date.today().year)
    return 0


def plan_event_payloads(*, plan: FinancialPlan) -> list[dict[str, Any]]:
    current_year = plan_fiscal_year(plan)
    return [
        payload
        | {
            "effective_end_year": event.effective_end_date.year
            if event.effective_end_date
            else None,
            "effective_end_month": event.effective_end_date.month
            if event.effective_end_date
            else None,
            # Aceptar un escenario crea sus lineas de presupuesto. En cuanto llega su
            # año, esas lineas entran en el año fiscal en curso, que es de donde salen
            # la aportacion y el ingreso base de la proyeccion: el evento ya esta dentro
            # de la linea base y volver a sumar sus deltas los contaria dos veces.
            "baseline_absorbed": int(str(payload["start_year"])) <= current_year,
        }
        for event in PlanEvent.objects.filter(
            plan=plan,
            status=PlanEvent.Status.PLANNED,
        ).order_by("planned_date", "id")
        for payload in event.planned_impact_json.get("events", [])
    ]


def event_deltas_for_year(
    *, events: tuple[dict[str, Any], ...], year: int, start_year: int
) -> dict[str, Decimal]:
    del start_year
    result = {
        "annual_expense_delta": Decimal("0"),
        "annual_income_delta": Decimal("0"),
        "annual_productive_contribution_delta": Decimal("0"),
        "annual_security_contribution_delta": Decimal("0"),
        "annual_debt_contribution_delta": Decimal("0"),
    }
    for event in events:
        event_start = int(str(event["start_year"]))
        effective_end_year = event.get("effective_end_year")
        effective_end_month = event.get("effective_end_month")
        event_end = event.get("end_year")
        if year < event_start:
            continue
        if effective_end_year is not None and year > int(str(effective_end_year)):
            continue
        if event_end is not None and year > int(str(event_end)):
            continue
        debt_end_year = event.get("debt_end_year")
        expense_end_year = event_end
        if expense_end_year is None and debt_end_year is not None:
            expense_end_year = debt_end_year
        active_months = Decimal("12")
        if effective_end_year is not None and year == int(str(effective_end_year)):
            active_months = Decimal(max(0, int(str(effective_end_month or 1)) - 1))
        if expense_end_year is None or year <= int(str(expense_end_year)):
            # El gasto sube el nivel de vida objetivo, que el usuario declara y el
            # presupuesto no alimenta: nunca queda absorbido por la linea base.
            result["annual_expense_delta"] += (
                Decimal(str(event.get("monthly_expense_delta") or "0")) * active_months
            )
        if event.get("baseline_absorbed"):
            continue
        result["annual_income_delta"] += (
            Decimal(str(event.get("monthly_income_delta") or "0")) * active_months
        )
        destination = str(event.get("monthly_contribution_destination") or "productive")
        contribution_key = {
            "security": "annual_security_contribution_delta",
            "debt": "annual_debt_contribution_delta",
        }.get(destination, "annual_productive_contribution_delta")
        result[contribution_key] += (
            Decimal(str(event.get("monthly_contribution_delta") or "0")) * active_months
        )
    return result


def one_off_flow_for_year(flows: tuple[dict[str, Any], ...], year: int) -> dict[str, Any] | None:
    for flow in flows:
        if int(str(flow["year"])) == year:
            return flow
    return None


def apply_initial_outflow(
    *, productive: Decimal, security: Decimal, amount: Decimal
) -> tuple[Decimal, Decimal]:
    if amount <= 0:
        return productive, security
    from_security = min(security, amount)
    security -= from_security
    remaining = amount - from_security
    if remaining > 0:
        productive = max(Decimal("0"), productive - remaining)
    return productive, security


def event_debt_balance(*, debts: list[dict[str, Decimal | int]], year: int) -> Decimal:
    total = Decimal("0")
    for debt in debts:
        elapsed = max(0, year - int(debt["start_year"]))
        principal = Decimal(debt["principal"])
        term_years = int(debt["term_years"])
        rate = Decimal(debt["rate"])
        if rate > 0:
            balance = amortized_balance(
                principal=principal, annual_rate=rate, term_years=term_years, elapsed_years=elapsed
            )
        else:
            balance = max(
                Decimal("0"), principal - principal / Decimal(term_years) * Decimal(elapsed)
            )
        total += balance
    return total


def amortized_balance(
    *, principal: Decimal, annual_rate: Decimal, term_years: int, elapsed_years: int
) -> Decimal:
    months = max(1, term_years * 12)
    elapsed_months = min(months, max(0, elapsed_years * 12))
    monthly_rate = annual_rate / Decimal("12")
    if monthly_rate <= 0:
        return max(Decimal("0"), principal - principal / Decimal(months) * Decimal(elapsed_months))
    payment = principal * monthly_rate / (Decimal("1") - (Decimal("1") + monthly_rate) ** -months)
    balance = principal
    for _ in range(elapsed_months):
        interest = balance * monthly_rate
        principal_paid = payment - interest
        balance = max(Decimal("0"), balance - principal_paid)
    return balance


def serialize_assumptions(assumption_set: AssumptionSet) -> dict[str, str]:
    return {
        "name": assumption_set.name,
        "inflation_rate": str(assumption_set.inflation_rate),
        "productive_return_rate": str(assumption_set.productive_return_rate),
        "non_productive_appreciation_rate": str(assumption_set.non_productive_appreciation_rate),
        "income_growth_rate": str(assumption_set.income_growth_rate),
        "contribution_growth_rate": str(assumption_set.contribution_growth_rate),
        "withdrawal_rate": str(assumption_set.withdrawal_rate),
        "default_liability_rate": str(assumption_set.default_liability_rate),
    }


def serialize_inputs(inputs: ProjectionInputs) -> dict[str, Any]:
    return {
        key: str(value) if isinstance(value, (Decimal, date)) else value
        for key, value in inputs.__dict__.items()
    }


def stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def wrap_metrics(
    metrics: dict[str, Any],
    assumptions: dict[str, str],
    quality_level: str,
    calculated_at: str,
) -> dict[str, Any]:
    return {
        key: {
            "value": decimal_str(value) if isinstance(value, Decimal) else value,
            "unit": "EUR"
            if key not in {"progress_percent", "projected_year", "target_year"}
            else ("percent" if key == "progress_percent" else "year"),
            "assumptions": assumptions,
            "calculated_at": calculated_at,
            "quality_level": quality_level,
        }
        for key, value in metrics.items()
    }


def serialize_classification(classification: ClassificationSummary) -> dict[str, Any]:
    return {
        "productive_capital": decimal_str(classification.productive_capital),
        "security_capital": decimal_str(classification.security_capital),
        "family_use_capital": decimal_str(classification.family_use_capital),
        "short_term_goal_capital": decimal_str(classification.short_term_goal_capital),
        "unknown_capital": decimal_str(classification.unknown_capital),
        "total_assets": decimal_str(classification.total_assets),
        "total_liabilities": decimal_str(classification.total_liabilities),
        "net_worth": decimal_str(classification.net_worth),
        "assets": [
            {
                "asset_id": row.asset_id,
                "name": row.name,
                "category": row.category,
                "subcategory": row.subcategory,
                "function": row.function,
                "inferred_function": row.inferred_function,
                "override_function": row.override_function,
                "gross_value": decimal_str(row.gross_value),
                "associated_liabilities": decimal_str(row.associated_liabilities),
                "net_value": decimal_str(row.net_value),
                "currency": row.currency,
            }
            for row in classification.assets
        ],
    }
