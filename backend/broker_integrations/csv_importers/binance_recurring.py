from __future__ import annotations

from .common import csv_rows, deterministic_id, parse_binance_datetime, to_decimal
from ..models import BrokerTrade


def import_binance_recurring(*, uploaded_file, credential=None) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0

    for row in csv_rows(uploaded_file):
        status = (row.get("Estado") or "").strip().upper()
        if status != "SUCCESS":
            skipped += 1
            continue

        original_amount = abs(to_decimal(row.get("Monto original")))
        final_amount = abs(to_decimal(row.get("Monto final")))
        original_asset = (row.get("Moneda original") or "").strip().upper()
        final_asset = (row.get("Moneda final") or "").strip().upper()
        if original_amount <= 0 or final_amount <= 0:
            skipped += 1
            continue

        timestamp_text = (
            row.get("Fecha de liquidación") or row.get("Fecha de creación") or ""
        ).strip()
        if not timestamp_text:
            skipped += 1
            continue
        symbol = f"{final_asset}{original_asset}"
        trade_id = deterministic_id(timestamp_text, symbol, original_amount)
        defaults = {
            "credential": credential,
            "symbol": symbol,
            "base_asset": final_asset,
            "quote_asset": original_asset,
            "side": BrokerTrade.Side.BUY,
            "price": original_amount / final_amount,
            "quantity": final_amount,
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
