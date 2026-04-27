from __future__ import annotations

from .common import csv_rows, deterministic_id, parse_binance_datetime, to_decimal
from ..models import BrokerTrade


def _parse_amount_asset(value: str) -> tuple[str, str]:
    parts = [part for part in value.strip().split(" ") if part]
    if len(parts) < 2:
        return "0", ""
    return parts[0], parts[-1].upper()


def import_binance_convert(*, uploaded_file, credential=None) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0

    for row in csv_rows(uploaded_file):
        status = (row.get("Estado") or "").strip().upper()
        if status != "SUCCESSFUL":
            skipped += 1
            continue
        sell_raw = row.get("Vender") or ""
        buy_raw = row.get("Comprar") or ""
        sell_amount_raw, sell_asset = _parse_amount_asset(sell_raw)
        buy_amount_raw, buy_asset = _parse_amount_asset(buy_raw)
        sell_amount = abs(to_decimal(sell_amount_raw))
        buy_amount = abs(to_decimal(buy_amount_raw))
        if buy_amount <= 0:
            skipped += 1
            continue
        timestamp_text = (row.get("Hora") or "").strip()
        if not timestamp_text:
            skipped += 1
            continue
        symbol = (row.get("Par") or f"{buy_asset}{sell_asset}").strip().upper()
        trade_id = deterministic_id(timestamp_text, symbol, sell_amount)
        defaults = {
            "credential": credential,
            "symbol": symbol,
            "base_asset": sell_asset,
            "quote_asset": buy_asset,
            "side": BrokerTrade.Side.SELL,
            "price": buy_amount / sell_amount,
            "quantity": sell_amount,
            "fee": to_decimal("0"),
            "fee_asset": "",
            "timestamp": parse_binance_datetime(timestamp_text),
            "raw": row,
        }
        _, was_created = BrokerTrade.objects.update_or_create(
            source=BrokerTrade.Source.BINANCE_CSV,
            trade_id=trade_id,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return {"created": created, "updated": updated, "skipped": skipped}
