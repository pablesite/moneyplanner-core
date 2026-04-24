from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from django.utils import timezone as django_timezone

from ..csv_importers.common import deterministic_id, upsert_income_event_dedup
from ..models import BotNetResult, BrokerCredential, BrokerTrade, IncomeEvent
from .binance_client import BinanceApiError, BinanceClient
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


def _parse_csv_env(name: str) -> list[str]:
    return [item.strip().upper() for item in os.getenv(name, "").split(",") if item.strip()]


def _normalize_symbol(value: str) -> str:
    clean = value.strip().upper().replace("-", "_").replace("/", "_")
    return clean


def _discover_spot_symbols(
    *,
    credential: BrokerCredential,
    balances: list[dict[str, Any]],
) -> list[str]:
    symbols: set[str] = set()
    ownership_symbols = BrokerTrade.objects.filter(
        credential__ownership=credential.ownership,
        source__in=(
            BrokerTrade.Source.PIONEX_API,
            BrokerTrade.Source.PIONEX_BOT_API,
            BrokerTrade.Source.PIONEX_CSV,
        ),
    ).values_list("symbol", flat=True)
    for symbol in ownership_symbols:
        normalized = _normalize_symbol(str(symbol))
        if normalized:
            symbols.add(normalized)

    stable_assets = {"USDT", "USDC", "EUR"}
    for row in balances:
        if not isinstance(row, dict):
            continue
        symbol = row.get("symbol") or row.get("pair")
        if symbol:
            symbols.add(_normalize_symbol(str(symbol)))
            continue
        raw_asset = row.get("coin") or row.get("asset") or row.get("currency")
        if not raw_asset:
            continue
        asset = str(raw_asset).strip().upper()
        if asset in stable_assets:
            continue
        amount = _to_decimal(row.get("total") or row.get("amount") or row.get("available"))
        if amount <= 0:
            continue
        symbols.add(f"{asset}_USDT")

    symbols.update(_parse_csv_env("PIONEX_SPOT_SYMBOLS"))
    if not symbols:
        symbols.update({"BTC_USDT", "ETH_USDT"})
    return sorted(symbol for symbol in symbols if symbol)


def _discover_dual_bases(*, balances: list[dict[str, Any]]) -> list[str]:
    env_bases = _parse_csv_env("PIONEX_DUAL_BASES")
    if env_bases:
        return env_bases
    discovered: set[str] = set()
    for row in balances:
        if not isinstance(row, dict):
            continue
        asset = str(row.get("coin") or row.get("asset") or row.get("currency") or "").upper()
        if not asset:
            continue
        amount = _to_decimal(row.get("total") or row.get("amount") or row.get("available"))
        if amount > 0:
            discovered.add(asset)
    if discovered:
        return sorted(discovered)
    return ["BTC", "ETH", "SOL", "BNB"]


def _compute_expected_balances(*, credential: BrokerCredential) -> dict[str, Decimal]:
    expected: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for trade in BrokerTrade.objects.filter(
        credential=credential,
        source__in=(
            BrokerTrade.Source.PIONEX_API,
            BrokerTrade.Source.PIONEX_BOT_API,
            BrokerTrade.Source.PIONEX_CSV,
        ),
    ).only("base_asset", "quote_asset", "side", "quantity", "price", "fee", "fee_asset"):
        base_asset = trade.base_asset.upper()
        quote_asset = trade.quote_asset.upper()
        quantity = trade.quantity
        quote_amount = trade.quantity * trade.price
        fee = trade.fee
        fee_asset = trade.fee_asset.upper()
        if trade.side == BrokerTrade.Side.BUY:
            expected[base_asset] += quantity
            expected[quote_asset] -= quote_amount
        else:
            expected[base_asset] -= quantity
            expected[quote_asset] += quote_amount
        if fee_asset:
            expected[fee_asset] -= fee
    for income in IncomeEvent.objects.filter(credential=credential).only("asset", "amount"):
        expected[income.asset.upper()] += income.amount
    return dict(expected)


def _compute_balance_reconciliation(
    *,
    credential: BrokerCredential,
    balances: list[dict[str, Any]],
    stats: SyncStats,
) -> None:
    expected_balances = _compute_expected_balances(credential=credential)
    actual_balances: dict[str, Decimal] = {}
    for row in balances:
        if not isinstance(row, dict):
            continue
        asset = str(row.get("coin") or row.get("asset") or row.get("currency") or "").upper()
        if not asset:
            continue
        actual_balances[asset] = _to_decimal(
            row.get("total")
            or row.get("amount")
            or (_to_decimal(row.get("available")) + _to_decimal(row.get("frozen")))
        )
    tolerance = _to_decimal(os.getenv("PIONEX_BALANCE_RECONCILIATION_TOLERANCE", "0.00000001"))
    for asset in sorted(set(expected_balances) | set(actual_balances)):
        expected = expected_balances.get(asset, Decimal("0"))
        actual = actual_balances.get(asset, Decimal("0"))
        diff = actual - expected
        if abs(diff) <= tolerance:
            continue
        stats.gaps.append(
            {
                "source": "balance_reconciliation",
                "reason": "balance_mismatch",
                "asset": asset,
                "expected": str(expected),
                "actual": str(actual),
                "diff": str(diff),
            }
        )


def _record_trade_fill(
    *,
    credential: BrokerCredential,
    fill: dict[str, Any],
    symbol_fallback: str,
    stats: SyncStats,
    source: str = BrokerTrade.Source.PIONEX_API,
    bot_result: BotNetResult | None = None,
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
        "bot": bot_result,
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
        source=source,
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


def _discover_spot_grid_bots(client: PionexClient, stats: SyncStats) -> dict[str, dict[str, Any]]:
    discovered_bots: dict[str, dict[str, Any]] = {}
    max_pages = 50
    for status in ("running", "finished"):
        page_token: str | None = None
        for _ in range(max_pages):
            try:
                rows, next_page_token = client.get_bot_orders(
                    status=status,
                    page_token=page_token,
                    limit=100,
                )
            except PionexApiError as exc:
                stats.gaps.append(
                    {"source": f"bot_orders:{status}", "reason": str(exc), "code": exc.code or ""}
                )
                break
            for row in rows:
                bot_order_type = str(row.get("buOrderType") or "").strip().lower()
                if bot_order_type != "spot_grid":
                    continue
                bot_id = str(row.get("buOrderId") or "").strip()
                if bot_id:
                    discovered_bots[bot_id] = row
            if not next_page_token:
                break
            page_token = next_page_token
    return discovered_bots


def _upsert_bot_result(
    *,
    credential: BrokerCredential,
    bot_id: str,
    payload: dict[str, Any],
    start_ms: int,
    end_ms: int,
    stats: SyncStats,
) -> BotNetResult:
    raw_data = payload.get("buOrderData") if isinstance(payload.get("buOrderData"), dict) else {}
    symbol = str(payload.get("symbol") or payload.get("base") or "BTC")
    if "_" in symbol:
        pair_symbol = symbol
    else:
        quote = str(payload.get("quote") or "USDT")
        pair_symbol = f"{symbol}_{quote}"
    base_asset, quote_asset = _split_symbol(pair_symbol)

    def pick_profit() -> Decimal:
        # Pionex spot-grid payloads often expose meaningful value in `gridProfit`
        # while `realizedProfit` remains the string "0".
        candidates = [
            raw_data.get("totalProfit"),
            payload.get("totalProfit"),
            raw_data.get("gridProfit"),
            payload.get("gridProfit"),
            raw_data.get("realizedProfit"),
            payload.get("realizedProfit"),
        ]
        parsed_values = [_to_decimal(value) for value in candidates if value not in (None, "")]
        for value in parsed_values:
            if value != 0:
                return value
        return parsed_values[0] if parsed_values else Decimal("0")

    defaults = {
        "bot_type": str(payload.get("buOrderType") or payload.get("botType") or "spot_grid"),
        "label": str(payload.get("customizeName") or payload.get("botName") or f"Bot {bot_id}"),
        "base_asset": base_asset,
        "quote_asset": quote_asset,
        "realized_profit": pick_profit(),
        "total_fee_base": _to_decimal(
            raw_data.get("totalFeeInBase")
            or raw_data.get("totalFeeBase")
            or payload.get("totalFeeBase")
        ),
        "total_fee_quote": _to_decimal(
            raw_data.get("totalFeeInQuote")
            or raw_data.get("totalFeeQuote")
            or payload.get("totalFeeQuote")
        ),
        "period_start": _timestamp_to_dt(
            payload.get("createTime") or raw_data.get("createTime") or start_ms
        ),
        "period_end": _timestamp_to_dt(
            payload.get("closeTime") or raw_data.get("closeTime") or end_ms
        ),
        "raw": payload,
    }
    bot_result, created = BotNetResult.objects.update_or_create(
        credential=credential,
        bot_id=bot_id,
        defaults=defaults,
    )
    if created:
        stats.new_bot_results += 1
    else:
        stats.updated_bot_results += 1
    return bot_result


def _record_binance_convert_trade(
    *,
    credential: BrokerCredential,
    record: dict[str, Any],
    stats: SyncStats,
) -> None:
    from_asset = str(
        record.get("fromAsset") or record.get("quoteAsset") or record.get("baseAsset") or "USDC"
    ).upper()
    to_asset = str(
        record.get("toAsset") or record.get("targetAsset") or record.get("symbol") or "BTC"
    ).upper()
    from_amount = _to_decimal(
        record.get("fromAmount")
        or record.get("quoteQty")
        or record.get("quoteAmount")
        or record.get("amount")
    )
    to_amount = _to_decimal(
        record.get("toAmount")
        or record.get("toQuantity")
        or record.get("baseQty")
        or record.get("quantity")
    )
    if to_amount <= 0:
        return
    symbol = str(record.get("symbol") or f"{to_asset}{from_asset}").upper()
    trade_id = str(
        record.get("orderId") or deterministic_id(record.get("createTime"), symbol, from_amount)
    )
    defaults = {
        "credential": credential,
        "symbol": symbol,
        "base_asset": to_asset,
        "quote_asset": from_asset,
        "side": BrokerTrade.Side.BUY,
        "price": abs(from_amount) / abs(to_amount),
        "quantity": abs(to_amount),
        "fee": Decimal("0"),
        "fee_asset": "",
        "timestamp": _timestamp_to_dt(record.get("createTime") or record.get("timestamp")),
        "raw": record,
    }
    _, created = BrokerTrade.objects.update_or_create(
        source=BrokerTrade.Source.BINANCE_API,
        trade_id=trade_id,
        defaults=defaults,
    )
    if created:
        stats.new_trades += 1
    else:
        stats.updated_trades += 1


def _record_binance_earn_income(
    *,
    credential: BrokerCredential,
    record: dict[str, Any],
    stats: SyncStats,
) -> None:
    asset = str(record.get("asset") or record.get("rewardAsset") or "USDC").upper()
    amount = _to_decimal(
        record.get("rewards") or record.get("amount") or record.get("totalRewardAmount")
    )
    timestamp = _timestamp_to_dt(
        record.get("time")
        or record.get("createTime")
        or record.get("timestamp")
        or record.get("rewardTime")
    )
    lookup = {
        "source": IncomeEvent.Source.BINANCE_EARN_API,
        "income_type": IncomeEvent.IncomeType.BINANCE_EARN,
        "asset": asset,
        "amount": amount,
        "timestamp": timestamp,
    }
    defaults = {
        "credential": credential,
        "description": "Binance Earn",
        "raw": record,
    }
    _, created = upsert_income_event_dedup(lookup=lookup, defaults=defaults)
    if created:
        stats.new_income_events += 1
    else:
        stats.updated_income_events += 1


def _record_binance_pay_trade(
    *,
    credential: BrokerCredential,
    record: dict[str, Any],
    stats: SyncStats,
) -> None:
    fiat_asset = str(
        record.get("currency") or record.get("sourceAsset") or record.get("quoteAsset") or "USDC"
    ).upper()
    crypto_asset = str(
        record.get("fundsDetail", {}).get("currency")
        if isinstance(record.get("fundsDetail"), dict)
        else record.get("targetAsset") or record.get("baseAsset") or "BTC"
    ).upper()
    quote_amount = _to_decimal(
        record.get("amount") or record.get("sourceAmount") or record.get("totalAmount")
    )
    quantity = _to_decimal(
        record.get("obtainAmount")
        or (
            record.get("fundsDetail", {}) if isinstance(record.get("fundsDetail"), dict) else {}
        ).get("amount")
        or record.get("quantity")
        or record.get("targetAmount")
    )
    fee_amount = _to_decimal(record.get("fee") or record.get("commission"))
    if quantity <= 0:
        return
    trade_id = str(record.get("orderId") or record.get("transactionId") or record.get("id"))
    if not trade_id:
        trade_id = deterministic_id(
            record.get("transactionTime"),
            record.get("transactionType"),
            crypto_asset,
            quantity,
        )
    defaults = {
        "credential": credential,
        "symbol": f"{crypto_asset}{fiat_asset}",
        "base_asset": crypto_asset,
        "quote_asset": fiat_asset,
        "side": BrokerTrade.Side.BUY,
        "price": abs(quote_amount) / abs(quantity),
        "quantity": abs(quantity),
        "fee": abs(fee_amount),
        "fee_asset": crypto_asset,
        "timestamp": _timestamp_to_dt(record.get("transactionTime") or record.get("timestamp")),
        "raw": record,
    }
    _, created = BrokerTrade.objects.update_or_create(
        source=BrokerTrade.Source.BINANCE_API,
        trade_id=trade_id,
        defaults=defaults,
    )
    if created:
        stats.new_trades += 1
    else:
        stats.updated_trades += 1


def sync_binance(*, credential: BrokerCredential, year: int) -> dict[str, Any]:
    stats = SyncStats()
    client = BinanceClient(
        api_key=credential.api_key,
        api_secret=decrypt(bytes(credential.api_secret_encrypted)),
    )
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000) - 1

    try:
        convert_rows = client.get_convert_history(start_ms=start_ms, end_ms=end_ms)
        for row in convert_rows:
            _record_binance_convert_trade(credential=credential, record=row, stats=stats)
    except BinanceApiError as exc:
        stats.gaps.append({"source": "convert", "reason": str(exc), "code": exc.code or ""})

    earn_assets = [
        item.strip().upper()
        for item in os.getenv("BINANCE_EARN_ASSETS", "USDT,USDC,BTC,ETH").split(",")
        if item.strip()
    ]
    for asset in earn_assets:
        try:
            rewards = client.get_earn_flexible_rewards(
                asset=asset,
                start_ms=start_ms,
                end_ms=end_ms,
            )
            for reward in rewards:
                _record_binance_earn_income(credential=credential, record=reward, stats=stats)
        except BinanceApiError as exc:
            stats.gaps.append(
                {"source": f"earn:{asset}", "reason": str(exc), "code": exc.code or ""}
            )

    try:
        transactions = client.get_pay_transactions(start_ms=start_ms, end_ms=end_ms)
        for record in transactions:
            _record_binance_pay_trade(credential=credential, record=record, stats=stats)
    except BinanceApiError as exc:
        stats.gaps.append(
            {"source": "pay_transactions", "reason": str(exc), "code": exc.code or ""}
        )

    try:
        referral_rows = client.get_referral_rebates(start_ms=start_ms, end_ms=end_ms)
        for row in referral_rows:
            asset = str(row.get("asset") or row.get("rebateAsset") or "USDC").upper()
            amount = _to_decimal(row.get("amount") or row.get("rebateAmount"))
            timestamp = _timestamp_to_dt(row.get("updateTime") or row.get("time"))
            lookup = {
                "source": IncomeEvent.Source.BINANCE_REFERRAL_CSV,
                "income_type": IncomeEvent.IncomeType.COMMISSION,
                "asset": asset,
                "amount": amount,
                "timestamp": timestamp,
            }
            defaults = {
                "credential": credential,
                "description": "Binance Referral",
                "raw": row,
            }
            _, created = upsert_income_event_dedup(lookup=lookup, defaults=defaults)
            if created:
                stats.new_income_events += 1
            else:
                stats.updated_income_events += 1
    except BinanceApiError as exc:
        stats.gaps.append(
            {"source": "rebate_tax_query", "reason": str(exc), "code": exc.code or ""}
        )

    payload = stats.to_dict()
    credential.last_sync_at = django_timezone.now()
    credential.last_sync_stats = payload
    credential.last_sync_gaps = payload["gaps"]
    credential.save(
        update_fields=["last_sync_at", "last_sync_stats", "last_sync_gaps", "updated_at"]
    )
    return payload


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
    balances: list[dict[str, Any]] = []
    try:
        balances = client.get_balances()
    except PionexApiError as exc:
        stats.gaps.append({"source": "balances", "reason": str(exc), "code": exc.code or ""})

    symbols = _discover_spot_symbols(credential=credential, balances=balances)
    for symbol in symbols:
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

    dual_bases = _discover_dual_bases(balances=balances)
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

    discovered_bots = _discover_spot_grid_bots(client, stats)
    env_bot_ids = {
        value.strip() for value in os.getenv("PIONEX_BOT_IDS", "").split(",") if value.strip()
    }
    for bot_id, payload in sorted(discovered_bots.items()):
        bot_result = _upsert_bot_result(
            credential=credential,
            bot_id=bot_id,
            payload=payload,
            start_ms=start_ms,
            end_ms=end_ms,
            stats=stats,
        )
        try:
            bot_fills = client.get_bot_spot_grid_orders(
                bot_id=bot_id,
                start_ms=start_ms,
                end_ms=end_ms,
                limit=100,
            )
            symbol_fallback = str(
                payload.get("symbol") or f"{bot_result.base_asset}_{bot_result.quote_asset}"
            )
            for fill in bot_fills:
                if isinstance(fill, dict):
                    _record_trade_fill(
                        credential=credential,
                        fill=fill,
                        symbol_fallback=symbol_fallback,
                        stats=stats,
                        source=str(BrokerTrade.Source.PIONEX_BOT_API),
                        bot_result=bot_result,
                    )
        except PionexApiError as exc:
            stats.gaps.append(
                {"source": f"bot_fills:{bot_id}", "reason": str(exc), "code": exc.code or ""}
            )

    for bot_id in sorted(env_bot_ids - set(discovered_bots.keys())):
        try:
            summary = client.get_bot_summary(bot_id=bot_id)
            bot_result = _upsert_bot_result(
                credential=credential,
                bot_id=bot_id,
                payload=summary,
                start_ms=start_ms,
                end_ms=end_ms,
                stats=stats,
            )
            bot_fills = client.get_bot_spot_grid_orders(
                bot_id=bot_id,
                start_ms=start_ms,
                end_ms=end_ms,
                limit=100,
            )
            symbol_fallback = str(
                summary.get("symbol") or f"{bot_result.base_asset}_{bot_result.quote_asset}"
            )
            for fill in bot_fills:
                if isinstance(fill, dict):
                    _record_trade_fill(
                        credential=credential,
                        fill=fill,
                        symbol_fallback=symbol_fallback,
                        stats=stats,
                        source=str(BrokerTrade.Source.PIONEX_BOT_API),
                        bot_result=bot_result,
                    )
        except PionexApiError as exc:
            stats.gaps.append(
                {"source": f"bot:{bot_id}", "reason": str(exc), "code": exc.code or ""}
            )

    if balances:
        _compute_balance_reconciliation(
            credential=credential,
            balances=balances,
            stats=stats,
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
    if credential.broker == BrokerCredential.Broker.BINANCE:
        return sync_binance(credential=credential, year=year)
    raise ValueError(f"Broker no soportado en esta fase: {credential.broker}")
