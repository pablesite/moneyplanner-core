from __future__ import annotations

from decimal import Decimal

from .common import csv_rows, parse_pionex_datetime, split_symbol, to_decimal
from ..models import FuturesPosition


def import_pionex_futures(*, uploaded_file, credential=None) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0
    for row in csv_rows(uploaded_file):
        position_id = (row.get("position_id") or "").strip()
        if not position_id:
            skipped += 1
            continue
        symbol = (row.get("symbol") or "").strip().upper()
        base_asset, _ = split_symbol(symbol)
        fee = to_decimal(row.get("fee"))
        net_pnl = to_decimal(row.get("pnl")) - abs(fee) + to_decimal(row.get("funding_fee"))
        defaults = {
            "credential": credential,
            "symbol": symbol,
            "base_asset": base_asset,
            "side": (row.get("position_side") or "long").strip().lower(),
            "open_time": parse_pionex_datetime(row.get("open_time") or ""),
            "close_time": parse_pionex_datetime(row.get("close_time") or ""),
            "pnl": to_decimal(row.get("pnl")),
            "fee": fee,
            "funding_fee": to_decimal(row.get("funding_fee")),
            "net_pnl": net_pnl.quantize(Decimal("0.0000000001")),
            "raw": row,
        }
        _, was_created = FuturesPosition.objects.update_or_create(
            source=FuturesPosition.Source.PIONEX_CSV,
            position_id=position_id,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated, "skipped": skipped}
