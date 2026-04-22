from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from django.utils import timezone as django_timezone

from ..models import BotNetResult, BrokerCredential, BrokerTrade, IncomeEvent
from .encryption import decrypt
from .pionex_client import PionexApiError, PionexClient


@dataclass
class SyncStats:
    new_trades: int = 0
    updated_trades: int = 0
    new_bot_results: int = 0
    updated_bot_results: int = 0
    new_income_events: int = 0
    updated_income_events: int = 0
    gaps: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "new_trades": self.new_trades,
            "updated_trades": self.updated_trades,
            "new_bot_results": self.new_bot_results,
            "updated_bot_results": self.updated_bot_results,
            "new_income_events": self.new_income_events,
            "updated_income_events": self.updated_income_events,
            "gaps": self.gaps,
        }


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _timestamp_to_dt(raw: Any) -> datetime:
    if raw is None:
        return django_timezone.now()
    text = str(raw).strip()
    if text.isdigit():
        number = int(text)
        if number > 10_000_000_000:
            number = number / 1000
        return datetime.fromtimestamp(number, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return django_timezone.now()


def _split_symbol(symbol: str) -> tuple[str, str]:
    clean = symbol.upper()
    if "_" in clean:
        base, quote = clean.split("_", 1)
        quote = quote.replace("_PERP", "").replace("PERP", "")
        return base, quote or "USDT"
    for suffix in ("USDT", "USDC", "BTC", "ETH", "EUR"):
        if clean.endswith(suffix) and len(clean) > len(suffix):
            return clean[: -len(suffix)], suffix
    return clean, "USDT"


def _record_trade_fill(
    *,
    credential: BrokerCredential,
    fill: dict[str, Any],
    symbol_fallback: str,
    stats: SyncStats,
) -> None:
    symbol = str(fill.get("symbol") or symbol_fallback or "").upper()
    base_asset, quote_asset = _split_symbol(symbol)
    trade_id = (
        fill.get("id")
        or fill.get("tradeId")
        or fill.get("orderId")
        or hashlib.sha256(json.dumps(fill, sort_keys=True).encode()).hexdigest()
    )
    timestamp = _timestamp_to_dt(
        fill.get("timestamp")
        or fill.get("time")
        or fill.get("createTime")
        or fill.get("filledTime")
    )
    defaults = {
        "credential": credential,
        "symbol": symbol,
        "base_asset": base_asset,
        "quote_asset": quote_asset,
        "side": str(fill.get("side") or "BUY").upper(),
        "price": _to_decimal(fill.get("price") or fill.get("avgPrice")),
        "quantity": _to_decimal(
            fill.get("quantity") or fill.get("size") or fill.get("amount") or fill.get("filledQty")
        ),
        "fee": _to_decimal(fill.get("fee") or fill.get("commission")),
        "fee_asset": str(fill.get("feeCoin") or fill.get("commissionAsset") or quote_asset).upper(),
        "timestamp": timestamp,
        "raw": fill,
    }
    _, created = BrokerTrade.objects.update_or_create(
        source=BrokerTrade.Source.PIONEX_API,
        trade_id=str(trade_id),
        defaults=defaults,
    )
    if created:
        stats.new_trades += 1
    else:
        stats.updated_trades += 1


def _record_dual_income(
    *, credential: BrokerCredential, record: dict[str, Any], stats: SyncStats
) -> None:
    timestamp = _timestamp_to_dt(
        record.get("settleTime")
        or record.get("time")
        or record.get("timestamp")
        or record.get("createTime")
    )
    amount = _to_decimal(
        record.get("yieldAmount") or record.get("profit") or record.get("interest")
    )
    asset = str(record.get("asset") or record.get("currency") or "USDT").upper()
    defaults = {
        "credential": credential,
        "description": "Pionex Dual Investment",
        "raw": record,
    }
    _, created = IncomeEvent.objects.update_or_create(
        source=IncomeEvent.Source.PIONEX_DUAL_INVEST_API,
        income_type=IncomeEvent.IncomeType.DUAL_INVEST_YIELD,
        asset=asset,
        amount=amount,
        timestamp=timestamp,
        defaults=defaults,
    )
    if created:
        stats.new_income_events += 1
    else:
        stats.updated_income_events += 1


def sync_pionex(*, credential: BrokerCredential, year: int) -> dict[str, Any]:
    stats = SyncStats()
    client = PionexClient(
        api_key=credential.api_key,
        api_secret=decrypt(bytes(credential.api_secret_encrypted)),
    )
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000) - 1

    try:
        client.get_balances()
    except PionexApiError as exc:
        stats.gaps.append({"source": "balances", "reason": str(exc), "code": exc.code or ""})

    for symbol in ("BTC_USDT", "ETH_USDT"):
        try:
            fills = client.get_fills(symbol=symbol, start_ms=start_ms, end_ms=end_ms, limit=100)
            for fill in fills:
                if isinstance(fill, dict):
                    _record_trade_fill(
                        credential=credential,
                        fill=fill,
                        symbol_fallback=symbol,
                        stats=stats,
                    )
        except PionexApiError as exc:
            stats.gaps.append(
                {"source": f"fills:{symbol}", "reason": str(exc), "code": exc.code or ""}
            )

    dual_bases = [
        item.strip().upper()
        for item in os.getenv("PIONEX_DUAL_BASES", "BTC,ETH,SOL,BNB").split(",")
        if item.strip()
    ]
    for base in dual_bases:
        try:
            dual_records = client.get_dual_invest_records(
                base=base,
                start_ms=start_ms,
                end_ms=end_ms,
                limit=100,
            )
            for record in dual_records:
                if isinstance(record, dict):
                    _record_dual_income(credential=credential, record=record, stats=stats)
        except PionexApiError as exc:
            stats.gaps.append(
                {"source": f"dual_records:{base}", "reason": str(exc), "code": exc.code or ""}
            )

    bot_ids = [
        value.strip() for value in os.getenv("PIONEX_BOT_IDS", "").split(",") if value.strip()
    ]
    for bot_id in bot_ids:
        try:
            summary = client.get_bot_summary(bot_id=bot_id)
            symbol = str(summary.get("symbol") or summary.get("quoteSymbol") or "BTC_USDT")
            base_asset, quote_asset = _split_symbol(symbol)
            defaults = {
                "bot_type": str(summary.get("botType") or "spot_grid"),
                "label": str(summary.get("name") or f"Bot {bot_id}"),
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "realized_profit": _to_decimal(
                    summary.get("realizedProfit") or summary.get("totalProfit")
                ),
                "total_fee_base": _to_decimal(summary.get("totalFeeBase")),
                "total_fee_quote": _to_decimal(summary.get("totalFeeQuote")),
                "period_start": _timestamp_to_dt(summary.get("startTime") or start_ms),
                "period_end": _timestamp_to_dt(summary.get("endTime") or end_ms),
                "raw": summary,
            }
            _, created = BotNetResult.objects.update_or_create(
                credential=credential,
                bot_id=bot_id,
                defaults=defaults,
            )
            if created:
                stats.new_bot_results += 1
            else:
                stats.updated_bot_results += 1
        except PionexApiError as exc:
            stats.gaps.append(
                {"source": f"bot:{bot_id}", "reason": str(exc), "code": exc.code or ""}
            )

    payload = stats.to_dict()
    credential.last_sync_at = django_timezone.now()
    credential.last_sync_stats = payload
    credential.last_sync_gaps = payload["gaps"]
    credential.save(
        update_fields=["last_sync_at", "last_sync_stats", "last_sync_gaps", "updated_at"]
    )
    return payload


def sync_credential(*, credential: BrokerCredential, year: int) -> dict[str, Any]:
    if credential.broker == BrokerCredential.Broker.PIONEX:
        return sync_pionex(credential=credential, year=year)
    raise ValueError(f"Broker no soportado en esta fase: {credential.broker}")
