from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .common import (
    csv_rows,
    deterministic_id,
    parse_binance_datetime,
    to_decimal,
    upsert_income_event_dedup,
)
from ..models import BrokerTrade


@dataclass
class _TxRow:
    index: int
    timestamp: datetime
    operation: str
    asset: str
    amount: Decimal
    row: dict[str, str]


def _normalize_operation(row: dict[str, str]) -> str:
    return (row.get("Operación") or row.get("Operacion") or "").strip()


def _record_income(
    *,
    source: str,
    income_type: str,
    operation_label: str,
    tx_row: _TxRow,
    credential,
) -> bool:
    lookup = {
        "source": source,
        "income_type": income_type,
        "asset": tx_row.asset,
        "amount": abs(tx_row.amount),
        "timestamp": tx_row.timestamp,
    }
    defaults = {
        "credential": credential,
        "description": operation_label,
        "raw": tx_row.row,
    }
    _, created = upsert_income_event_dedup(lookup=lookup, defaults=defaults)
    return created


def _find_best_match(
    *, target: _TxRow, candidates: list[_TxRow], used_indexes: set[int]
) -> _TxRow | None:
    best: _TxRow | None = None
    best_delta: float | None = None
    for candidate in candidates:
        if candidate.index in used_indexes:
            continue
        delta = abs((candidate.timestamp - target.timestamp).total_seconds())
        if delta > 2:
            continue
        if best is None or (best_delta is not None and delta < best_delta):
            best = candidate
            best_delta = delta
    return best


def import_binance_transactions(*, uploaded_file, credential=None) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0

    tx_rows: list[_TxRow] = []
    for index, row in enumerate(csv_rows(uploaded_file)):
        operation = _normalize_operation(row)
        asset = (row.get("Moneda") or "").strip().upper()
        amount = to_decimal(row.get("Cambiar"))
        timestamp_text = (row.get("Hora") or "").strip()
        if not timestamp_text:
            skipped += 1
            continue
        try:
            timestamp = parse_binance_datetime(timestamp_text)
        except ValueError:
            skipped += 1
            continue
        tx_row = _TxRow(
            index=index,
            timestamp=timestamp,
            operation=operation,
            asset=asset,
            amount=amount,
            row=row,
        )

        if operation == "Simple Earn Flexible Interest":
            if _record_income(
                source="binance_earn_csv",
                income_type="binance_earn",
                operation_label="Binance Earn",
                tx_row=tx_row,
                credential=credential,
            ):
                created += 1
            else:
                updated += 1
            continue

        if operation == "Referral Commission":
            if _record_income(
                source="binance_referral_csv",
                income_type="commission",
                operation_label="Referral Commission",
                tx_row=tx_row,
                credential=credential,
            ):
                created += 1
            else:
                updated += 1
            continue

        if operation in {"Transaction Buy", "Transaction Spend", "Transaction Fee"}:
            tx_rows.append(tx_row)
            continue

        # Movement types that are irrelevant for fiscal trade ingestion in this phase.
        skipped += 1

    buys = [row for row in tx_rows if row.operation == "Transaction Buy" and row.amount > 0]
    spends = [row for row in tx_rows if row.operation == "Transaction Spend" and row.amount < 0]
    fees = [row for row in tx_rows if row.operation == "Transaction Fee" and row.amount < 0]
    used_spends: set[int] = set()
    used_fees: set[int] = set()

    for buy in sorted(buys, key=lambda item: (item.timestamp, item.index)):
        spend = _find_best_match(target=buy, candidates=spends, used_indexes=used_spends)
        fee_candidates = [fee for fee in fees if fee.asset == buy.asset]
        fee = _find_best_match(target=buy, candidates=fee_candidates, used_indexes=used_fees)
        if spend is None or fee is None:
            skipped += 1
            continue

        quantity = abs(buy.amount) - abs(fee.amount)
        if quantity <= 0:
            skipped += 1
            continue
        quote_amount = abs(spend.amount)
        trade_id = deterministic_id(
            buy.row.get("Hora"),
            "TxBuy",
            buy.asset,
            abs(buy.amount),
        )
        symbol = f"{buy.asset}{spend.asset}"
        defaults = {
            "credential": credential,
            "symbol": symbol,
            "base_asset": buy.asset,
            "quote_asset": spend.asset,
            "side": BrokerTrade.Side.BUY,
            "price": quote_amount / quantity,
            "quantity": quantity,
            "fee": abs(fee.amount),
            "fee_asset": fee.asset,
            "timestamp": buy.timestamp,
            "raw": {
                "buy": buy.row,
                "spend": spend.row,
                "fee": fee.row,
            },
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
        used_spends.add(spend.index)
        used_fees.add(fee.index)

    return {"created": created, "updated": updated, "skipped": skipped}
