"""Composición por clases compartida por las lecturas de cartera.

Una ficha parcial no reduce el patrimonio ni completa su reparto con otra fuente.
La parte desconocida conserva su valor bajo ``unclassified``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .models import Instrument, PortfolioPosition, PositionHolding

ZERO = Decimal("0")
HUNDRED = Decimal("100")
UNKNOWN = str(Instrument.AssetClass.UNCLASSIFIED)


@dataclass(frozen=True)
class ClassComposition:
    weights: dict[str, Decimal]
    source: str
    observed_on: date | None

    @property
    def covered_percent(self) -> Decimal:
        return HUNDRED - self.weights.get(UNKNOWN, ZERO)


def current_holdings(*, position_ids: set[int], on_date: date) -> dict[int, list[PositionHolding]]:
    """Última ficha no posterior a la consulta, sin mezclar sus fechas."""
    rows = PositionHolding.objects.filter(
        position_id__in=position_ids, observed_on__lte=on_date
    ).order_by("position_id", "-observed_on", "-percent", "id")
    snapshots: dict[int, date] = {}
    selected: dict[int, list[PositionHolding]] = {}
    for row in rows:
        current = snapshots.setdefault(row.position_id, row.observed_on)
        if row.observed_on == current:
            selected.setdefault(row.position_id, []).append(row)
    return selected


def class_compositions(
    *,
    positions: list[PortfolioPosition],
    on_date: date,
    holdings_by_position: dict[int, list[PositionHolding]] | None = None,
) -> dict[int, ClassComposition]:
    holdings_by_position = (
        current_holdings(position_ids={position.id for position in positions}, on_date=on_date)
        if holdings_by_position is None
        else holdings_by_position
    )
    result = {}
    for position in positions:
        holdings = holdings_by_position.get(position.id, [])
        breakdown = list(position.class_breakdown.all()) if not holdings else []
        weights: dict[str, Decimal] = {}
        if holdings:
            source, observed_on = "holdings", holdings[0].observed_on
            parts = [(row.asset_class, row.percent) for row in holdings]
        elif breakdown:
            source, observed_on = "breakdown", None
            parts = [(row.asset_class, row.percent) for row in breakdown]
        else:
            source, observed_on = "classification", None
            parts = [(position.effective_asset_class, HUNDRED)]
        for asset_class, percent in parts:
            weights[asset_class] = weights.get(asset_class, ZERO) + percent
        declared = sum(weights.values(), ZERO)
        if declared > HUNDRED or any(value < ZERO for value in weights.values()):
            # Datos inválidos escritos fuera del formulario tampoco pueden inventar valor.
            weights = {UNKNOWN: HUNDRED}
        elif declared < HUNDRED:
            weights[UNKNOWN] = weights.get(UNKNOWN, ZERO) + HUNDRED - declared
        result[position.id] = ClassComposition(
            {key: value for key, value in weights.items() if value > ZERO}, source, observed_on
        )
    return result
