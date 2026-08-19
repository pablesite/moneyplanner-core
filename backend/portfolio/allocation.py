"""Politica de asignacion: donde quieres estar, frente a donde estas.

La cartera sabia decir donde estas. Esto anade la otra mitad —la politica— y su
diferencia, que es lo unico que convierte el seguimiento en una decision.

El ambito es una `Ownership`, no un miembro. "Lo de Pablo", "lo de Lucas" y "lo
compartido al 50%" son mandatos distintos, con horizontes distintos: una politica unica
para los tres no significaria nada. Filtrar por miembro responde a otra pregunta —que
parte economica te toca de cada posicion— y sigue siendo el filtro de titularidad.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from memberships.models import Ownership

from .models import AllocationStrategy, AllocationTarget, Portfolio, PortfolioPosition
from .performance import (
    PerformanceContext,
    _position_value_base,
    load_performance_context,
    timeline_context_start,
)

ZERO = Decimal("0")


@dataclass(frozen=True)
class ScopeSlice:
    """Lo que una posicion aporta a una clase dentro del ambito."""

    position: PortfolioPosition
    asset_class: str
    value: Decimal


def resolve_strategy(
    *, portfolio: Portfolio, ownership: Ownership, on_date: date
) -> AllocationStrategy | None:
    """La version vigente en esa fecha, que no tiene por que ser la ultima escrita."""
    return (
        portfolio.allocation_strategies.filter(ownership=ownership, effective_from__lte=on_date)
        .order_by("-effective_from", "-id")
        .first()
    )


def _ownership_at(context: PerformanceContext, position_id: int, target: date):
    return next(
        (
            row
            for row in context.ownership_periods.get(position_id, [])
            if row.start_date <= target and (row.end_date is None or row.end_date >= target)
        ),
        None,
    )


def positions_in_scope(
    *, context: PerformanceContext, ownership_id: int, on_date: date
) -> list[PortfolioPosition]:
    """Las posiciones cuya titularidad vigente en esa fecha es la del ambito.

    Se lee del tramo vigente, no del ultimo escrito: si algo dejo de ser compartido en
    marzo, en febrero seguia siendolo y la politica de febrero le aplicaba.
    """
    selected = []
    for position in context.positions:
        if position.status == PortfolioPosition.Status.ARCHIVED:
            # Una posicion archivada esta fuera de la cartera: no recibe aportacion ni
            # arrastra la desviacion hacia un objetivo que ya no se persigue.
            continue
        period = _ownership_at(context, position.id, on_date)
        if period is not None and period.ownership_id == ownership_id:
            selected.append(position)
    return selected


def scope_slices(
    *, context: PerformanceContext, positions: list[PortfolioPosition], on_date: date
) -> list[ScopeSlice]:
    """Valor de cada posicion repartido por clase, aplicando el look-through si lo tiene."""
    slices: list[ScopeSlice] = []
    for position in positions:
        value, _ = _position_value_base(
            context=context, position=position, target=on_date, member_id=None
        )
        if value is None:
            continue
        breakdown = list(position.class_breakdown.all())
        if not breakdown:
            slices.append(ScopeSlice(position, position.effective_asset_class, value))
            continue
        for row in breakdown:
            slices.append(
                ScopeSlice(position, row.asset_class, value * row.percent / Decimal("100"))
            )
    return slices


def _band_state(actual: Decimal, target: AllocationTarget | None) -> str:
    if target is None:
        return "unplanned"
    if target.min_percent is not None and actual < target.min_percent:
        return "below"
    if target.max_percent is not None and actual > target.max_percent:
        return "above"
    return "within"


def build_allocation(
    *,
    portfolio: Portfolio,
    ownership: Ownership,
    on_date: date,
    context: PerformanceContext | None = None,
) -> dict[str, Any]:
    """Actual frente a objetivo para un ambito, por clase y por posicion.

    Una clase sin objetivo aparece igualmente como `unplanned`: esconder lo que tienes y
    no habias planeado es justo lo contrario de lo que hace falta para decidir.
    """
    context = context or load_performance_context(
        portfolio=portfolio,
        start_date=timeline_context_start(portfolio=portfolio, start_date=on_date),
        end_date=on_date,
    )
    strategy = resolve_strategy(portfolio=portfolio, ownership=ownership, on_date=on_date)
    positions = positions_in_scope(context=context, ownership_id=ownership.id, on_date=on_date)
    slices = scope_slices(context=context, positions=positions, on_date=on_date)
    total = sum((row.value for row in slices), ZERO)

    targets_by_class: dict[str, AllocationTarget] = {}
    targets_by_position: dict[int, AllocationTarget] = {}
    if strategy is not None:
        for target in strategy.targets.all():
            if target.asset_class:
                targets_by_class[target.asset_class] = target
            elif target.position_id:
                targets_by_position[target.position_id] = target

    by_class: dict[str, Decimal] = {}
    by_position: dict[int, Decimal] = {}
    for row in slices:
        by_class[row.asset_class] = by_class.get(row.asset_class, ZERO) + row.value
        by_position[row.position.id] = by_position.get(row.position.id, ZERO) + row.value

    def rows(current: dict, targets: dict, label: str) -> list[dict[str, Any]]:
        keys = list(current) + [key for key in targets if key not in current]
        result = []
        for key in keys:
            value = current.get(key, ZERO)
            share = (value / total * Decimal("100")) if total else ZERO
            target = targets.get(key)
            ideal = (target.target_percent / Decimal("100") * total) if target else None
            result.append(
                {
                    label: key,
                    "value": str(value.quantize(Decimal("0.01"))),
                    "actual_percent": str(share.quantize(Decimal("0.01"))),
                    "target_percent": str(target.target_percent) if target else None,
                    "min_percent": str(target.min_percent)
                    if target and target.min_percent is not None
                    else None,
                    "max_percent": str(target.max_percent)
                    if target and target.max_percent is not None
                    else None,
                    "drift_value": str((ideal - value).quantize(Decimal("0.01")))
                    if ideal is not None
                    else None,
                    "band": _band_state(share, target),
                }
            )
        return sorted(result, key=lambda row: Decimal(row["value"]), reverse=True)

    return {
        "ownership_id": ownership.id,
        "on_date": on_date.isoformat(),
        "currency": portfolio.base_currency,
        "strategy": (
            {
                "id": strategy.id,
                "effective_from": strategy.effective_from.isoformat(),
                "note": strategy.note,
                "target_total": str(
                    sum(
                        (row.target_percent for row in strategy.targets.all() if row.asset_class),
                        ZERO,
                    )
                ),
            }
            if strategy is not None
            else None
        ),
        "total_value": str(total.quantize(Decimal("0.01"))),
        "position_count": len(positions),
        "by_class": rows(by_class, targets_by_class, "asset_class"),
        "by_position": rows(by_position, targets_by_position, "position_id"),
    }
