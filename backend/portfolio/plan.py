"""Valor de Cartera que puede consumir Mi Plan sin duplicar activos.

Patrimonio sigue siendo la fuente de inventario: cada posicion de Cartera esta vinculada a
un Asset. Este adaptador solo sustituye el importe de ese mismo Asset cuando Cartera tiene
un cierre suficientemente fiable, y deja que Patrimonio siga siendo el respaldo si falta.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.utils import timezone

from core.services import convert_currency_detailed

from .models import Portfolio, PortfolioPosition
from .performance import (
    _position_value_base,
    _value_status,
    default_performance_period,
    load_performance_context,
    timeline_context_start,
)


USABLE_VALUE_STATUSES = {"fresh", "at_cost"}


def portfolio_plan_valuations(
    *, user, base_currency: str, on_date: date | None = None
) -> dict[str, Any]:
    """Devuelve overrides por Asset y el nivel de cobertura que los respalda.

    No devuelve ningun valor de efectivo de contenedor: ese efectivo ya existe, si procede,
    como Asset de Patrimonio. Solo se reemplazan Assets enlazados a posiciones activas.
    """
    portfolio = Portfolio.objects.filter(user=user).first()
    if portfolio is None:
        return _result(status="unavailable", on_date=on_date, total=0, usable=0, values={})

    target = on_date or timezone.localdate()
    active = list(
        PortfolioPosition.objects.filter(
            portfolio=portfolio,
            status=PortfolioPosition.Status.ACTIVE,
        ).select_related("asset")
    )
    if not active:
        return _result(status="unavailable", on_date=target, total=0, usable=0, values={})

    start_date, _ = default_performance_period(portfolio)
    context = load_performance_context(
        portfolio=portfolio,
        start_date=timeline_context_start(portfolio=portfolio, start_date=start_date),
        end_date=target,
    )
    values: dict[int, Decimal] = {}
    for position in active:
        value, native = _position_value_base(
            context=context,
            position=position,
            target=target,
            member_id=None,
        )
        value_status = _value_status(position=position, native=native, target=target)
        if value is None or value_status not in USABLE_VALUE_STATUSES:
            continue
        try:
            values[position.asset_id] = _convert(
                amount=value,
                from_currency=portfolio.base_currency,
                to_currency=base_currency,
                on_date=target,
            )
        except ValidationError:
            continue

    status = "ready" if len(values) == len(active) else "partial"
    return _result(
        status=status,
        on_date=target,
        total=len(active),
        usable=len(values),
        values=values,
    )


def _result(
    *,
    status: str,
    on_date: date | None,
    total: int,
    usable: int,
    values: dict[int, Decimal],
) -> dict[str, Any]:
    return {
        "status": status,
        "as_of": on_date.isoformat() if on_date else None,
        "position_count": total,
        "usable_position_count": usable,
        "values": values,
    }


def _convert(*, amount: Decimal, from_currency: str, to_currency: str, on_date: date) -> Decimal:
    if from_currency.upper() == to_currency.upper():
        return amount
    try:
        return convert_currency_detailed(
            amount,
            from_currency,
            to_currency,
            on_date=on_date,
            allow_sync=False,
        ).converted
    except ValidationError:
        # La posicion queda fuera del override; Patrimonio conserva su cifra hasta que
        # exista la conversion, igual que hace con una valoracion no apta.
        raise
