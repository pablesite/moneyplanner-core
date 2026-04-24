from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from memberships.models import Ownership

from ..models import BrokerTrade
from .eur_converter import EurConverter


@dataclass
class _BuyLot:
    timestamp: datetime
    quantity_remaining: Decimal
    unit_price_eur: Decimal
    exchange: str
    symbol: str


def _exchange_from_source(source: str) -> str:
    return (source or "").split("_", 1)[0].strip().lower() or "unknown"


def calculate_fifo_for_asset(
    *,
    ownership: Ownership,
    base_asset: str,
    year: int,
    eur_converter: EurConverter,
) -> dict[str, Any]:
    trades = list(
        BrokerTrade.objects.filter(
            credential__ownership=ownership,
            base_asset=(base_asset or "").strip().upper(),
        ).order_by("timestamp", "id")
    )

    buy_queue: deque[_BuyLot] = deque()
    realized_lots: list[dict[str, Any]] = []
    warnings: list[str] = []

    for trade in trades:
        trade_date = trade.timestamp.date()
        unit_price_eur = trade.price * eur_converter.get_eur_rate(
            trade_date=trade_date,
            asset=trade.quote_asset,
        )

        if trade.side == BrokerTrade.Side.BUY:
            buy_queue.append(
                _BuyLot(
                    timestamp=trade.timestamp,
                    quantity_remaining=Decimal(trade.quantity),
                    unit_price_eur=unit_price_eur,
                    exchange=_exchange_from_source(trade.source),
                    symbol=trade.symbol,
                )
            )
            continue

        if trade.side != BrokerTrade.Side.SELL:
            continue
        if trade.timestamp.year != year:
            continue

        remaining_sell_qty = Decimal(trade.quantity)
        sell_exchange = _exchange_from_source(trade.source)

        while remaining_sell_qty > 0 and buy_queue:
            lot = buy_queue[0]
            qty_consumed = min(remaining_sell_qty, lot.quantity_remaining)
            cost_eur = qty_consumed * lot.unit_price_eur
            proceeds_eur = qty_consumed * unit_price_eur
            gain_loss_eur = proceeds_eur - cost_eur

            realized_lots.append(
                {
                    "buy_date": lot.timestamp.date().isoformat(),
                    "sell_date": trade.timestamp.date().isoformat(),
                    "exchange_buy": lot.exchange,
                    "exchange_sell": sell_exchange,
                    "symbol": trade.symbol,
                    "quantity": qty_consumed,
                    "cost_eur": cost_eur,
                    "proceeds_eur": proceeds_eur,
                    "gain_loss_eur": gain_loss_eur,
                    "hold_days": (trade.timestamp.date() - lot.timestamp.date()).days,
                    "casilla": "332",
                }
            )

            lot.quantity_remaining -= qty_consumed
            remaining_sell_qty -= qty_consumed
            if lot.quantity_remaining <= 0:
                buy_queue.popleft()

        if remaining_sell_qty > 0:
            warnings.append(
                f"FIFO gap {base_asset}: venta {trade.id} sin compras suficientes. "
                f"Cantidad no cubierta={remaining_sell_qty}."
            )
            proceeds_eur = remaining_sell_qty * unit_price_eur
            realized_lots.append(
                {
                    "buy_date": None,
                    "sell_date": trade.timestamp.date().isoformat(),
                    "exchange_buy": "missing",
                    "exchange_sell": sell_exchange,
                    "symbol": trade.symbol,
                    "quantity": remaining_sell_qty,
                    "cost_eur": Decimal("0"),
                    "proceeds_eur": proceeds_eur,
                    "gain_loss_eur": proceeds_eur,
                    "hold_days": 0,
                    "casilla": "332",
                }
            )

    return {
        "asset": base_asset,
        "lots": realized_lots,
        "warnings": warnings,
    }
