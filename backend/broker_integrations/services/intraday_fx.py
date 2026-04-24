from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from ..models import MarketRateSnapshot
from .eur_converter import EurConverter


class IntradayFxError(Exception):
    pass


class IntradayFxService:
    BINANCE_BASE_URL = "https://api.binance.com"
    MAX_KLINES_PER_REQUEST = 1000

    def __init__(self) -> None:
        self._daily_converter = EurConverter()

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _minute_floor(value: datetime) -> datetime:
        normalized = IntradayFxService._to_utc(value)
        return normalized.replace(second=0, microsecond=0)

    @staticmethod
    def _to_ms(value: datetime) -> int:
        return int(IntradayFxService._to_utc(value).timestamp() * 1000)

    @staticmethod
    def _normalize_asset(value: str) -> str:
        return (value or "").strip().upper()

    def _request_klines(
        self,
        *,
        pair: str,
        interval: str,
        start_ms: int,
        end_ms: int,
        limit: int = MAX_KLINES_PER_REQUEST,
    ) -> list[list[Any]]:
        query = urllib.parse.urlencode(
            {
                "symbol": pair,
                "interval": interval,
                "startTime": str(start_ms),
                "endTime": str(end_ms),
                "limit": str(limit),
            }
        )
        url = f"{self.BINANCE_BASE_URL}/api/v3/klines?{query}"
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": "moneyplanner-core/intraday-fx",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8", errors="ignore")
                data = json.loads(payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise IntradayFxError(f"Binance klines HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise IntradayFxError(f"Binance klines request error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise IntradayFxError("Invalid JSON payload from Binance klines") from exc
        if not isinstance(data, list):
            raise IntradayFxError("Unexpected Binance klines payload.")
        return [row for row in data if isinstance(row, list)]

    def fetch_klines(
        self,
        *,
        pair: str,
        start_ms: int,
        end_ms: int,
        interval: str = MarketRateSnapshot.Interval.MINUTE_1,
    ) -> list[dict[str, Any]]:
        all_rows: list[dict[str, Any]] = []
        cursor = start_ms
        while cursor <= end_ms:
            rows = self._request_klines(
                pair=pair,
                interval=interval,
                start_ms=cursor,
                end_ms=end_ms,
                limit=self.MAX_KLINES_PER_REQUEST,
            )
            if not rows:
                break
            for row in rows:
                if len(row) < 6:
                    continue
                all_rows.append(
                    {
                        "open_time_ms": int(row[0]),
                        "close": Decimal(str(row[4])),
                        "high": Decimal(str(row[2])),
                        "low": Decimal(str(row[3])),
                        "raw": row,
                    }
                )
            last_open_time_ms = int(rows[-1][0])
            if len(rows) < self.MAX_KLINES_PER_REQUEST:
                break
            cursor = last_open_time_ms + 60_000
        return all_rows

    def ensure_range(
        self,
        *,
        pair: str,
        start_ms: int,
        end_ms: int,
        interval: str = MarketRateSnapshot.Interval.MINUTE_1,
    ) -> None:
        rows = self.fetch_klines(pair=pair, start_ms=start_ms, end_ms=end_ms, interval=interval)
        for row in rows:
            open_time = datetime.fromtimestamp(row["open_time_ms"] / 1000, tz=timezone.utc)
            MarketRateSnapshot.objects.update_or_create(
                pair=pair,
                interval=interval,
                open_time=open_time,
                defaults={
                    "close": row["close"],
                    "high": row["high"],
                    "low": row["low"],
                    "source": "binance_klines",
                    "raw": row["raw"],
                },
            )

    def _lookup_snapshot(
        self,
        *,
        pair: str,
        minute: datetime,
        interval: str = MarketRateSnapshot.Interval.MINUTE_1,
    ) -> Decimal | None:
        row = MarketRateSnapshot.objects.filter(
            pair=pair,
            interval=interval,
            open_time=minute,
        ).first()
        return Decimal(row.close) if row else None

    def _fetch_and_lookup_minute(self, *, pair: str, minute: datetime) -> Decimal | None:
        start_ms = self._to_ms(minute)
        end_ms = self._to_ms(minute + timedelta(minutes=1)) - 1
        self.ensure_range(pair=pair, start_ms=start_ms, end_ms=end_ms, interval="1m")
        return self._lookup_snapshot(pair=pair, minute=minute, interval="1m")

    def _daily_fallback(self, *, timestamp: datetime, asset: str) -> tuple[Decimal, str]:
        rate = self._daily_converter.get_eur_rate(
            trade_date=self._to_utc(timestamp).date(),
            asset=asset,
        )
        return rate, "daily_fallback"

    def get_rate_at(self, *, timestamp: datetime, asset: str) -> tuple[Decimal, str]:
        normalized_asset = self._normalize_asset(asset)
        if not normalized_asset or normalized_asset == "EUR":
            return Decimal("1"), "identity"
        if normalized_asset in {"USD", "USDT", "USDC"}:
            return self._daily_fallback(timestamp=timestamp, asset=normalized_asset)

        minute = self._minute_floor(timestamp)
        direct_pair = f"{normalized_asset}EUR"
        direct_rate = self._lookup_snapshot(pair=direct_pair, minute=minute, interval="1m")
        if direct_rate is None:
            direct_rate = self._fetch_and_lookup_minute(pair=direct_pair, minute=minute)
        if direct_rate is not None:
            return direct_rate, "binance_klines_1m"

        via_usdt_pair = f"{normalized_asset}USDT"
        via_usdt_rate = self._lookup_snapshot(pair=via_usdt_pair, minute=minute, interval="1m")
        if via_usdt_rate is None:
            via_usdt_rate = self._fetch_and_lookup_minute(pair=via_usdt_pair, minute=minute)
        if via_usdt_rate is not None:
            usdt_to_eur = self._daily_converter.get_eur_rate(
                trade_date=self._to_utc(timestamp).date(),
                asset="USDT",
            )
            return via_usdt_rate * usdt_to_eur, "binance_klines_1m_via_usdt"

        return self._daily_fallback(timestamp=timestamp, asset=normalized_asset)


def get_rate_at(*, timestamp: datetime, asset: str) -> tuple[Decimal, str]:
    service = IntradayFxService()
    return service.get_rate_at(timestamp=timestamp, asset=asset)


def prefetch_pairs_for_trades(*, trades: list[dict[str, datetime | str]]) -> None:
    if not trades:
        return
    service = IntradayFxService()
    minute_groups: dict[str, tuple[datetime, datetime]] = {}
    for entry in trades:
        timestamp = entry.get("timestamp")
        quote_asset = str(entry.get("quote_asset") or "").strip().upper()
        if not isinstance(timestamp, datetime) or not quote_asset:
            continue
        minute = service._minute_floor(timestamp)
        direct_pair = f"{quote_asset}EUR"
        start, end = minute_groups.get(direct_pair, (minute, minute))
        minute_groups[direct_pair] = (min(start, minute), max(end, minute))
        if quote_asset != "EUR":
            via_pair = f"{quote_asset}USDT"
            start_via, end_via = minute_groups.get(via_pair, (minute, minute))
            minute_groups[via_pair] = (min(start_via, minute), max(end_via, minute))
    for pair, (start_minute, end_minute) in minute_groups.items():
        start_ms = service._to_ms(start_minute)
        end_ms = service._to_ms(end_minute + timedelta(minutes=1)) - 1
        try:
            service.ensure_range(pair=pair, start_ms=start_ms, end_ms=end_ms, interval="1m")
        except IntradayFxError:
            # Best-effort prefetch; get_rate_at handles fallbacks and fine-grained fetches.
            continue
