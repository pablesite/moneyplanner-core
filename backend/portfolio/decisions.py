"""Registro de decisiones: que propuso el sistema, que hizo el usuario y que paso despues.

Es la unica forma honesta de saber si esto ayuda. La alternativa —simular que habria
pasado con DCA puro o con buy & hold— suena mas cientifica y es peor: con pocas apuestas
reales y pocos anos de historia, la diferencia medida esta dominada por el ruido, asi que
se estaria midiendo suerte y llamandola sistema. Y para la parte iliquida ni siquiera es
calculable, porque no tiene serie de precios.

Aqui no se simula nada. Se registra lo que de verdad ocurrio: una propuesta de aportacion
con su reparto, lo que el usuario ejecuto de ella —entera, a medias o nada— y la
desviacion del ambito antes y despues. Si seguir las propuestas acerca la cartera a su
politica, se vera; si no, tambien.

No hay modelo nuevo: la cesta ya guarda la propuesta, sus lineas guardan que se confirmo y
el libro guarda lo que se contabilizo. Duplicarlo en una tabla de auditoria solo anadiria
una segunda version de la verdad que puede desincronizarse de la primera.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from memberships.models import Ownership

from .allocation import build_allocation
from .models import ContributionBasket, ContributionBasketLine, Portfolio
from .performance import PerformanceContext

ZERO = Decimal("0")


def _worst_drift(allocation: dict[str, Any]) -> Decimal | None:
    """La clase que mas lejos esta de su objetivo, en valor absoluto.

    Una sola cifra para "cuanto se parece la cartera a su plan". La media escondería el
    problema: dos clases desviadas en sentidos opuestos se cancelarian y darian cero.
    """
    drifts = [
        abs(Decimal(row["drift_value"]))
        for row in allocation.get("by_class", [])
        if row.get("drift_value") is not None
    ]
    return max(drifts) if drifts else None


def _line_rows(basket: ContributionBasket) -> list[dict[str, Any]]:
    rows = []
    for line in basket.lines.select_related("position__asset", "cash_account__container").all():
        rows.append(
            {
                "id": line.id,
                "target": (
                    line.position.asset.name
                    if line.position_id
                    else f"Efectivo · {line.cash_account.container.name}"
                    if line.cash_account_id
                    else ""
                ),
                "amount": str(line.amount),
                "status": line.status,
                "ledger_transaction_id": line.ledger_transaction_id,
            }
        )
    return rows


def build_decision_log(
    *,
    portfolio: Portfolio,
    ownership: Ownership,
    on_date: date,
    limit: int = 24,
    context: PerformanceContext | None = None,
) -> dict[str, Any]:
    """Las ultimas propuestas del ambito, con lo que se hizo con ellas y como quedo."""
    baskets = list(
        ContributionBasket.objects.filter(portfolio=portfolio, ownership=ownership)
        .prefetch_related("lines__position__asset", "lines__cash_account__container")
        .order_by("-booking_date", "-id")[:limit]
    )
    current = build_allocation(
        portfolio=portfolio, ownership=ownership, on_date=on_date, context=context
    )
    drift_now = _worst_drift(current)

    entries = []
    followed = 0
    ignored = 0
    for basket in baskets:
        lines = _line_rows(basket)
        confirmed = [
            row for row in lines if row["status"] == ContributionBasketLine.Status.CONFIRMED
        ]
        executed_amount = sum((Decimal(row["amount"]) for row in confirmed), ZERO)
        proposed_amount = Decimal(basket.amount)
        # La desviacion del dia en que se propuso, medida contra la politica que estaba
        # escrita entonces: juzgar marzo con la politica de hoy no dice nada.
        allocation_then = build_allocation(
            portfolio=portfolio, ownership=ownership, on_date=basket.booking_date
        )
        drift_then = _worst_drift(allocation_then)
        if executed_amount > ZERO:
            followed += 1
        elif basket.status != ContributionBasket.Status.DRAFT:
            ignored += 1
        entries.append(
            {
                "id": basket.id,
                "date": basket.booking_date.isoformat(),
                "status": basket.status,
                "recommended": {
                    "amount": str(proposed_amount),
                    "reserved_cash": str(basket.reserved_cash),
                    "leftover": str(basket.leftover),
                    "lines": lines,
                    "explanation": basket.explanation or {},
                },
                "did": {
                    "executed_amount": str(executed_amount),
                    "lines_confirmed": len(confirmed),
                    "lines_total": len(lines),
                    "followed": (
                        "fully"
                        if lines and len(confirmed) == len(lines)
                        else "partially"
                        if confirmed
                        else "not_yet"
                        if basket.status == ContributionBasket.Status.DRAFT
                        else "no"
                    ),
                },
                "outcome": {
                    # Sin comparacion inventada: la desviacion de entonces y la de ahora,
                    # y que cada uno saque su conclusion.
                    "worst_drift_at_decision": None if drift_then is None else str(drift_then),
                    "worst_drift_now": None if drift_now is None else str(drift_now),
                    "measurable": drift_then is not None and drift_now is not None,
                },
            }
        )

    return {
        "ownership_id": ownership.id,
        "currency": portfolio.base_currency,
        "on_date": on_date.isoformat(),
        "worst_drift_now": None if drift_now is None else str(drift_now),
        "summary": {
            "decisions": len(entries),
            "followed": followed,
            "ignored": ignored,
            "pending": sum(
                1 for row in entries if row["status"] == ContributionBasket.Status.DRAFT
            ),
        },
        "entries": entries,
        # Se dice en el propio contrato para que nadie lo lea como un backtest.
        "method": {
            "kind": "observed",
            "note": (
                "Registro de lo ocurrido, no simulacion. No se compara contra DCA ni buy & "
                "hold: con esta historia y este numero de posiciones esa diferencia mide "
                "ruido, y para la parte iliquida no es calculable."
            ),
        },
    }
