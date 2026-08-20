"""Exposicion real de la cartera: donde esta metido el dinero, no en que envoltorio.

La clase de activo contesta de que depende que una posicion suba o baje. Esto contesta
la pregunta siguiente, que es la que decide si estas diversificado: dentro de tu renta
variable, cuanto pesa Norteamerica; cuanto de tu cartera depende de la tecnologia; y
cuanto se solapan dos productos que compraste pensando que eran cosas distintas.

Los pesos los declara el usuario desde la ficha del fondo. Ningun proveedor los regala a
partir del ISIN, cambian despacio y son una docena de numeros por posicion. Lo que aporta
el sistema es sumarlos bien y **declarar lo que no sabe**: una exposicion calculada sobre
media cartera y presentada como si fuera entera miente mas que no ensenar nada.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from .models import PositionExposure, Portfolio
from .performance import (
    PerformanceContext,
    _position_value_base,
    load_performance_context,
    timeline_context_start,
)

ZERO = Decimal("0")
CENT = Decimal("0.01")
# Por debajo de esto la exposicion no se publica como si describiera la cartera: con
# menos de cuatro quintas partes declaradas, el reparto que salga es el de otra cartera.
READY_COVERAGE = Decimal("80")
# Dos productos por debajo de esto comparten lo que comparte cualquier par: no es una
# senal, es ruido.
OVERLAP_FLOOR = Decimal("25")
# El envoltorio no es riesgo compartido: dos ETFs coinciden en el 100% de su vehiculo por
# definicion, y publicarlo llenaria la lista de hallazgos que no dicen nada.
RISK_DIMENSIONS: tuple[str, ...] = ("geography", "sector")


def _values(*, context: PerformanceContext, on_date: date) -> dict[int, Decimal]:
    values: dict[int, Decimal] = {}
    for position in context.positions:
        value, _ = _position_value_base(
            context=context, position=position, target=on_date, member_id=None
        )
        if value is not None and value > 0:
            values[position.id] = value
    return values


def _weights(rows: list[PositionExposure]) -> dict[str, Decimal]:
    return {row.bucket: row.percent for row in rows}


def overlap_percent(left: dict[str, Decimal], right: dict[str, Decimal]) -> Decimal:
    """Cuanto comparten dos repartos: la suma de lo que coincide bucket a bucket.

    Es el area comun de las dos distribuciones. Dos fondos con el mismo reparto dan 100;
    dos que no coinciden en nada, 0. No es solapamiento por valor concreto —para eso
    harian falta las tenencias— sino por exposicion, que es la pregunta que se hace uno
    al mirar dos fondos que parecian distintos.
    """
    shared = sum((min(value, right.get(bucket, ZERO)) for bucket, value in left.items()), ZERO)
    return shared.quantize(CENT)


def build_exposure(
    *,
    portfolio: Portfolio,
    on_date: date,
    context: PerformanceContext | None = None,
    scope_ids: set[int] | None = None,
) -> dict[str, Any]:
    """Exposicion agregada de la cartera por cada dimension, con lo que no se sabe."""
    context = context or load_performance_context(
        portfolio=portfolio,
        start_date=timeline_context_start(portfolio=portfolio, start_date=on_date),
        end_date=on_date,
    )
    values = _values(context=context, on_date=on_date)
    if scope_ids is not None:
        values = {key: value for key, value in values.items() if key in scope_ids}
    total = sum(values.values(), ZERO)
    names = {position.id: position.asset.name for position in context.positions}

    rows_by_position: dict[int, dict[str, list[PositionExposure]]] = {}
    for row in PositionExposure.objects.filter(position_id__in=list(values)):
        rows_by_position.setdefault(row.position_id, {}).setdefault(row.dimension, []).append(row)

    dimensions = []
    for dimension, label in PositionExposure.Dimension.choices:
        buckets: dict[str, Decimal] = {}
        covered = ZERO
        oldest: date | None = None
        for position_id, value in values.items():
            rows = rows_by_position.get(position_id, {}).get(dimension, [])
            if not rows:
                continue
            declared = sum((row.percent for row in rows), ZERO)
            if declared <= 0:
                continue
            # Se cuenta como cubierto lo que el usuario declaro, no la posicion entera:
            # una ficha que reparte el 90% y calla el resto no cubre ese resto.
            covered += value * min(declared, Decimal("100")) / Decimal("100")
            for row in rows:
                buckets[row.bucket] = buckets.get(row.bucket, ZERO) + value * row.percent / (
                    Decimal("100")
                )
            for row in rows:
                oldest = row.observed_on if oldest is None else min(oldest, row.observed_on)
        coverage = (covered / total * Decimal("100")) if total else ZERO
        # El reparto se calcula sobre lo cubierto, no sobre el total: si no, todo sale
        # mas pequeno de lo que es y las partes no suman cien.
        base = sum(buckets.values(), ZERO)
        dimensions.append(
            {
                "dimension": dimension,
                "label": label,
                "status": _coverage_status(coverage),
                "covered_percent": str(coverage.quantize(CENT)),
                "covered_value": str(covered.quantize(CENT)),
                "observed_from": oldest.isoformat() if oldest else None,
                "rows": sorted(
                    (
                        {
                            "bucket": bucket,
                            "value": str(value.quantize(CENT)),
                            "percent": str((value / base * Decimal("100")).quantize(CENT))
                            if base
                            else "0.00",
                        }
                        for bucket, value in buckets.items()
                    ),
                    key=lambda item: Decimal(item["percent"]),
                    reverse=True,
                ),
            }
        )

    return {
        "on_date": on_date.isoformat(),
        "currency": portfolio.base_currency,
        "total_value": str(total.quantize(CENT)),
        "position_count": len(values),
        "dimensions": dimensions,
        "concentration": _concentration(values=values, names=names, total=total),
        "overlap": _overlap(values=values, names=names, rows_by_position=rows_by_position),
    }


def _coverage_status(coverage: Decimal) -> str:
    if coverage <= 0:
        return "insufficient"
    return "ready" if coverage >= READY_COVERAGE else "partial"


def _concentration(
    *, values: dict[int, Decimal], names: dict[int, str], total: Decimal
) -> dict[str, Any]:
    """Cuanto pesa lo mas gordo, y como de repartida esta la cartera.

    El indice usa el mismo Herfindahl normalizado que la salud patrimonial de Mi Plan,
    para que las dos cifras signifiquen lo mismo en los dos sitios.
    """
    if total <= 0:
        return {
            "top_positions": [],
            "top_five_percent": "0.00",
            "diversification_index": None,
            "effective_positions": None,
        }
    ranked = sorted(values.items(), key=lambda item: item[1], reverse=True)
    hhi = sum(((value / total) ** 2 for _, value in ranked), ZERO)
    # Normalizado contra el reparto perfecto de *estas* posiciones. Con el 0,2 fijo de la
    # salud patrimonial —pensado para cinco categorias— cualquier cartera con mas de un
    # punado de posiciones saturaba en 100% y el numero dejaba de decir nada.
    floor = Decimal("1") / Decimal(len(ranked))
    index = (Decimal("1") - hhi) / (Decimal("1") - floor) if len(ranked) > 1 else ZERO
    index = max(ZERO, min(Decimal("1"), index))
    return {
        "top_positions": [
            {
                "position_id": position_id,
                "name": names.get(position_id, ""),
                "percent": str((value / total * Decimal("100")).quantize(CENT)),
            }
            for position_id, value in ranked[:5]
        ],
        "top_five_percent": str(
            (sum((value for _, value in ranked[:5]), ZERO) / total * Decimal("100")).quantize(CENT)
        ),
        "diversification_index": str(index.quantize(Decimal("0.001"))),
        # Lo mismo dicho de forma legible: a cuantas posiciones iguales equivale esta
        # cartera. Un indice normalizado dice poco; "equivale a 6,7 iguales" se entiende.
        "effective_positions": str((Decimal("1") / hhi).quantize(CENT)) if hhi > 0 else None,
    }


def _overlap(
    *,
    values: dict[int, Decimal],
    names: dict[int, str],
    rows_by_position: dict[int, dict[str, list[PositionExposure]]],
) -> list[dict[str, Any]]:
    """Pares que comparten exposicion, de mas a menos.

    Solo se publica lo que pasa del suelo: dos productos globales siempre comparten algo,
    y ensenar todos los pares convertiria una senal en una lista de la compra.
    """
    pairs: list[dict[str, Any]] = []
    ordered = sorted(values, key=lambda key: values[key], reverse=True)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            # El vehiculo queda fuera: dos ETFs comparten el 100% de su vehiculo por
            # definicion, y eso no es un solapamiento de riesgo sino de envoltorio.
            for dimension in RISK_DIMENSIONS:
                left_rows = rows_by_position.get(left, {}).get(dimension, [])
                right_rows = rows_by_position.get(right, {}).get(dimension, [])
                if not left_rows or not right_rows:
                    continue
                shared = overlap_percent(_weights(left_rows), _weights(right_rows))
                if shared < OVERLAP_FLOOR:
                    continue
                pairs.append(
                    {
                        "dimension": dimension,
                        "left_id": left,
                        "left_name": names.get(left, ""),
                        "right_id": right,
                        "right_name": names.get(right, ""),
                        "percent": str(shared),
                        # Lo que de verdad se solapa en dinero: el menor de los dos, que
                        # es cuanto de la cartera esta expuesto dos veces a lo mismo.
                        "shared_value": str(
                            (min(values[left], values[right]) * shared / Decimal("100")).quantize(
                                CENT
                            )
                        ),
                    }
                )
    return sorted(pairs, key=lambda row: Decimal(row["percent"]), reverse=True)[:12]
