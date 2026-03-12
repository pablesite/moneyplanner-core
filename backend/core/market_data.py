from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.utils import timezone

from .models import FxRate

logger = logging.getLogger(__name__)

FRANKFURTER_API_URL = "https://api.frankfurter.app"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
SUPPORTED_CRYPTO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
}


class MarketDataSyncError(RuntimeError):
    pass


def _fetch_json(*, url: str, timeout: int = 30) -> dict:
    try:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "moneyplanner-core/1.0",
            },
        )
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise MarketDataSyncError(f"Unable to fetch market data from {url}.") from exc


def _normalize_date_range(*, start_date: date | None, end_date: date | None) -> tuple[date, date]:
    resolved_end_date = end_date or timezone.localdate()
    resolved_start_date = start_date or resolved_end_date
    if resolved_end_date < resolved_start_date:
        raise MarketDataSyncError("end_date must be equal to or later than start_date.")
    return resolved_start_date, resolved_end_date


def _upsert_fx_rows(
    *, from_currency: str, to_currency: str, rows: Iterable[tuple[date, Decimal]]
) -> int:
    created_or_updated = 0
    for rate_date, rate in rows:
        FxRate.objects.update_or_create(
            from_currency=from_currency,
            to_currency=to_currency,
            rate_date=rate_date,
            defaults={"rate": rate},
        )
        created_or_updated += 1
    return created_or_updated


def sync_fiat_history(
    *, from_currency: str, to_currency: str, start_date: date, end_date: date
) -> int:
    if from_currency == to_currency:
        return 0

    query = urlencode({"from": from_currency, "to": to_currency})
    url = f"{FRANKFURTER_API_URL}/{start_date.isoformat()}..{end_date.isoformat()}?{query}"
    payload = _fetch_json(url=url)
    raw_rates = payload.get("rates") or {}
    rows = []
    for raw_date, rate_map in sorted(raw_rates.items()):
        rate = rate_map.get(to_currency)
        if rate in (None, ""):
            continue
        rows.append((date.fromisoformat(raw_date), Decimal(str(rate))))
    return _upsert_fx_rows(from_currency=from_currency, to_currency=to_currency, rows=rows)


def _iter_crypto_range_chunks(
    *, start_date: date, end_date: date, chunk_days: int = 90
) -> Iterable[tuple[date, date]]:
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end_date)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def sync_crypto_history(
    *, from_currency: str, to_currency: str, start_date: date, end_date: date
) -> int:
    coin_id = SUPPORTED_CRYPTO_IDS.get(from_currency.upper())
    if not coin_id:
        return 0

    daily_prices: dict[date, Decimal] = {}
    for chunk_start, chunk_end in _iter_crypto_range_chunks(
        start_date=start_date, end_date=end_date
    ):
        from_ts = int(datetime.combine(chunk_start, datetime.min.time(), tzinfo=UTC).timestamp())
        to_ts = (
            int(
                datetime.combine(
                    chunk_end + timedelta(days=1), datetime.min.time(), tzinfo=UTC
                ).timestamp()
            )
            - 1
        )
        query = urlencode(
            {
                "vs_currency": to_currency.lower(),
                "from": from_ts,
                "to": to_ts,
            }
        )
        url = f"{COINGECKO_API_URL}/coins/{coin_id}/market_chart/range?{query}"
        payload = _fetch_json(url=url)
        prices = payload.get("prices") or []
        grouped: dict[date, list[tuple[int, Decimal]]] = defaultdict(list)
        for timestamp_ms, raw_price in prices:
            point_date = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).date()
            grouped[point_date].append((int(timestamp_ms), Decimal(str(raw_price))))
        for point_date, entries in grouped.items():
            if point_date < chunk_start or point_date > chunk_end:
                continue
            _, last_price = max(entries, key=lambda row: row[0])
            daily_prices[point_date] = last_price

    rows = sorted(daily_prices.items(), key=lambda row: row[0])
    return _upsert_fx_rows(from_currency=from_currency, to_currency=to_currency, rows=rows)


def sync_market_history(
    *, from_currency: str, to_currency: str, start_date: date | None, end_date: date | None = None
) -> int:
    normalized_from = str(from_currency or "").upper().strip()
    normalized_to = str(to_currency or "").upper().strip()
    if not normalized_from or not normalized_to or normalized_from == normalized_to:
        return 0

    resolved_start_date, resolved_end_date = _normalize_date_range(
        start_date=start_date,
        end_date=end_date,
    )

    if normalized_from in SUPPORTED_CRYPTO_IDS:
        return sync_crypto_history(
            from_currency=normalized_from,
            to_currency=normalized_to,
            start_date=resolved_start_date,
            end_date=resolved_end_date,
        )

    return sync_fiat_history(
        from_currency=normalized_from,
        to_currency=normalized_to,
        start_date=resolved_start_date,
        end_date=resolved_end_date,
    )


def ensure_market_history(
    *, from_currency: str, to_currency: str, start_date: date | None, end_date: date | None = None
) -> int:
    normalized_from = str(from_currency or "").upper().strip()
    normalized_to = str(to_currency or "").upper().strip()
    if (
        not normalized_from
        or not normalized_to
        or normalized_from == normalized_to
        or start_date is None
    ):
        return 0

    earliest_row = (
        FxRate.objects.filter(from_currency=normalized_from, to_currency=normalized_to)
        .order_by("rate_date")
        .first()
    )
    if earliest_row and earliest_row.rate_date <= start_date:
        return 0

    sync_start_date = start_date
    if earliest_row is not None:
        sync_end_date = earliest_row.rate_date - timedelta(days=1)
    else:
        sync_end_date = end_date or timezone.localdate()

    if sync_end_date < sync_start_date:
        return 0

    return sync_market_history(
        from_currency=normalized_from,
        to_currency=normalized_to,
        start_date=sync_start_date,
        end_date=sync_end_date,
    )


def ensure_market_history_safe(
    *, from_currency: str, to_currency: str, start_date: date | None, end_date: date | None = None
) -> int:
    try:
        return ensure_market_history(
            from_currency=from_currency,
            to_currency=to_currency,
            start_date=start_date,
            end_date=end_date,
        )
    except MarketDataSyncError:
        logger.warning(
            "Unable to backfill FX history for %s->%s from %s.",
            from_currency,
            to_currency,
            start_date,
            exc_info=True,
        )
        return 0
