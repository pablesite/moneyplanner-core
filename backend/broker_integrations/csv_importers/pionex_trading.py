from __future__ import annotations

from .common import (
    compute_fiscal_identity_key,
    csv_rows,
    deterministic_id,
    parse_pionex_datetime,
    split_symbol,
    to_decimal,
)
from ..models import BrokerTrade


def import_pionex_trading(*, uploaded_file, credential=None) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0
    for row in csv_rows(uploaded_file):
        market_type = (row.get("market_type") or "").strip()
        if market_type != "Spot":
            skipped += 1
            continue
        symbol = (row.get("symbol") or "").strip().upper()
        base_asset, quote_asset = split_symbol(symbol)
        timestamp = parse_pionex_datetime(row.get("date(UTC+0)") or "")
        side = (row.get("side") or "BUY").strip().upper()
        side_clean = side if side in {"BUY", "SELL"} else "BUY"
        quantity = to_decimal(row.get("executed_qty"))
        price = to_decimal(row.get("price"))
        trade_id = deterministic_id(
            row.get("date(UTC+0)"),
            symbol,
            side,
            row.get("executed_qty"),
            row.get("price"),
        )
        defaults = {
            "credential": credential,
            "symbol": symbol,
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "side": side_clean,
            "price": price,
            "quantity": quantity,
            "fee": to_decimal(row.get("fee")),
            "fee_asset": (row.get("fee_coin") or "").strip().upper(),
            "timestamp": timestamp,
            "fiscal_provenance": BrokerTrade.FiscalProvenance.CSV_FALLBACK,
            "fiscal_identity_key": compute_fiscal_identity_key(
                symbol=symbol,
                side=side_clean,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
            ),
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
