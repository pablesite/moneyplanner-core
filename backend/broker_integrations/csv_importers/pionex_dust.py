from __future__ import annotations

from decimal import Decimal

from .common import csv_rows, deterministic_id, parse_pionex_datetime, to_decimal
from ..models import BrokerTrade


def import_pionex_dust(*, uploaded_file, credential=None) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0
    for row in csv_rows(uploaded_file):
        amount = to_decimal(row.get("amount"))
        if amount <= 0:
            skipped += 1
            continue
        swap_value = to_decimal(row.get("swap_value"))
        price = Decimal("0") if amount == 0 else (swap_value / amount)
        timestamp = parse_pionex_datetime(row.get("date(UTC+0)") or "")
        symbol = f"{(row.get('coin') or '').strip().upper()}_USDT"
        trade_id = deterministic_id(
            row.get("date(UTC+0)"),
            row.get("coin"),
            row.get("amount"),
            row.get("swap_value"),
        )
        defaults = {
            "credential": credential,
            "symbol": symbol,
            "base_asset": (row.get("coin") or "").strip().upper(),
            "quote_asset": "USDT",
            "side": BrokerTrade.Side.SELL,
            "price": price.quantize(Decimal("0.0000000001")),
            "quantity": amount,
            "fee": Decimal("0"),
            "fee_asset": "",
            "timestamp": timestamp,
            "raw": row,
        }
        _, was_created = BrokerTrade.objects.update_or_create(
            source=BrokerTrade.Source.PIONEX_CSV,
            trade_id=trade_id,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated, "skipped": skipped}
