from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.utils import timezone

from accounts.models import UserSettings
from net_worth.models import (
    Asset,
    AssetValuation,
    InvestmentAssetEvent,
    Liability,
    LiabilityEvent,
    LiabilityValuation,
    LiquidityAssetEvent,
)

from .models import FxRate, InflationIndex, MarketDataSyncState

logger = logging.getLogger(__name__)

FRANKFURTER_API_URL = "https://api.frankfurter.app"
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
CRYPTOCOMPARE_API_URL = "https://min-api.cryptocompare.com/data/v2"
INE_API_URL = "https://servicios.ine.es/wstempus/js/ES"
INE_GENERAL_INDEX_TABLE_ID = 24078

SUPPORTED_CRYPTO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
}

INE_REGION_NAME_TO_CODE = {
    "Nacional": "ES",
    "Andalucía": "ES-AN",
    "Aragón": "ES-AR",
    "Asturias, Principado de": "ES-AS",
    "Balears, Illes": "ES-IB",
    "Canarias": "ES-CN",
    "Cantabria": "ES-CB",
    "Castilla y León": "ES-CL",
    "Castilla - La Mancha": "ES-CM",
    "Cataluña": "ES-CT",
    "Comunitat Valenciana": "ES-VC",
    "Extremadura": "ES-EX",
    "Galicia": "ES-GA",
    "Madrid, Comunidad de": "ES-MD",
    "Murcia, Región de": "ES-MC",
    "Navarra, Comunidad Foral de": "ES-NC",
    "País Vasco": "ES-PV",
    "Rioja, La": "ES-RI",
    "Ceuta": "ES-CE",
    "Melilla": "ES-ML",
}


class MarketDataSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyncScopeRequest:
    dataset: str
    scope: str
    required_start_date: date | None


def _fetch_json(*, url: str, timeout: int = 30) -> Any:
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


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _normalize_month_range(*, start_date: date | None, end_date: date | None) -> tuple[date, date]:
    resolved_end = _month_start(end_date or timezone.localdate())
    resolved_start = _month_start(start_date or resolved_end)
    if resolved_end < resolved_start:
        raise MarketDataSyncError("end_date must be equal to or later than start_date.")
    return resolved_start, resolved_end


def _upsert_fx_rows(
    *,
    from_currency: str,
    to_currency: str,
    rows: Iterable[tuple[date, Decimal]],
    source: str,
    source_key: str,
    managed_by_system: bool = True,
) -> int:
    synced_at = timezone.now()
    created_or_updated = 0
    for rate_date, rate in rows:
        FxRate.objects.update_or_create(
            from_currency=from_currency,
            to_currency=to_currency,
            rate_date=rate_date,
            defaults={
                "rate": rate,
                "source": source,
                "source_key": source_key,
                "managed_by_system": managed_by_system,
                "last_synced_at": synced_at,
            },
        )
        created_or_updated += 1
    return created_or_updated


def _upsert_inflation_rows(
    *,
    region: str,
    rows: Iterable[tuple[date, Decimal]],
    source: str,
    source_key: str,
    managed_by_system: bool = True,
) -> int:
    synced_at = timezone.now()
    created_or_updated = 0
    for period, index_value in rows:
        InflationIndex.objects.update_or_create(
            region=region,
            period=period,
            defaults={
                "index": index_value,
                "source": source,
                "source_key": source_key,
                "managed_by_system": managed_by_system,
                "last_synced_at": synced_at,
            },
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
    return _upsert_fx_rows(
        from_currency=from_currency,
        to_currency=to_currency,
        rows=rows,
        source="frankfurter",
        source_key=f"{from_currency}->{to_currency}",
    )


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

    try:
        rows = _fetch_crypto_rows_coingecko(
            coin_id=coin_id,
            start_date=start_date,
            end_date=end_date,
            to_currency=to_currency,
        )
        source = "coingecko"
    except MarketDataSyncError:
        # Fallback provider for long historical ranges where CoinGecko may reject
        # anonymous requests. We keep this transparent for sync callers.
        logger.warning(
            "CoinGecko crypto sync failed for %s->%s. Falling back to CryptoCompare.",
            from_currency,
            to_currency,
            exc_info=True,
        )
        rows = _fetch_crypto_rows_cryptocompare(
            from_currency=from_currency,
            to_currency=to_currency,
            start_date=start_date,
            end_date=end_date,
        )
        source = "cryptocompare"

    return _upsert_fx_rows(
        from_currency=from_currency,
        to_currency=to_currency,
        rows=rows,
        source=source,
        source_key=f"{from_currency}->{to_currency}",
    )


def _fetch_crypto_rows_coingecko(
    *, coin_id: str, to_currency: str, start_date: date, end_date: date
) -> list[tuple[date, Decimal]]:
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

    return sorted(daily_prices.items(), key=lambda row: row[0])


def _fetch_crypto_rows_cryptocompare(
    *, from_currency: str, to_currency: str, start_date: date, end_date: date
) -> list[tuple[date, Decimal]]:
    # histoday supports up to 2000 daily points per request.
    chunk_days = 2000
    daily_prices: dict[date, Decimal] = {}
    for chunk_start, chunk_end in _iter_crypto_range_chunks(
        start_date=start_date, end_date=end_date, chunk_days=chunk_days
    ):
        to_ts = (
            int(
                datetime.combine(
                    chunk_end + timedelta(days=1), datetime.min.time(), tzinfo=UTC
                ).timestamp()
            )
            - 1
        )
        limit = max(1, (chunk_end - chunk_start).days)
        query = urlencode(
            {
                "fsym": from_currency.upper(),
                "tsym": to_currency.upper(),
                "limit": limit,
                "toTs": to_ts,
            }
        )
        url = f"{CRYPTOCOMPARE_API_URL}/histoday?{query}"
        payload = _fetch_json(url=url)
        data_payload = payload.get("Data") if isinstance(payload, dict) else None
        points = data_payload.get("Data") if isinstance(data_payload, dict) else None
        if not isinstance(points, list):
            raise MarketDataSyncError(
                f"Unexpected CryptoCompare response for {from_currency}->{to_currency}."
            )
        for point in points:
            timestamp = point.get("time")
            close_price = point.get("close")
            if timestamp in (None, "") or close_price in (None, ""):
                continue
            point_date = datetime.fromtimestamp(int(timestamp), tz=UTC).date()
            if point_date < chunk_start or point_date > chunk_end:
                continue
            daily_prices[point_date] = Decimal(str(close_price))

    return sorted(daily_prices.items(), key=lambda row: row[0])


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


def _extract_ine_region_name(series: dict[str, Any]) -> str | None:
    for metadata in series.get("MetaData") or []:
        variable = str(metadata.get("T3_Variable") or "")
        if variable in {"Totales Territoriales", "Comunidades y Ciudades Autónomas"}:
            return str(metadata.get("Nombre") or "").strip() or None
    name = str(series.get("Nombre") or "")
    if not name:
        return None
    return name.split(".")[0].strip() or None


def _fetch_ine_general_index_series() -> dict[str, list[tuple[date, Decimal]]]:
    payload = _fetch_json(url=f"{INE_API_URL}/DATOS_TABLA/{INE_GENERAL_INDEX_TABLE_ID}?tip=AM")
    if not isinstance(payload, list):
        raise MarketDataSyncError("Unexpected INE response for inflation data.")

    grouped: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    for series in payload:
        region_name = _extract_ine_region_name(series)
        region_code = INE_REGION_NAME_TO_CODE.get(region_name or "")
        if not region_code:
            continue
        for row in series.get("Data") or []:
            raw_value = row.get("Valor")
            raw_date = str(row.get("Fecha") or "")
            if raw_value in (None, "") or not raw_date:
                continue
            grouped[region_code].append(
                (date.fromisoformat(raw_date[:10]), Decimal(str(raw_value)))
            )

    return {
        region: sorted({period: value for period, value in rows}.items(), key=lambda item: item[0])
        for region, rows in grouped.items()
    }


def sync_inflation_history(
    *, region: str, start_date: date | None, end_date: date | None = None
) -> int:
    normalized_region = str(region or "").strip().upper()
    if not normalized_region:
        return 0

    resolved_start_date, resolved_end_date = _normalize_month_range(
        start_date=start_date,
        end_date=end_date,
    )
    rows_by_region = _fetch_ine_general_index_series()
    region_rows = rows_by_region.get(normalized_region, [])
    rows = [
        (period, index_value)
        for period, index_value in region_rows
        if resolved_start_date <= period <= resolved_end_date
    ]
    return _upsert_inflation_rows(
        region=normalized_region,
        rows=rows,
        source="ine",
        source_key=f"ine:{normalized_region}",
    )


def _collect_relevant_position_dates() -> dict[str, date]:
    earliest_by_currency: dict[str, date] = {}
    global_dates: list[date] = []

    def register(currency: str, point_date: date | None) -> None:
        normalized_currency = str(currency or "").strip().upper()
        if point_date is None:
            return
        global_dates.append(point_date)
        if not normalized_currency:
            return
        current = earliest_by_currency.get(normalized_currency)
        if current is None or point_date < current:
            earliest_by_currency[normalized_currency] = point_date

    for asset in Asset.objects.all().only("currency", "start_date"):
        register(asset.currency, asset.start_date)
    for liability in Liability.objects.all().only("currency", "start_date"):
        register(liability.currency, liability.start_date)
    for valuation in AssetValuation.objects.select_related("asset").all():
        register(valuation.asset.currency, valuation.valuation_date)
    for valuation in LiabilityValuation.objects.select_related("liability").all():
        register(valuation.liability.currency, valuation.valuation_date)
    for event in InvestmentAssetEvent.objects.select_related("asset").all():
        register(event.asset.currency, event.event_date)
    for event in LiquidityAssetEvent.objects.select_related("asset").all():
        register(event.asset.currency, event.event_date)
    for event in LiabilityEvent.objects.select_related("liability").all():
        register(event.liability.currency, event.event_date)

    if global_dates:
        earliest_by_currency["__global__"] = min(global_dates)
    return earliest_by_currency


_FX_DEFAULT_HISTORY_YEARS = 5


def _build_fx_scope_requests(
    *, history_floor_years: int | None = _FX_DEFAULT_HISTORY_YEARS
) -> list[SyncScopeRequest]:
    earliest_by_currency = _collect_relevant_position_dates()
    global_start = earliest_by_currency.get("__global__")
    if global_start is None:
        return []

    floor_date = None
    if history_floor_years is not None:
        # Guarantee at least N years of history for every needed pair, regardless of
        # when the earliest asset was created. This avoids a 24-h gap when a user adds
        # a foreign-currency asset for the first time.
        floor_date = date.today() - timedelta(days=365 * history_floor_years)

    base_currencies = {
        str(value or "").strip().upper()
        for value in UserSettings.objects.values_list("base_currency", flat=True)
        if str(value or "").strip()
    }
    if not base_currencies:
        base_currencies = {"EUR"}

    source_currencies = {
        currency
        for currency in earliest_by_currency.keys()
        if currency and currency != "__global__"
    }
    # Provider capability: crypto history is supported only when the source
    # currency is crypto. For fiat->crypto needs, we sync the inverse pair
    # (crypto->fiat) and conversion uses inverse lookup.
    crypto_codes = set(SUPPORTED_CRYPTO_IDS.keys())
    requests_by_scope: dict[str, date] = {}
    for quote_currency in sorted(base_currencies):
        for from_currency in sorted(source_currencies):
            if from_currency == quote_currency:
                continue
            asset_start = earliest_by_currency.get(from_currency, global_start)
            required_start_date = (
                min(asset_start, floor_date) if floor_date is not None else asset_start
            )
            if from_currency not in crypto_codes and quote_currency in crypto_codes:
                scope = f"{quote_currency}->{from_currency}"
            else:
                scope = f"{from_currency}->{quote_currency}"

            current_start = requests_by_scope.get(scope)
            if current_start is None or required_start_date < current_start:
                requests_by_scope[scope] = required_start_date

    return [
        SyncScopeRequest(
            dataset=cast(str, MarketDataSyncState.Dataset.FX),
            scope=scope,
            required_start_date=required_start_date,
        )
        for scope, required_start_date in sorted(requests_by_scope.items())
    ]


def _build_inflation_scope_requests() -> list[SyncScopeRequest]:
    earliest_by_currency = _collect_relevant_position_dates()
    global_start = earliest_by_currency.get("__global__")
    if global_start is None:
        return []

    # Always sync all supported Spanish regions so that when a user changes their
    # inflation_region in settings, data is already available without waiting for
    # the next sync cycle.
    regions = {choice[0] for choice in InflationIndex.Region.choices}
    return [
        SyncScopeRequest(
            dataset=cast(str, MarketDataSyncState.Dataset.INFLATION),
            scope=region,
            required_start_date=_month_start(global_start),
        )
        for region in sorted(regions)
    ]


class MarketDataProvider(ABC):
    dataset: str
    source: str

    @abstractmethod
    def build_scope_requests(self) -> list[SyncScopeRequest]:
        raise NotImplementedError

    @abstractmethod
    def sync_scope(
        self, *, scope: str, required_start_date: date | None, mode: str, today: date
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_coverage_bounds(self, *, scope: str) -> tuple[date | None, date | None]:
        raise NotImplementedError


class FxMarketDataProvider(MarketDataProvider):
    dataset = MarketDataSyncState.Dataset.FX
    source = "fx_provider"

    def __init__(self, *, history_floor_years: int | None = _FX_DEFAULT_HISTORY_YEARS):
        self.history_floor_years = history_floor_years

    def build_scope_requests(self) -> list[SyncScopeRequest]:
        return _build_fx_scope_requests(history_floor_years=self.history_floor_years)

    def get_coverage_bounds(self, *, scope: str) -> tuple[date | None, date | None]:
        from_currency, to_currency = scope.split("->", 1)
        rows = FxRate.objects.filter(from_currency=from_currency, to_currency=to_currency)
        earliest = rows.order_by("rate_date").values_list("rate_date", flat=True).first()
        latest = rows.order_by("-rate_date").values_list("rate_date", flat=True).first()
        return earliest, latest

    def sync_scope(
        self, *, scope: str, required_start_date: date | None, mode: str, today: date
    ) -> int:
        from_currency, to_currency = scope.split("->", 1)
        if required_start_date is None:
            return 0

        earliest, latest = self.get_coverage_bounds(scope=scope)
        inserted = 0
        if mode == "refresh":
            start_date = latest + timedelta(days=1) if latest else required_start_date
            if start_date <= today:
                inserted += sync_market_history(
                    from_currency=from_currency,
                    to_currency=to_currency,
                    start_date=start_date,
                    end_date=today,
                )
            return inserted

        if earliest is None or latest is None:
            return sync_market_history(
                from_currency=from_currency,
                to_currency=to_currency,
                start_date=required_start_date,
                end_date=today,
            )

        if required_start_date < earliest:
            inserted += sync_market_history(
                from_currency=from_currency,
                to_currency=to_currency,
                start_date=required_start_date,
                end_date=earliest - timedelta(days=1),
            )
        if latest < today:
            inserted += sync_market_history(
                from_currency=from_currency,
                to_currency=to_currency,
                start_date=latest + timedelta(days=1),
                end_date=today,
            )
        return inserted


class InflationMarketDataProvider(MarketDataProvider):
    dataset = MarketDataSyncState.Dataset.INFLATION
    source = "ine"

    def build_scope_requests(self) -> list[SyncScopeRequest]:
        return _build_inflation_scope_requests()

    def get_coverage_bounds(self, *, scope: str) -> tuple[date | None, date | None]:
        rows = InflationIndex.objects.filter(region=scope)
        earliest = rows.order_by("period").values_list("period", flat=True).first()
        latest = rows.order_by("-period").values_list("period", flat=True).first()
        return earliest, latest

    def sync_scope(
        self, *, scope: str, required_start_date: date | None, mode: str, today: date
    ) -> int:
        if required_start_date is None:
            return 0

        target_end = _month_start(today)
        earliest, latest = self.get_coverage_bounds(scope=scope)
        inserted = 0

        if mode == "refresh":
            start_date = _next_month(latest) if latest else required_start_date
            if start_date <= target_end:
                inserted += sync_inflation_history(
                    region=scope,
                    start_date=start_date,
                    end_date=target_end,
                )
            return inserted

        if earliest is None or latest is None:
            return sync_inflation_history(
                region=scope,
                start_date=required_start_date,
                end_date=target_end,
            )

        if required_start_date < earliest:
            inserted += sync_inflation_history(
                region=scope,
                start_date=required_start_date,
                end_date=earliest,
            )
        if latest < target_end:
            inserted += sync_inflation_history(
                region=scope,
                start_date=_next_month(latest),
                end_date=target_end,
            )

        # Fill internal gaps: non-system-managed rows (interpolated / seed stubs)
        # that the INE should replace. The INE endpoint returns the full series in
        # one HTTP request, so re-fetching the whole range costs a single call.
        has_non_managed = InflationIndex.objects.filter(
            region=scope,
            period__gte=required_start_date,
            period__lte=target_end,
            managed_by_system=False,
        ).exists()
        if has_non_managed:
            inserted += sync_inflation_history(
                region=scope,
                start_date=required_start_date,
                end_date=target_end,
            )

        return inserted


def _get_provider_registry(
    *, fx_history_floor_years: int | None = _FX_DEFAULT_HISTORY_YEARS
) -> dict[str, MarketDataProvider]:
    return {
        cast(str, MarketDataSyncState.Dataset.FX): FxMarketDataProvider(
            history_floor_years=fx_history_floor_years
        ),
        cast(str, MarketDataSyncState.Dataset.INFLATION): InflationMarketDataProvider(),
    }


def sync_market_data(
    *,
    datasets: Iterable[str] | None = None,
    mode: str = "reconcile",
    fx_history_floor_years: int | None = _FX_DEFAULT_HISTORY_YEARS,
) -> dict[str, int]:
    normalized_mode = str(mode or "reconcile").strip().lower()
    if normalized_mode not in {"reconcile", "refresh"}:
        raise MarketDataSyncError("mode must be reconcile or refresh.")

    registry = _get_provider_registry(fx_history_floor_years=fx_history_floor_years)
    dataset_list = [
        str(item).strip().lower() for item in (datasets or registry.keys()) if str(item).strip()
    ]
    if not dataset_list:
        dataset_list = list(registry.keys())

    summary: dict[str, int] = {dataset: 0 for dataset in dataset_list}
    today = timezone.localdate()
    attempted_at = timezone.now()

    for dataset in dataset_list:
        provider = registry.get(dataset)
        if provider is None:
            raise MarketDataSyncError(f"Unsupported dataset '{dataset}'.")

        for request in provider.build_scope_requests():
            state, _ = MarketDataSyncState.objects.get_or_create(
                dataset=request.dataset,
                scope=request.scope,
            )
            state.required_start_date = request.required_start_date
            state.last_attempt_at = attempted_at
            state.source = provider.source
            state.save(
                update_fields=["required_start_date", "last_attempt_at", "source", "updated_at"]
            )

            try:
                summary[dataset] += provider.sync_scope(
                    scope=request.scope,
                    required_start_date=request.required_start_date,
                    mode=normalized_mode,
                    today=today,
                )
                _, latest = provider.get_coverage_bounds(scope=request.scope)
                state.covered_until = latest
                state.last_success_at = timezone.now()
                state.last_error = ""
            except MarketDataSyncError as exc:
                logger.warning(
                    "Market data sync failed for %s/%s.",
                    request.dataset,
                    request.scope,
                    exc_info=True,
                )
                state.last_error = str(exc)
            state.save(
                update_fields=[
                    "covered_until",
                    "last_success_at",
                    "last_error",
                    "updated_at",
                ]
            )

    return summary


def get_market_data_status() -> dict[str, Any]:
    states = list(MarketDataSyncState.objects.all())
    fx_scope_requests = _build_fx_scope_requests()
    valid_fx_scopes = {request.scope for request in fx_scope_requests}
    if valid_fx_scopes:
        fx_states = [
            state
            for state in states
            if state.dataset == MarketDataSyncState.Dataset.FX and state.scope in valid_fx_scopes
        ]
    else:
        fx_states = [state for state in states if state.dataset == MarketDataSyncState.Dataset.FX]

    return {
        "supported_inflation_regions": InflationIndex.supported_regions(),
        "datasets": {
            "fx": {
                "states": [
                    {
                        "scope": state.scope,
                        "required_start_date": (
                            state.required_start_date.isoformat()
                            if state.required_start_date
                            else None
                        ),
                        "covered_until": state.covered_until.isoformat()
                        if state.covered_until
                        else None,
                        "last_attempt_at": (
                            state.last_attempt_at.isoformat() if state.last_attempt_at else None
                        ),
                        "last_success_at": (
                            state.last_success_at.isoformat() if state.last_success_at else None
                        ),
                        "last_error": state.last_error or None,
                    }
                    for state in fx_states
                ],
                "latest_rows": [
                    {
                        "id": row.id,
                        "rate_date": row.rate_date.isoformat(),
                        "from_currency": row.from_currency,
                        "to_currency": row.to_currency,
                        "rate": str(row.rate),
                        "source": row.source,
                        "managed_by_system": row.managed_by_system,
                        "last_synced_at": row.last_synced_at.isoformat()
                        if row.last_synced_at
                        else None,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    }
                    for row in FxRate.objects.order_by(
                        "-rate_date", "from_currency", "to_currency"
                    )[:25]
                ],
            },
            "inflation": {
                "states": [
                    {
                        "scope": state.scope,
                        "required_start_date": (
                            state.required_start_date.isoformat()
                            if state.required_start_date
                            else None
                        ),
                        "covered_until": state.covered_until.isoformat()
                        if state.covered_until
                        else None,
                        "last_attempt_at": (
                            state.last_attempt_at.isoformat() if state.last_attempt_at else None
                        ),
                        "last_success_at": (
                            state.last_success_at.isoformat() if state.last_success_at else None
                        ),
                        "last_error": state.last_error or None,
                    }
                    for state in states
                    if state.dataset == MarketDataSyncState.Dataset.INFLATION
                ],
                "latest_rows": [
                    {
                        "id": row.id,
                        "region": row.region,
                        "period": row.period.isoformat(),
                        "index": str(row.index),
                        "source": row.source,
                        "managed_by_system": row.managed_by_system,
                        "last_synced_at": row.last_synced_at.isoformat()
                        if row.last_synced_at
                        else None,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                    }
                    for row in InflationIndex.objects.order_by("-period", "region")[:50]
                ],
            },
        },
    }
