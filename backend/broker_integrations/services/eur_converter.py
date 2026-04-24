from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from core.models import FxRate


STABLECOIN_TO_FIAT = {
    "USDT": "USD",
    "USDC": "USD",
}


class EurConverter:
    def __init__(self) -> None:
        self._cache: dict[tuple[date, str], Decimal] = {}

    def _normalize_asset(self, asset: str) -> str:
        normalized = (asset or "").strip().upper()
        return STABLECOIN_TO_FIAT.get(normalized, normalized)

    @staticmethod
    def _lookup_direct(
        *, from_currency: str, to_currency: str, rate_date: date, exact_day: bool
    ) -> Decimal | None:
        filters = {
            "from_currency": from_currency,
            "to_currency": to_currency,
        }
        if exact_day:
            filters["rate_date"] = rate_date
        else:
            filters["rate_date__lte"] = rate_date
        row = FxRate.objects.filter(**filters).order_by("-rate_date").first()
        return Decimal(row.rate) if row else None

    @staticmethod
    def _sync_pair_for_day(*, from_currency: str, to_currency: str, rate_date: date) -> None:
        from core.market_data import MarketDataSyncError, sync_market_history

        start_date = rate_date - timedelta(days=7)
        try:
            sync_market_history(
                from_currency=from_currency,
                to_currency=to_currency,
                start_date=start_date,
                end_date=rate_date,
            )
        except MarketDataSyncError:
            return

    def _resolve_pair_rate(
        self, *, from_currency: str, to_currency: str, rate_date: date
    ) -> Decimal | None:
        exact = self._lookup_direct(
            from_currency=from_currency,
            to_currency=to_currency,
            rate_date=rate_date,
            exact_day=True,
        )
        if exact is not None:
            return exact

        self._sync_pair_for_day(
            from_currency=from_currency,
            to_currency=to_currency,
            rate_date=rate_date,
        )
        exact_after_sync = self._lookup_direct(
            from_currency=from_currency,
            to_currency=to_currency,
            rate_date=rate_date,
            exact_day=True,
        )
        if exact_after_sync is not None:
            return exact_after_sync

        # Weekend/holiday fallback for fiat markets: use last known rate before the movement date.
        previous = self._lookup_direct(
            from_currency=from_currency,
            to_currency=to_currency,
            rate_date=rate_date,
            exact_day=False,
        )
        if previous is not None:
            return previous

        next_row = (
            FxRate.objects.filter(
                from_currency=from_currency,
                to_currency=to_currency,
                rate_date__gte=rate_date,
            )
            .order_by("rate_date")
            .first()
        )
        return Decimal(next_row.rate) if next_row else None

    def get_eur_rate(self, *, trade_date: date, asset: str) -> Decimal:
        normalized_asset = self._normalize_asset(asset)
        cache_key = (trade_date, normalized_asset)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if normalized_asset == "EUR":
            self._cache[cache_key] = Decimal("1")
            return self._cache[cache_key]

        direct = self._resolve_pair_rate(
            from_currency=normalized_asset,
            to_currency="EUR",
            rate_date=trade_date,
        )
        if direct is not None:
            self._cache[cache_key] = direct
            return direct

        inverse = self._resolve_pair_rate(
            from_currency="EUR",
            to_currency=normalized_asset,
            rate_date=trade_date,
        )
        if inverse is not None and inverse != 0:
            self._cache[cache_key] = Decimal("1") / inverse
            return self._cache[cache_key]

        via_usd_leg1 = self._resolve_pair_rate(
            from_currency=normalized_asset,
            to_currency="USD",
            rate_date=trade_date,
        )
        if via_usd_leg1 is None:
            via_usd_leg1_inverse = self._resolve_pair_rate(
                from_currency="USD",
                to_currency=normalized_asset,
                rate_date=trade_date,
            )
            if via_usd_leg1_inverse is not None and via_usd_leg1_inverse != 0:
                via_usd_leg1 = Decimal("1") / via_usd_leg1_inverse

        via_usd_leg2 = self._resolve_pair_rate(
            from_currency="USD",
            to_currency="EUR",
            rate_date=trade_date,
        )
        if via_usd_leg2 is None:
            via_usd_leg2_inverse = self._resolve_pair_rate(
                from_currency="EUR",
                to_currency="USD",
                rate_date=trade_date,
            )
            if via_usd_leg2_inverse is not None and via_usd_leg2_inverse != 0:
                via_usd_leg2 = Decimal("1") / via_usd_leg2_inverse

        if via_usd_leg1 is not None and via_usd_leg2 is not None:
            self._cache[cache_key] = via_usd_leg1 * via_usd_leg2
            return self._cache[cache_key]

        raise ValueError(
            f"Missing EUR conversion rate for {normalized_asset} on {trade_date.isoformat()}."
        )

    def convert_amount_to_eur(self, *, amount: Decimal, asset: str, trade_date: date) -> Decimal:
        return Decimal(amount) * self.get_eur_rate(trade_date=trade_date, asset=asset)
