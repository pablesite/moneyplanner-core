from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from memberships.models import Ownership

from ..models import BrokerSyncRun, BrokerTrade, ManualCostBasis
from .eur_converter import EurConverter


GAP_REASON_PRE_PERIOD_BUY = "pre_period_buy"
GAP_REASON_MISSING_DATA = "missing_data"
GAP_REASON_BALANCE_TRANSFER_IN = "balance_transfer_in"


@dataclass
class _PoolLot:
    buy_trade_id: int | None
    manual_cost_basis_id: int | None
    buy_date: datetime | None
    buy_exchange: str | None
    buy_symbol: str | None
    quantity_remaining: Decimal
    unit_price_eur: Decimal
    source_kind: str  # trade | manual


@dataclass
class MatchedLot:
    buy_trade_id: int | None
    manual_cost_basis_id: int | None
    buy_date: str | None
    buy_exchange: str | None
    buy_symbol: str | None
    quantity_consumed: Decimal
    unit_price_eur: Decimal
    cost_eur: Decimal
    fee_eur_allocated: Decimal
    gain_loss_eur: Decimal
    hold_days: int


@dataclass
class FifoSaleMatch:
    sell_trade_id: int
    sell_date: str
    sell_exchange: str
    sell_symbol: str
    quantity_sold: Decimal
    proceeds_eur: Decimal
    fee_eur: Decimal
    matched_lots: list[MatchedLot]
    gap_quantity: Decimal
    gap_reason: str | None


def _exchange_from_source(source: str) -> str:
    return (source or "").split("_", 1)[0].strip().lower() or "unknown"


def _normalize_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _trade_unit_price_eur(*, trade: BrokerTrade, eur_converter: EurConverter) -> Decimal:
    if trade.price_eur is not None:
        return Decimal(trade.price_eur)
    return Decimal(trade.price) * eur_converter.get_eur_rate(
        trade_date=trade.timestamp.date(),
        asset=trade.quote_asset,
    )


def _trade_fee_eur(*, trade: BrokerTrade, eur_converter: EurConverter) -> Decimal:
    if trade.fee_eur is not None:
        return Decimal(trade.fee_eur)
    if not trade.fee or not trade.fee_asset:
        return Decimal("0")
    return Decimal(trade.fee) * eur_converter.get_eur_rate(
        trade_date=trade.timestamp.date(),
        asset=trade.fee_asset,
    )


def _build_missing_data_assets(*, ownership: Ownership) -> set[str]:
    assets: set[str] = set()
    runs = BrokerSyncRun.objects.filter(credential__ownership=ownership).only("gaps")
    for run in runs:
        gaps = run.gaps if isinstance(run.gaps, list) else []
        for gap in gaps:
            if not isinstance(gap, dict):
                continue
            if gap.get("source") != "balance_reconciliation":
                continue
            if gap.get("reason") != "balance_mismatch":
                continue
            asset = str(gap.get("asset") or "").strip().upper()
            if asset:
                assets.add(asset)
    return assets


def _determine_gap_reason(
    *,
    base_asset: str,
    ownership: Ownership,
    missing_data_assets: set[str],
    fiscal_year: int,
) -> str:
    if base_asset in missing_data_assets:
        return GAP_REASON_MISSING_DATA
    has_pre_year_buy = BrokerTrade.objects.filter(
        credential__ownership=ownership,
        base_asset=base_asset,
        side=BrokerTrade.Side.BUY,
        timestamp__year__lt=fiscal_year,
    ).exists()
    has_manual_pre_year = ManualCostBasis.objects.filter(
        ownership=ownership,
        asset=base_asset,
        acquired_at__year__lt=fiscal_year,
    ).exists()
    if has_pre_year_buy or has_manual_pre_year:
        return GAP_REASON_PRE_PERIOD_BUY
    return GAP_REASON_BALANCE_TRANSFER_IN


def calculate_fifo_for_asset(
    *,
    ownership: Ownership,
    base_asset: str,
    year: int,
    eur_converter: EurConverter,
) -> dict[str, Any]:
    asset = (base_asset or "").strip().upper()
    trades = list(
        BrokerTrade.objects.filter(
            credential__ownership=ownership,
            base_asset=asset,
        ).order_by("timestamp", "id")
    )

    manual_rows = list(
        ManualCostBasis.objects.filter(ownership=ownership, asset=asset).order_by(
            "acquired_at", "id"
        )
    )
    for row in manual_rows:
        row.quantity_remaining = row.quantity
    if manual_rows:
        ManualCostBasis.objects.bulk_update(manual_rows, ["quantity_remaining"])

    pool: list[_PoolLot] = []
    for row in manual_rows:
        if row.quantity_remaining <= 0:
            continue
        unit_price = Decimal(row.cost_eur) / Decimal(row.quantity) if row.quantity else Decimal("0")
        pool.append(
            _PoolLot(
                buy_trade_id=None,
                manual_cost_basis_id=row.id,
                buy_date=row.acquired_at,
                buy_exchange="manual",
                buy_symbol=asset,
                quantity_remaining=Decimal(row.quantity_remaining),
                unit_price_eur=unit_price,
                source_kind="manual",
            )
        )

    sale_matches: list[FifoSaleMatch] = []
    warnings: list[str] = []
    missing_data_assets = _build_missing_data_assets(ownership=ownership)

    for trade in trades:
        unit_price_eur = _trade_unit_price_eur(trade=trade, eur_converter=eur_converter)
        if trade.side == BrokerTrade.Side.BUY:
            pool.append(
                _PoolLot(
                    buy_trade_id=trade.id,
                    manual_cost_basis_id=None,
                    buy_date=trade.timestamp,
                    buy_exchange=_exchange_from_source(trade.source),
                    buy_symbol=trade.symbol,
                    quantity_remaining=Decimal(trade.quantity),
                    unit_price_eur=unit_price_eur,
                    source_kind="trade",
                )
            )
            min_dt = datetime.min.replace(tzinfo=timezone.utc)
            pool.sort(key=lambda item: (item.buy_date or min_dt, item.buy_trade_id or 0))
            continue

        if trade.side != BrokerTrade.Side.SELL or trade.timestamp.year != year:
            continue

        quantity_sold = Decimal(trade.quantity)
        proceeds_eur_total = quantity_sold * unit_price_eur
        fee_eur_total = _trade_fee_eur(trade=trade, eur_converter=eur_converter)
        remaining_sell_qty = quantity_sold
        matched_lots: list[MatchedLot] = []

        for lot in pool:
            if remaining_sell_qty <= 0:
                break
            if lot.quantity_remaining <= 0:
                continue
            qty_consumed = min(remaining_sell_qty, lot.quantity_remaining)
            if qty_consumed <= 0:
                continue
            lot_proceeds = (
                proceeds_eur_total * qty_consumed / quantity_sold if quantity_sold else Decimal("0")
            )
            fee_alloc = (
                fee_eur_total * qty_consumed / quantity_sold if quantity_sold else Decimal("0")
            )
            cost_eur = qty_consumed * lot.unit_price_eur
            gain_loss = lot_proceeds - cost_eur - fee_alloc
            hold_days = 0
            if lot.buy_date is not None:
                hold_days = (trade.timestamp.date() - lot.buy_date.date()).days
            matched_lots.append(
                MatchedLot(
                    buy_trade_id=lot.buy_trade_id,
                    manual_cost_basis_id=lot.manual_cost_basis_id,
                    buy_date=lot.buy_date.date().isoformat() if lot.buy_date else None,
                    buy_exchange=lot.buy_exchange,
                    buy_symbol=lot.buy_symbol,
                    quantity_consumed=qty_consumed,
                    unit_price_eur=lot.unit_price_eur,
                    cost_eur=cost_eur,
                    fee_eur_allocated=fee_alloc,
                    gain_loss_eur=gain_loss,
                    hold_days=hold_days,
                )
            )
            lot.quantity_remaining -= qty_consumed
            remaining_sell_qty -= qty_consumed

        # Keep manual rows in sync with consumed pool quantities.
        if manual_rows:
            manual_by_id = {row.id: row for row in manual_rows}
            for lot in pool:
                if lot.manual_cost_basis_id is None:
                    continue
                row = manual_by_id.get(lot.manual_cost_basis_id)
                if row is None:
                    continue
                row.quantity_remaining = max(Decimal("0"), lot.quantity_remaining)
            ManualCostBasis.objects.bulk_update(manual_rows, ["quantity_remaining"])

        gap_reason = None
        if remaining_sell_qty > 0:
            gap_reason = _determine_gap_reason(
                base_asset=asset,
                ownership=ownership,
                missing_data_assets=missing_data_assets,
                fiscal_year=year,
            )
            warnings.append(
                f"FIFO gap {asset}: venta {trade.id} con cantidad no cubierta={remaining_sell_qty} ({gap_reason})."
            )

        sale_matches.append(
            FifoSaleMatch(
                sell_trade_id=trade.id,
                sell_date=trade.timestamp.date().isoformat(),
                sell_exchange=_exchange_from_source(trade.source),
                sell_symbol=trade.symbol,
                quantity_sold=quantity_sold,
                proceeds_eur=proceeds_eur_total,
                fee_eur=fee_eur_total,
                matched_lots=matched_lots,
                gap_quantity=remaining_sell_qty,
                gap_reason=gap_reason,
            )
        )

    return {
        "asset": asset,
        "sales": [
            {
                **asdict(sale),
                "matched_lots": [asdict(lot) for lot in sale.matched_lots],
            }
            for sale in sale_matches
        ],
        "warnings": warnings,
    }
