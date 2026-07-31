from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from budget.models import AnnualExpenseEntry
from net_worth.models import Asset, Liability
from net_worth.services import get_effective_asset_amount, get_effective_liability_amount

from .models import FinancialPlan
from .services_projection import planned_contribution_amount
from .services_quality import DataQualityService
from .services_inputs import (
    annual_expense_entries,
    expense_buckets,
    plan_fiscal_year,
    structural_income,
)

MONEY = Decimal("0.01")
PCT = Decimal("0.0001")

# Un superávit comprometido negativo es un "esfuerzo temporal" (no un déficit
# estructural) si la base operativa permanente es positiva y los compromisos
# temporales vencen dentro de esta ventana, devolviendo el superávit a >=0.
TRANSIENT_SQUEEZE_MAX_YEARS = 3

ILLIQUID_INVESTMENT_SUBCATEGORIES = {
    Asset.Subcategory.PENSION_PLANS,
    Asset.Subcategory.REAL_ESTATE_CROWD,
    Asset.Subcategory.CROWDLENDING,
    Asset.Subcategory.OTHER,
}
# Fondo de emergencia clásico: solo caja y depósitos. Las inversiones líquidas
# (fondos, ETFs, acciones, cripto...) son vendibles pero no son el colchón: contar
# la cartera como emergencia inflaba la cobertura (31 meses con 15.000 € de caja).
EMERGENCY_INVESTMENT_SUBCATEGORIES = {
    Asset.Subcategory.DEPOSITS,
}

# El fondo de emergencia se puntúa contra su propio objetivo, no contra una escala
# ajena: con la anterior (3→12 meses) alcanzar el objetivo daba 33/100 y el cimiento
# seguía en rojo. Con este anclaje, el objetivo puntúa 100 y la mitad del objetivo
# es el suelo, así que "casi conseguido" cae en ámbar en vez de en crítico.
EMERGENCY_TARGET_MONTHS = Decimal("6")
EMERGENCY_FLOOR_MONTHS = EMERGENCY_TARGET_MONTHS / Decimal("2")


@dataclass(frozen=True)
class FoundationMetrics:
    payload: dict[str, Any]


def q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def q4(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value).quantize(PCT, rounding=ROUND_HALF_UP)


def clamp(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    return max(minimum, min(maximum, value))


def score_increasing(value: Decimal | None, minimum: Decimal, maximum: Decimal) -> Decimal:
    if value is None or maximum <= minimum:
        return Decimal("0")
    return clamp(
        (value - minimum) / (maximum - minimum) * Decimal("100"), Decimal("0"), Decimal("100")
    )


def score_decreasing(value: Decimal | None, minimum: Decimal, maximum: Decimal) -> Decimal:
    if value is None or maximum <= minimum:
        return Decimal("0")
    return clamp(
        (maximum - value) / (maximum - minimum) * Decimal("100"), Decimal("0"), Decimal("100")
    )


def weighted_score(items: list[tuple[Decimal, Decimal]]) -> Decimal:
    total_weight = sum((weight for _score, weight in items), Decimal("0"))
    if total_weight <= 0:
        return Decimal("0")
    total = sum((score * weight for score, weight in items), Decimal("0"))
    return clamp(total / total_weight, Decimal("0"), Decimal("100"))


def money(value: Decimal) -> str:
    return str(q2(value))


def ratio(value: Decimal | None) -> str | None:
    rounded = q4(value)
    return str(rounded) if rounded is not None else None


def score(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def health_status(value: int) -> str:
    """Banda de producto del score 0-100 ya redondeado (el que se muestra), para que
    el frontend coloree sin inventar umbrales y sin discrepar en los bordes."""
    if value >= 70:
        return "good"
    if value >= 40:
        return "warning"
    return "critical"


def health_grade(value: int) -> str:
    """Nota A-E del score ya redondeado.

    Recupera la escala de la Guía v1, pero **encajada en las bandas actuales** para
    que letra y color no puedan contradecirse: A y B son `good`, C y D `warning`,
    E `critical`. La letra añade granularidad dentro de la banda (una B avisa de que
    el margen es corto sin pintarse de ámbar)."""
    if value >= 85:
        return "A"
    if value >= 70:
        return "B"
    if value >= 55:
        return "C"
    if value >= 40:
        return "D"
    return "E"


def graded(value: Decimal | int) -> dict[str, Any]:
    """Trio score/status/grade a partir de un score sin redondear."""
    rounded = score(Decimal(value))
    return {
        "score": rounded,
        "status": health_status(rounded),
        "grade": health_grade(rounded),
    }


# Peso de cada cimiento en la nota global del bloque. El flujo de caja manda porque
# es lo que alimenta todo lo demás; la calidad de datos pesa poco porque mide la
# confianza en el diagnóstico, no la salud en sí.
FOUNDATION_WEIGHTS: tuple[tuple[str, Decimal], ...] = (
    ("cash_flow", Decimal("0.28")),
    ("emergency_fund", Decimal("0.22")),
    ("debt", Decimal("0.18")),
    ("planned_contribution", Decimal("0.14")),
    ("net_worth_health", Decimal("0.10")),
    ("data_quality", Decimal("0.08")),
)

# Tasa de ahorro (aportación planificada / ingresos estructurales): 5 % es el suelo
# desde el que se empieza a puntuar y 20 % ya es una tasa sólida.
SAVINGS_RATE_FLOOR = Decimal("0.05")
SAVINGS_RATE_TARGET = Decimal("0.20")


def active_assets(plan: FinancialPlan) -> list[Asset]:
    return list(Asset.objects.filter(user=plan.user, is_active=True))


def active_liabilities(plan: FinancialPlan) -> list[Liability]:
    return list(Liability.objects.filter(user=plan.user, is_active=True))


def structural_operating_expense(plan: FinancialPlan) -> Decimal:
    return expense_buckets(annual_expense_entries(plan)).operating


def temporary_commitment_expense(plan: FinancialPlan) -> Decimal:
    return expense_buckets(annual_expense_entries(plan)).temporary_commitment


def committed_recovery_year(
    *, plan: FinancialPlan, operating_surplus: Decimal, start_year: int
) -> int | None:
    """Primer año fiscal (>= start_year) en que el superávit comprometido vuelve
    a ser >= 0 según van venciendo los compromisos temporales.

    En euros de hoy, sin inflación: es una clasificación del esfuerzo, no una
    proyección. Un compromiso con `term_end_year = Y` sigue activo durante `Y` y
    desaparece en `Y+1`; los de `term_end_year` nulo se tratan como indefinidos.
    Devuelve `None` si la base operativa no cubre lo permanente (nunca recupera
    estructuralmente) o si no recupera dentro del horizonte.
    """
    if operating_surplus < 0:
        return None
    commitments = list(
        annual_expense_entries(plan)
        .filter(cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT)
        .values_list("amount_annual", "term_end_year")
    )
    for year in range(start_year, start_year + 21):
        active = sum(
            (Decimal(amount) for amount, end in commitments if end is None or end >= year),
            Decimal("0"),
        )
        if operating_surplus - active >= 0:
            return year
    return None


def temporary_commitment_breakdown(plan: FinancialPlan) -> list[dict[str, Any]]:
    """Compromisos temporales con su importe y vencimiento, del más próximo al más
    lejano. Alimenta la UI de "esfuerzo temporal" (para ver cuándo se libera cada uno)."""
    rows = annual_expense_entries(plan).filter(
        cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT
    )
    breakdown = [
        {
            "name": row.name,
            "amount": money(Decimal(row.amount_annual)),
            "end_year": row.term_end_year,
            "end_month": row.term_end_month,
        }
        for row in rows
    ]
    # Sin fin conocido va al final; dentro del año, por mes.
    breakdown.sort(
        key=lambda item: (
            item["end_year"] if item["end_year"] is not None else 9999,
            item["end_month"] if item["end_month"] is not None else 12,
        )
    )
    return breakdown


def asset_amount(asset: Asset) -> Decimal:
    """Valor efectivo del activo (contabilidad, posiciones e histórico), el mismo que
    usa la clasificación del plan. Leer `asset.amount` en crudo dejaba a cero toda la
    cartera de inversión de quien la lleva por posiciones: el patrimonio del
    diagnóstico no cuadraba con el de Patrimonio y la iliquidez salía inflada."""
    return max(get_effective_asset_amount(asset=asset), Decimal("0"))


def liability_amount(liability: Liability) -> Decimal:
    return max(get_effective_liability_amount(liability=liability), Decimal("0"))


def asset_liquidity_metrics(assets: list[Asset]) -> dict[str, Any]:
    amounts = {asset.id: asset_amount(asset) for asset in assets}
    assets_value = sum(amounts.values(), Decimal("0"))
    by_category: dict[str, Decimal] = {}
    illiquid = Decimal("0")
    emergency_liquid = Decimal("0")
    immediate_liquid = Decimal("0")

    for asset in assets:
        amount = amounts[asset.id]
        if amount <= 0:
            continue
        by_category[asset.category] = by_category.get(asset.category, Decimal("0")) + amount
        illiquid_by_category = asset.category in {
            Asset.Category.REAL_ESTATE,
            Asset.Category.FURNISHINGS,
            Asset.Category.OTHER,
        }
        illiquid_by_investment = (
            asset.category == Asset.Category.INVESTMENTS
            and asset.subcategory in ILLIQUID_INVESTMENT_SUBCATEGORIES
        )
        illiquid_by_cash_deposit = (
            asset.category == Asset.Category.CASH
            and asset.subcategory == Asset.Subcategory.OTHER
            and Decimal(asset.annual_interest_tae or 0) > 0
        )
        if illiquid_by_category or illiquid_by_investment or illiquid_by_cash_deposit:
            illiquid += amount

        if asset.category == Asset.Category.CASH:
            emergency_liquid += amount
            immediate_liquid += amount
        elif (
            asset.category == Asset.Category.INVESTMENTS
            and asset.subcategory in EMERGENCY_INVESTMENT_SUBCATEGORIES
        ):
            emergency_liquid += amount

    category_values = [value for value in by_category.values() if value > 0]
    top_share = (
        max(category_values) / assets_value if assets_value > 0 and category_values else None
    )
    diversification_index = None
    if assets_value > 0 and category_values:
        hhi = sum(((value / assets_value) ** 2 for value in category_values), Decimal("0"))
        diversification_index = clamp(
            (Decimal("1") - hhi) / (Decimal("1") - Decimal("0.2")),
            Decimal("0"),
            Decimal("1"),
        )

    return {
        "assets_value": assets_value,
        "illiquid_assets_value": illiquid,
        "illiquid_assets_share": illiquid / assets_value if assets_value > 0 else None,
        "emergency_liquid_assets_value": emergency_liquid,
        "immediate_liquidity_assets_value": immediate_liquid,
        "emergency_liquidity_to_assets": emergency_liquid / assets_value
        if assets_value > 0
        else None,
        "immediate_liquidity_share_within_emergency": (
            immediate_liquid / emergency_liquid if emergency_liquid > 0 else None
        ),
        "top_asset_share": top_share,
        "diversification_index": diversification_index,
    }


def debt_metrics(plan: FinancialPlan, liabilities: list[Liability]) -> dict[str, Any]:
    amounts = {liability.id: liability_amount(liability) for liability in liabilities}
    liabilities_value = sum(amounts.values(), Decimal("0"))
    unbacked = sum(
        (amounts[liability.id] for liability in liabilities if not liability.is_asset_backed),
        Decimal("0"),
    )
    known_rate_rows = [row for row in liabilities if row.annual_interest_tae is not None]
    weighted_tae = None
    if known_rate_rows:
        denominator = sum((amounts[row.id] for row in known_rate_rows), Decimal("0"))
        if denominator > 0:
            weighted_tae = (
                sum(
                    (
                        amounts[row.id] * Decimal(row.annual_interest_tae or 0)
                        for row in known_rate_rows
                    ),
                    Decimal("0"),
                )
                / denominator
            )
    max_tae = (
        max(Decimal(row.annual_interest_tae or 0) for row in known_rate_rows)
        if known_rate_rows
        else None
    )
    high_cost_threshold = Decimal("8")
    high_cost_debt = sum(
        (
            amounts[row.id]
            for row in liabilities
            if row.annual_interest_tae is not None
            and Decimal(row.annual_interest_tae) >= high_cost_threshold
        ),
        Decimal("0"),
    )
    recurrent_income = structural_income(plan)
    monthly_income = recurrent_income / Decimal("12") if recurrent_income > 0 else None
    monthly_debt_payment = sum(
        (
            Decimal(entry.amount_annual) / Decimal("12")
            for entry in annual_expense_entries(plan).filter(
                cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT
            )
        ),
        Decimal("0"),
    )
    debt_payment_to_income = (
        monthly_debt_payment / monthly_income
        if monthly_income is not None and monthly_income > 0 and monthly_debt_payment > 0
        else None
    )
    top_liability_share = (
        max(amounts.values(), default=Decimal("0")) / liabilities_value
        if liabilities_value > 0
        else None
    )
    return {
        "liabilities_value": liabilities_value,
        "unbacked_debt_value": unbacked,
        "unbacked_debt_to_liabilities": unbacked / liabilities_value
        if liabilities_value > 0
        else None,
        "weighted_liability_tae_pct": weighted_tae,
        "max_liability_tae_pct": max_tae,
        "high_cost_debt_value": high_cost_debt,
        "high_cost_debt_share": high_cost_debt / liabilities_value
        if liabilities_value > 0
        else None,
        "debt_payment_to_income": debt_payment_to_income,
        "top_liability_share": top_liability_share,
    }


class FoundationService:
    def calculate(self, *, plan: FinancialPlan) -> dict[str, Any]:
        assets = active_assets(plan)
        liabilities = active_liabilities(plan)
        asset_metrics = asset_liquidity_metrics(assets)
        debt = debt_metrics(plan, liabilities)

        annual_income = structural_income(plan)
        operating_expense = structural_operating_expense(plan)
        commitment_expense = temporary_commitment_expense(plan)
        monthly_operating_expense = (
            operating_expense / Decimal("12") if operating_expense > 0 else None
        )
        committed_expense = operating_expense + commitment_expense
        monthly_committed_expense = (
            committed_expense / Decimal("12") if committed_expense > 0 else None
        )
        operating_surplus = annual_income - operating_expense
        committed_surplus = annual_income - committed_expense
        planned_contribution = planned_contribution_amount(plan=plan)

        # Tercera capa: distinguir esfuerzo temporal de déficit estructural.
        start_year = plan_fiscal_year(plan)
        recovery_year = committed_recovery_year(
            plan=plan, operating_surplus=operating_surplus, start_year=start_year
        )
        if committed_surplus >= 0:
            committed_status = "healthy"
        elif (
            operating_surplus >= 0
            and recovery_year is not None
            and recovery_year <= start_year + TRANSIENT_SQUEEZE_MAX_YEARS
        ):
            committed_status = "transient"
        else:
            committed_status = "structural"

        emergency_months_base = (
            asset_metrics["emergency_liquid_assets_value"] / monthly_operating_expense
            if monthly_operating_expense is not None and monthly_operating_expense > 0
            else None
        )
        emergency_months_committed = (
            asset_metrics["emergency_liquid_assets_value"] / monthly_committed_expense
            if monthly_committed_expense is not None and monthly_committed_expense > 0
            else None
        )

        cash_flow_score = weighted_score(
            [
                (
                    score_decreasing(
                        operating_expense / annual_income if annual_income > 0 else None,
                        Decimal("0.5"),
                        Decimal("1"),
                    ),
                    Decimal("0.45"),
                ),
                (
                    score_decreasing(
                        committed_expense / annual_income if annual_income > 0 else None,
                        Decimal("0.65"),
                        Decimal("1.05"),
                    ),
                    Decimal("0.35"),
                ),
                (
                    score_increasing(
                        operating_surplus / annual_income if annual_income > 0 else None,
                        Decimal("-0.2"),
                        Decimal("0.2"),
                    ),
                    Decimal("0.20"),
                ),
            ]
        )
        # El cimiento mide una sola cosa: cuántos meses de gasto operativo cubre tu
        # colchón frente a su objetivo. Antes promediaba además la cobertura *con
        # compromisos* (que ya penaliza el flujo de caja) y el peso del colchón sobre
        # el patrimonio total (que es diversificación, y vive en salud patrimonial):
        # con 5,5 de 6 meses objetivo la nota bajaba a D. La cobertura comprometida
        # sigue publicándose como dato del desglose.
        emergency_score = score_increasing(
            emergency_months_base, EMERGENCY_FLOOR_MONTHS, EMERGENCY_TARGET_MONTHS
        )

        debt_score = weighted_score(
            [
                (
                    score_decreasing(
                        debt["weighted_liability_tae_pct"], Decimal("0.5"), Decimal("10")
                    ),
                    Decimal("0.35"),
                ),
                (
                    score_decreasing(
                        debt["unbacked_debt_to_liabilities"], Decimal("0.01"), Decimal("0.5")
                    ),
                    Decimal("0.35"),
                ),
                (
                    score_decreasing(debt["high_cost_debt_share"], Decimal("0.05"), Decimal("0.6")),
                    Decimal("0.30"),
                ),
            ]
        )
        net_worth_health_score = weighted_score(
            [
                (
                    score_decreasing(
                        debt["unbacked_debt_value"] / asset_metrics["assets_value"]
                        if asset_metrics["assets_value"] > 0
                        else None,
                        Decimal("0.05"),
                        Decimal("0.35"),
                    ),
                    Decimal("0.4"),
                ),
                (
                    score_decreasing(
                        asset_metrics["illiquid_assets_share"], Decimal("0.25"), Decimal("0.8")
                    ),
                    Decimal("0.3"),
                ),
                (
                    score_decreasing(
                        asset_metrics["top_asset_share"], Decimal("0.4"), Decimal("0.9")
                    ),
                    Decimal("0.3"),
                ),
            ]
        )

        # El cimiento usa la calidad real del motor (la misma que gradúa la
        # proyección), no un checklist propio: los 4 flags anteriores daban
        # 100/100 a un plan sin contabilidad ni pasivos ("todas las TAE
        # completas" se cumplía por vacío con cero deudas).
        quality = DataQualityService().evaluate(user=plan.user)
        quality_flags = quality.factors
        quality_score = (
            sum(1 for value in quality_flags.values() if value) / len(quality_flags) * 100
        )

        # Tasa de ahorro: la aportación planificada frente a los ingresos. Es el KPI
        # que faltaba puntuar del bloque (antes solo mostraba el importe), y el que
        # explica si el plan avanza al ritmo que hace falta.
        savings_rate = planned_contribution / annual_income if annual_income > 0 else None
        contribution_score = score_increasing(savings_rate, SAVINGS_RATE_FLOOR, SAVINGS_RATE_TARGET)

        blocks: dict[str, Any] = {
            "cash_flow": {
                **graded(cash_flow_score),
                "structural_annual_income": money(annual_income),
                "structural_operating_expense": money(operating_expense),
                "temporary_commitment_expense": money(commitment_expense),
                "operating_surplus": money(operating_surplus),
                "committed_surplus": money(committed_surplus),
                "operating_surplus_ratio": ratio(
                    operating_surplus / annual_income if annual_income > 0 else None
                ),
                # healthy (>=0) | transient (esfuerzo que vence pronto sobre base
                # operativa sana) | structural (déficit real).
                "committed_status": committed_status,
                "committed_recovery_year": recovery_year,
                "temporary_commitments": temporary_commitment_breakdown(plan),
            },
            "emergency_fund": {
                **graded(emergency_score),
                "eligible_liquidity": money(asset_metrics["emergency_liquid_assets_value"]),
                "coverage_months_base": ratio(emergency_months_base),
                "coverage_months_committed": ratio(emergency_months_committed),
                "target_months": ratio(EMERGENCY_TARGET_MONTHS),
            },
            "debt": {
                **graded(debt_score),
                "total_debt": money(debt["liabilities_value"]),
                "unbacked_debt": money(debt["unbacked_debt_value"]),
                "high_cost_debt": money(debt["high_cost_debt_value"]),
                "weighted_tae_pct": ratio(debt["weighted_liability_tae_pct"]),
                "debt_payment_to_income": ratio(debt["debt_payment_to_income"]),
            },
            "net_worth_health": {
                **graded(net_worth_health_score),
                "assets_value": money(asset_metrics["assets_value"]),
                "illiquid_assets_share": ratio(asset_metrics["illiquid_assets_share"]),
                "top_asset_share": ratio(asset_metrics["top_asset_share"]),
                "diversification_index": ratio(asset_metrics["diversification_index"]),
            },
            "planned_contribution": {
                **graded(contribution_score),
                "annual_amount": money(planned_contribution),
                "monthly_amount": money(planned_contribution / Decimal("12")),
                "savings_rate": ratio(savings_rate),
                "target_savings_rate": ratio(SAVINGS_RATE_TARGET),
            },
            "data_quality": {
                **graded(Decimal(str(quality_score))),
                "flags": quality_flags,
            },
        }

        # Nota global del bloque: media ponderada de los seis cimientos, con la misma
        # escala, para poder titular "Salud financiera · C" en vez de contar cuántos
        # están en ámbar.
        overall_score = weighted_score(
            [(Decimal(blocks[key]["score"]), weight) for key, weight in FOUNDATION_WEIGHTS]
        )

        return {
            "period": "current",
            "overall": graded(overall_score),
            **blocks,
        }
