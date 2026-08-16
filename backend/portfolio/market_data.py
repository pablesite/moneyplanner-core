from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.utils import timezone

from core.market_data import (
    MarketDataProvider,
    MarketDataSyncError,
    SyncScopeRequest,
    _fetch_json,
    fetch_crypto_daily_closes,
)
from core.models import FxRate, MarketDataSyncState

from .models import Instrument, InstrumentPrice, InstrumentProviderMapping, PortfolioPosition

TWELVE_DATA_API_URL = "https://api.twelvedata.com"

CRYPTO_IDENTITIES = {
    "BTC": ("Bitcoin", "bitcoin"),
    "ETH": ("Ethereum", "ethereum"),
}


def ensure_confirmed_crypto_mapping(*, position: PortfolioPosition) -> None:
    identity = CRYPTO_IDENTITIES.get(position.asset.currency.upper())
    if position.tracking_style != PortfolioPosition.TrackingStyle.UNITS_BASED or identity is None:
        return
    name, provider_symbol = identity
    canonical, _ = Instrument.objects.get_or_create(
        identity_kind=Instrument.IdentityKind.CANONICAL,
        ticker=position.asset.currency.upper(),
        market="CRYPTO",
        defaults={
            "name": name,
            "asset_class": Instrument.AssetClass.CRYPTO,
            "instrument_type": Instrument.InstrumentType.CRYPTO,
            "quote_currency": "USD",
        },
    )
    old_instrument = position.instrument
    if old_instrument.id != canonical.id:
        position.instrument = canonical
        position.save(update_fields=["instrument", "updated_at"])
        if not old_instrument.positions.exists():
            old_instrument.is_active = False
            old_instrument.save(update_fields=["is_active", "updated_at"])
    InstrumentProviderMapping.objects.get_or_create(
        instrument=canonical,
        provider=InstrumentProviderMapping.Provider.COINGECKO,
        quote_currency=position.portfolio.base_currency,
        defaults={
            "provider_symbol": provider_symbol,
            "provider_market": "",
            "is_confirmed": True,
            "confirmed_at": timezone.now(),
        },
    )


def _mapping_scope(mapping_id: int) -> str:
    return f"mapping:{mapping_id}"


def _mapping_from_scope(scope: str) -> InstrumentProviderMapping:
    try:
        prefix, raw_id = scope.split(":", 1)
        if prefix != "mapping":
            raise ValueError
        mapping_id = int(raw_id)
    except (TypeError, ValueError) as exc:
        raise MarketDataSyncError(f"Invalid instrument price scope '{scope}'.") from exc
    try:
        return InstrumentProviderMapping.objects.select_related("instrument").get(
            id=mapping_id,
            is_confirmed=True,
        )
    except InstrumentProviderMapping.DoesNotExist as exc:
        raise MarketDataSyncError(f"Confirmed mapping not found for scope '{scope}'.") from exc


def _fetch_twelve_data_closes(
    *, mapping: InstrumentProviderMapping, start_date: date, end_date: date
) -> list[tuple[date, Decimal]]:
    api_key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
    if not api_key:
        raise MarketDataSyncError("TWELVE_DATA_API_KEY is required for Twelve Data mappings.")
    query = urlencode(
        {
            "symbol": mapping.provider_symbol,
            "exchange": mapping.provider_market,
            "interval": "1day",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "order": "ASC",
            "outputsize": 5000,
            "apikey": api_key,
        }
    )
    payload = _fetch_json(url=f"{TWELVE_DATA_API_URL}/time_series?{query}")
    if not isinstance(payload, dict) or payload.get("status") == "error":
        message = payload.get("message") if isinstance(payload, dict) else None
        raise MarketDataSyncError(str(message or "Unexpected Twelve Data response."))
    meta = payload.get("meta") or {}
    response_currency = str(meta.get("currency") or "").upper()
    response_exchange = str(meta.get("exchange") or "").upper()
    if response_currency != mapping.quote_currency.upper():
        raise MarketDataSyncError(
            f"Twelve Data currency mismatch: expected {mapping.quote_currency}, "
            f"received {response_currency or 'unknown'}."
        )
    if response_exchange != mapping.provider_market.upper():
        raise MarketDataSyncError(
            f"Twelve Data market mismatch: expected {mapping.provider_market}, "
            f"received {response_exchange or 'unknown'}."
        )
    rows: list[tuple[date, Decimal]] = []
    for point in payload.get("values") or []:
        raw_date = str(point.get("datetime") or "")[:10]
        raw_close = point.get("close")
        if not raw_date or raw_close in (None, ""):
            continue
        point_date = date.fromisoformat(raw_date)
        if start_date <= point_date <= end_date:
            rows.append((point_date, Decimal(str(raw_close))))
    return rows


def _fetch_mapping_closes(
    *, mapping: InstrumentProviderMapping, start_date: date, end_date: date
) -> tuple[str, list[tuple[date, Decimal]]]:
    if mapping.provider == InstrumentProviderMapping.Provider.TWELVE_DATA:
        return "twelve_data", _fetch_twelve_data_closes(
            mapping=mapping,
            start_date=start_date,
            end_date=end_date,
        )
    if mapping.provider == InstrumentProviderMapping.Provider.COINGECKO:
        crypto_code = {
            "bitcoin": "BTC",
            "ethereum": "ETH",
        }.get(mapping.provider_symbol.lower())
        if crypto_code is None:
            raise MarketDataSyncError(
                "CoinGecko mapping is not supported by the fallback contract."
            )
        return fetch_crypto_daily_closes(
            from_currency=crypto_code,
            coin_id=mapping.provider_symbol.lower(),
            to_currency=mapping.quote_currency,
            start_date=start_date,
            end_date=end_date,
        )
    raise MarketDataSyncError(f"Unsupported price provider '{mapping.provider}'.")


def sync_instrument_mapping(
    *, mapping: InstrumentProviderMapping, start_date: date, end_date: date
) -> int:
    if not mapping.is_confirmed:
        raise MarketDataSyncError("Instrument mapping must be confirmed before synchronization.")
    if mapping.provider == InstrumentProviderMapping.Provider.COINGECKO:
        crypto_code = {
            "bitcoin": "BTC",
            "ethereum": "ETH",
        }.get(mapping.provider_symbol.lower())
        persisted_rows = list(
            FxRate.objects.filter(
                from_currency=crypto_code,
                to_currency=mapping.quote_currency,
                rate_date__gte=start_date,
                rate_date__lte=end_date,
            ).order_by("rate_date")
        )
        if persisted_rows:
            fetched_at = timezone.now()
            for row in persisted_rows:
                InstrumentPrice.objects.update_or_create(
                    instrument=mapping.instrument,
                    price_date=row.rate_date,
                    source=row.source,
                    source_key=f"{mapping.provider_symbol}:{crypto_code}->{mapping.quote_currency}",
                    defaults={
                        "provider_mapping": mapping,
                        "close": row.rate,
                        "currency": mapping.quote_currency,
                        "source_market": "",
                        "fetched_at": row.last_synced_at or fetched_at,
                    },
                )
            return len(persisted_rows)
    source, rows = _fetch_mapping_closes(
        mapping=mapping,
        start_date=start_date,
        end_date=end_date,
    )
    fetched_at = timezone.now()
    for price_date, close in rows:
        InstrumentPrice.objects.update_or_create(
            instrument=mapping.instrument,
            price_date=price_date,
            source=source,
            source_key=mapping.provider_symbol,
            defaults={
                "provider_mapping": mapping,
                "close": close,
                "currency": mapping.quote_currency,
                "source_market": mapping.provider_market,
                "fetched_at": fetched_at,
            },
        )
    return len(rows)


def refresh_confirmed_mapping(*, mapping: InstrumentProviderMapping) -> int:
    if not mapping.is_confirmed:
        raise MarketDataSyncError("Instrument mapping must be confirmed before synchronization.")
    scope = _mapping_scope(mapping.id)
    state, _ = MarketDataSyncState.objects.get_or_create(
        dataset=MarketDataSyncState.Dataset.INSTRUMENT_PRICES,
        scope=scope,
    )
    opened_dates = list(mapping.instrument.positions.values_list("opened_on", flat=True))
    required_start = min(opened_dates) if opened_dates else timezone.localdate()
    latest = (
        InstrumentPrice.objects.filter(provider_mapping=mapping)
        .order_by("-price_date")
        .values_list("price_date", flat=True)
        .first()
    )
    start_date = latest + timedelta(days=1) if latest else required_start
    today = timezone.localdate()
    state.required_start_date = required_start
    state.last_attempt_at = timezone.now()
    state.source = mapping.provider
    state.save(update_fields=["required_start_date", "last_attempt_at", "source", "updated_at"])
    if start_date > today:
        return 0
    try:
        inserted = sync_instrument_mapping(
            mapping=mapping,
            start_date=start_date,
            end_date=today,
        )
    except MarketDataSyncError as exc:
        state.last_error = str(exc)
        state.save(update_fields=["last_error", "updated_at"])
        raise
    state.covered_until = (
        InstrumentPrice.objects.filter(provider_mapping=mapping)
        .order_by("-price_date")
        .values_list("price_date", flat=True)
        .first()
    )
    state.last_success_at = timezone.now()
    state.last_error = ""
    state.save(update_fields=["covered_until", "last_success_at", "last_error", "updated_at"])
    return inserted


class InstrumentPriceMarketDataProvider(MarketDataProvider):
    dataset = MarketDataSyncState.Dataset.INSTRUMENT_PRICES
    source = "instrument_adapter_registry"

    def build_scope_requests(self) -> list[SyncScopeRequest]:
        requests: list[SyncScopeRequest] = []
        mappings = InstrumentProviderMapping.objects.filter(is_confirmed=True).prefetch_related(
            "instrument__positions"
        )
        for mapping in mappings:
            opened_dates = [position.opened_on for position in mapping.instrument.positions.all()]
            if not opened_dates:
                continue
            requests.append(
                SyncScopeRequest(
                    dataset=str(self.dataset),
                    scope=_mapping_scope(mapping.id),
                    required_start_date=min(opened_dates),
                )
            )
        return requests

    def get_coverage_bounds(self, *, scope: str) -> tuple[date | None, date | None]:
        mapping = _mapping_from_scope(scope)
        rows = InstrumentPrice.objects.filter(provider_mapping=mapping)
        earliest = rows.order_by("price_date").values_list("price_date", flat=True).first()
        latest = rows.order_by("-price_date").values_list("price_date", flat=True).first()
        return earliest, latest

    def sync_scope(
        self, *, scope: str, required_start_date: date | None, mode: str, today: date
    ) -> int:
        if required_start_date is None:
            return 0
        mapping = _mapping_from_scope(scope)
        earliest, latest = self.get_coverage_bounds(scope=scope)
        if mode == "refresh":
            start_date = latest + timedelta(days=1) if latest else required_start_date
            if start_date > today:
                return 0
            return sync_instrument_mapping(
                mapping=mapping,
                start_date=start_date,
                end_date=today,
            )
        inserted = 0
        if earliest is None or latest is None:
            return sync_instrument_mapping(
                mapping=mapping,
                start_date=required_start_date,
                end_date=today,
            )
        if required_start_date < earliest:
            inserted += sync_instrument_mapping(
                mapping=mapping,
                start_date=required_start_date,
                end_date=earliest - timedelta(days=1),
            )
        if latest < today:
            inserted += sync_instrument_mapping(
                mapping=mapping,
                start_date=latest + timedelta(days=1),
                end_date=today,
            )
        return inserted
