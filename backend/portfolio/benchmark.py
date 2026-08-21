"""Benchmark estrategico y lectura de riesgo de un ambito de la cartera.

El benchmark principal **no es un indice**: es la propia politica escrita. Cada mes se
toma la version vigente en esa fecha —no la de hoy, que juzgaria marzo con lo que se
decidio en julio— y se compone la rentabilidad que habrian dado sus pesos objetivo usando
el comportamiento real de cada clase de la cartera. Comparado con lo que la cartera hizo
de verdad, el exceso responde exactamente a una pregunta: **desviarse del plan, ayudo o
no**. Un indice global respondería a otra —si merecio la pena elegir productos— y por eso
queda como secundario y opcional.

La liquidez queda fuera de los dos lados. La serie de la cartera se calcula sobre las
posiciones del ambito, y el efectivo de contenedor no es de ninguna clase, asi que
incluirlo solo en el benchmark compararia dos cosas distintas. Los pesos de las clases
restantes se renormalizan y se declara que se ha hecho.

Cuando una clase con objetivo no tiene rentabilidad calculable ese mes, el mes entero se
declara sin dato en vez de repartir su peso entre las demas: repartirlo produciria una
cifra continua sobre datos que no existen, que es justo lo que este modulo no debe hacer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings

from memberships.models import Ownership

from .allocation import positions_in_scope, resolve_strategy
from .models import Portfolio
from .performance import (
    PerformanceContext,
    build_portfolio_performance,
    load_performance_context,
    timeline_context_start,
    timeline_dates,
)
from .risk import (
    PeriodReturn,
    advanced_metric_interfaces,
    annualized_return,
    best_and_worst,
    longest_complete_run,
    max_drawdown,
    sharpe,
    volatility,
)

ZERO = Decimal("0")
ONE = Decimal("1")
CASH_CLASS = "cash"
DEFAULT_RISK_FREE_RATE = Decimal("0.02")


def resolve_risk_free_rate() -> Decimal:
    """La tasa sin riesgo anual con la que se calcula el Sharpe.

    Configurable por entorno (`PORTFOLIO_RISK_FREE_RATE`, anual y en tanto por uno) porque
    no es una constante del mundo: el 2% por defecto describe una letra a corto plazo en
    euros de los ultimos anos, y quien viva otra realidad monetaria necesita cambiarla sin
    tocar codigo. Se publica junto a cada cifra que la usa, que es la unica forma de que
    un Sharpe se pueda comparar con otro.
    """
    raw = getattr(settings, "PORTFOLIO_RISK_FREE_RATE", None)
    if raw is None:
        return DEFAULT_RISK_FREE_RATE
    try:
        return Decimal(str(raw))
    except (ArithmeticError, ValueError):
        return DEFAULT_RISK_FREE_RATE


def _is_month_end(day: date) -> bool:
    return (day + timedelta(days=1)).month != day.month


def monthly_boundaries(start_date: date, end_date: date) -> list[date]:
    """Los cierres de mes del periodo, sin los tramos parciales de los extremos.

    Un tramo de nueve dias no es un mes, y tratarlo como tal deforma cualquier estadistica
    que despues se anualice. El periodo elegido por el usuario sigue mandando en el valor
    y la rentabilidad del resumen; aqui solo se recortan los bordes.
    """
    return [row for row in timeline_dates(start_date, end_date) if _is_month_end(row)]


@dataclass(frozen=True)
class SeriesPoint:
    label: str
    start: date
    end: date
    portfolio: Decimal | None
    benchmark: Decimal | None
    reason: str = ""


def _scope_return(
    *,
    portfolio: Portfolio,
    context: PerformanceContext,
    scope_ids: set[int],
    start_date: date,
    end_date: date,
    member_id: int | None,
) -> Decimal | None:
    if not scope_ids:
        return None
    block = build_portfolio_performance(
        portfolio=portfolio,
        start_date=start_date,
        end_date=end_date,
        member_id=member_id,
        context=context,
        scope_ids=scope_ids,
    )
    raw = block["return"]["twr"]
    return None if raw is None else Decimal(raw)


def _class_weights(strategy) -> dict[str, Decimal]:
    """Los pesos objetivo por clase, sin liquidez y renormalizados a 1."""
    weights = {
        target.asset_class: target.target_percent
        for target in strategy.targets.all()
        if target.asset_class and target.asset_class != CASH_CLASS and target.target_percent > 0
    }
    total = sum(weights.values(), ZERO)
    if total <= ZERO:
        return {}
    return {key: value / total for key, value in weights.items()}


def build_benchmark_series(
    *,
    portfolio: Portfolio,
    ownership: Ownership,
    start_date: date,
    end_date: date,
    member_id: int | None = None,
    context: PerformanceContext | None = None,
) -> dict[str, Any]:
    """Serie mensual de cartera y benchmark estrategico, mas su exceso acumulado."""
    context = context or load_performance_context(
        portfolio=portfolio,
        start_date=timeline_context_start(portfolio=portfolio, start_date=start_date),
        end_date=end_date,
    )
    boundaries = monthly_boundaries(start_date, end_date)
    if len(boundaries) < 2:
        return {
            "status": "insufficient",
            "reason": "not_enough_full_months",
            "months": 0,
            "points": [],
        }

    points: list[SeriesPoint] = []
    unreachable: set[str] = set()
    renormalized_cash = False
    for previous, current in zip(boundaries, boundaries[1:], strict=False):
        label = current.strftime("%Y-%m")
        positions = positions_in_scope(context=context, ownership_id=ownership.id, on_date=current)
        scope_ids = {position.id for position in positions}
        portfolio_return = _scope_return(
            portfolio=portfolio,
            context=context,
            scope_ids=scope_ids,
            start_date=previous,
            end_date=current,
            member_id=member_id,
        )
        # Un cierre mensual solo tiene una politica comparable: la vigente cuando empezo
        # el intervalo. Una version creada a mitad de mes no puede reescribir el objetivo
        # contra el que se juzgan los dias anteriores; entra en el siguiente mes completo.
        strategy = resolve_strategy(
            portfolio=portfolio,
            ownership=ownership,
            on_date=previous + date.resolution,
        )
        if strategy is None:
            points.append(
                SeriesPoint(label, previous, current, portfolio_return, None, "no_strategy")
            )
            continue
        if any(
            target.asset_class == CASH_CLASS and target.target_percent > 0
            for target in strategy.targets.all()
        ):
            renormalized_cash = True
        weights = _class_weights(strategy)
        if not weights:
            points.append(
                SeriesPoint(label, previous, current, portfolio_return, None, "no_targets")
            )
            continue

        by_class: dict[str, set[int]] = {}
        for position in positions:
            by_class.setdefault(position.effective_asset_class, set()).add(position.id)

        weighted = ZERO
        covered_weight = ZERO
        missing = False
        for asset_class, weight in weights.items():
            members = by_class.get(asset_class)
            if not members:
                # Una clase planeada sin ningun producto no puede aportar rentabilidad. No
                # invalida el mes: se dice y su peso se reparte entre las que si existen.
                unreachable.add(asset_class)
                continue
            class_return = _scope_return(
                portfolio=portfolio,
                context=context,
                scope_ids=members,
                start_date=previous,
                end_date=current,
                member_id=member_id,
            )
            if class_return is None:
                missing = True
                break
            weighted += weight * class_return
            covered_weight += weight
        if missing or covered_weight <= ZERO:
            points.append(
                SeriesPoint(
                    label,
                    previous,
                    current,
                    portfolio_return,
                    None,
                    "class_return_unavailable" if missing else "no_reachable_class",
                )
            )
            continue
        points.append(
            SeriesPoint(label, previous, current, portfolio_return, weighted / covered_weight)
        )

    return {
        "status": "ok",
        "months": len(points),
        "points": points,
        "unreachable_classes": sorted(unreachable),
        "cash_excluded": renormalized_cash,
    }


def _chain(values: list[Decimal | None]) -> Decimal | None:
    if not values or any(row is None for row in values):
        return None
    index = ONE
    for value in values:
        assert value is not None
        index *= ONE + value
    return index - ONE


def _secondary_benchmark(
    *,
    portfolio: Portfolio,
    ownership: Ownership,
    boundaries: list[date],
    end_date: date,
) -> dict[str, Any]:
    """El indice de referencia, si el ambito declaro uno y tiene precios utilizables."""
    strategy = resolve_strategy(portfolio=portfolio, ownership=ownership, on_date=end_date)
    instrument = getattr(strategy, "benchmark_instrument", None) if strategy else None
    if instrument is None:
        return {"status": "unavailable", "reason": "not_configured", "instrument": None}
    detail = {"id": instrument.id, "name": instrument.name}
    if instrument.quote_currency.upper() != portfolio.base_currency.upper():
        # Convertirlo exigiria una serie FX diaria del indice; sin ella, el cambio de
        # divisa se colaria dentro de la rentabilidad del indice como si fuera suya.
        return {"status": "unavailable", "reason": "currency_mismatch", "instrument": detail}
    prices = {
        row.price_date: row.close
        for row in instrument.prices.filter(
            price_date__gte=boundaries[0], price_date__lte=boundaries[-1]
        )
    }
    raw_closes = [prices.get(row) for row in boundaries]
    if any(row is None or row <= ZERO for row in raw_closes):
        return {"status": "unavailable", "reason": "missing_prices", "instrument": detail}
    closes: list[Decimal] = [row for row in raw_closes if row is not None]
    returns: list[Decimal | None] = [
        (closes[index] / closes[index - 1]) - ONE for index in range(1, len(closes))
    ]
    cumulative = _chain(returns)
    return {
        "status": "available",
        "instrument": detail,
        "cumulative_return": None if cumulative is None else str(cumulative),
    }


def build_portfolio_benchmark(
    *,
    portfolio: Portfolio,
    ownership: Ownership,
    start_date: date,
    end_date: date,
    member_id: int | None = None,
    context: PerformanceContext | None = None,
) -> dict[str, Any]:
    """Cartera contra su propia politica, mes a mes y en acumulado."""
    series = build_benchmark_series(
        portfolio=portfolio,
        ownership=ownership,
        start_date=start_date,
        end_date=end_date,
        member_id=member_id,
        context=context,
    )
    base = {
        "ownership_id": ownership.id,
        "currency": portfolio.base_currency,
        "period": {"from": start_date.isoformat(), "to": end_date.isoformat()},
        "calendar": {"frequency": "monthly", "boundaries": "month_end"},
    }
    if series["status"] != "ok":
        return {
            **base,
            "status": "insufficient",
            "reason": series["reason"],
            "months": series["months"],
            "points": [],
            "portfolio_return": None,
            "benchmark_return": None,
            "excess_return": None,
            "secondary": {"status": "unavailable", "reason": "not_configured", "instrument": None},
        }
    points: list[SeriesPoint] = series["points"]
    portfolio_total = _chain([row.portfolio for row in points])
    benchmark_total = _chain([row.benchmark for row in points])
    excess = (
        portfolio_total - benchmark_total
        if portfolio_total is not None and benchmark_total is not None
        else None
    )
    covered = sum(1 for row in points if row.benchmark is not None)
    return {
        **base,
        "status": "ok" if benchmark_total is not None else "insufficient",
        "reason": "" if benchmark_total is not None else "months_without_benchmark",
        "months": len(points),
        "months_with_benchmark": covered,
        "unreachable_classes": series["unreachable_classes"],
        "cash_excluded": series["cash_excluded"],
        "portfolio_return": None if portfolio_total is None else str(portfolio_total),
        "benchmark_return": None if benchmark_total is None else str(benchmark_total),
        "excess_return": None if excess is None else str(excess),
        "points": [
            {
                "period": row.label,
                "from": row.start.isoformat(),
                "to": row.end.isoformat(),
                "portfolio": None if row.portfolio is None else str(row.portfolio),
                "benchmark": None if row.benchmark is None else str(row.benchmark),
                "reason": row.reason,
            }
            for row in points
        ],
        "secondary": _secondary_benchmark(
            portfolio=portfolio,
            ownership=ownership,
            boundaries=monthly_boundaries(start_date, end_date),
            end_date=end_date,
        ),
    }


def build_portfolio_risk(
    *,
    portfolio: Portfolio,
    ownership: Ownership,
    start_date: date,
    end_date: date,
    member_id: int | None = None,
    context: PerformanceContext | None = None,
) -> dict[str, Any]:
    """Volatilidad, caida maxima, mejor/peor mes y Sharpe del ambito, con su cobertura."""
    series = build_benchmark_series(
        portfolio=portfolio,
        ownership=ownership,
        start_date=start_date,
        end_date=end_date,
        member_id=member_id,
        context=context,
    )
    risk_free = resolve_risk_free_rate()
    base = {
        "ownership_id": ownership.id,
        "currency": portfolio.base_currency,
        "period": {"from": start_date.isoformat(), "to": end_date.isoformat()},
        "calendar": {"frequency": "monthly", "boundaries": "month_end"},
        "risk_free_rate": str(risk_free),
        "advanced": advanced_metric_interfaces(),
    }
    if series["status"] != "ok":
        empty = {"status": "insufficient", "value": None, "reason": series["reason"]}
        return {
            **base,
            "observations": 0,
            "coverage": {
                "months_in_period": 0,
                "months_used": 0,
                "window": {"from": None, "to": None},
                "months_without_data": [],
            },
            "annualized_return": dict(empty),
            "volatility": dict(empty),
            "max_drawdown": dict(empty),
            "best_period": dict(empty),
            "worst_period": dict(empty),
            "sharpe": dict(empty),
        }
    returns = [PeriodReturn(row.label, row.portfolio) for row in series["points"]]
    # Las metricas se calculan sobre el tramo contiguo mas largo, no sobre la serie con
    # huecos: encadenar los dos lados de un mes que falta trataria dos meses como uno.
    # Mejor y peor mes son la excepcion —son lecturas puntuales, no encadenadas—, asi que
    # leen todo lo que haya.
    run = longest_complete_run(returns)
    extremes = best_and_worst(returns)
    gaps = [row.label for row in returns if row.value is None]
    return {
        **base,
        "observations": len(run),
        "coverage": {
            "months_in_period": len(returns),
            "months_used": len(run),
            "window": (
                {"from": run[0].label, "to": run[-1].label} if run else {"from": None, "to": None}
            ),
            "months_without_data": gaps,
        },
        "annualized_return": annualized_return(run),
        "volatility": volatility(run),
        "max_drawdown": max_drawdown(run),
        "best_period": extremes["best"],
        "worst_period": extremes["worst"],
        "sharpe": sharpe(series=run, risk_free_rate=risk_free),
    }
