from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from core.services import build_fx_cache, convert_currency_cached

from .models import (
    Asset,
    AssetValuation,
    InvestmentAssetEvent,
    Liability,
    LiabilityEvent,
    LiabilityValuation,
    LiquidityAssetEvent,
    LiquidityMonthlyCheckin,
)
from .services import calculate_totals, get_base_currency_for_user
from .services_assets_core import get_effective_asset_amount
from .services_liabilities_core import get_effective_liability_amount


@dataclass
class PositionDataCache:
    """In-memory cache of position-level data for timeline builds."""

    asset_valuations: dict[int, list] = field(default_factory=dict)
    investment_events: dict[int, list] = field(default_factory=dict)
    liquidity_events: dict[int, list] = field(default_factory=dict)
    liquidity_checkins: dict[int, list] = field(default_factory=dict)
    liability_valuations: dict[int, list] = field(default_factory=dict)
    liability_events: dict[int, list] = field(default_factory=dict)


def _build_position_data_cache(
    assets: list[Asset], liabilities: list[Liability],
) -> PositionDataCache:
    cache = PositionDataCache()
    asset_ids = [a.id for a in assets]
    liability_ids = [li.id for li in liabilities]

    # AssetValuation grouped by asset_id, sorted desc
    if asset_ids:
        for v in AssetValuation.objects.filter(asset_id__in=asset_ids).order_by(
            "-valuation_date", "-updated_at", "-id"
        ):
            cache.asset_valuations.setdefault(v.asset_id, []).append(v)

        for e in InvestmentAssetEvent.objects.filter(asset_id__in=asset_ids):
            cache.investment_events.setdefault(e.asset_id, []).append(e)

        for e in LiquidityAssetEvent.objects.filter(asset_id__in=asset_ids):
            cache.liquidity_events.setdefault(e.asset_id, []).append(e)

        for c in LiquidityMonthlyCheckin.objects.filter(asset_id__in=asset_ids).order_by(
            "-fiscal_year", "-month", "-updated_at", "-id"
        ):
            cache.liquidity_checkins.setdefault(c.asset_id, []).append(c)

    if liability_ids:
        for v in LiabilityValuation.objects.filter(liability_id__in=liability_ids).order_by(
            "-valuation_date", "-updated_at", "-id"
        ):
            cache.liability_valuations.setdefault(v.liability_id, []).append(v)

        for e in LiabilityEvent.objects.filter(liability_id__in=liability_ids):
            cache.liability_events.setdefault(e.liability_id, []).append(e)

    return cache


def _month_end_for(value: date) -> date:
    if value.month == 12:
        next_month = date(value.year + 1, 1, 1)
    else:
        next_month = date(value.year, value.month + 1, 1)
    return next_month.fromordinal(next_month.toordinal() - 1)


def _iter_month_ends(*, start_date: date, end_date: date) -> list[date]:
    current = _month_end_for(start_date)
    end_month = _month_end_for(end_date)
    rows: list[date] = []
    while current <= end_month:
        rows.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 31)
        else:
            next_month_start = date(current.year, current.month + 1, 1)
            current = _month_end_for(next_month_start)
    return rows


def _parse_date_param(*, raw_value: str | None, field_name: str) -> date | None:
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError as err:
        raise ValidationError({field_name: "Fecha invalida. Usa YYYY-MM-DD."}) from err


def parse_timeline_query_params(*, query_params) -> dict[str, object]:
    group_by = str(query_params.get("group_by") or "month").strip().lower()
    if group_by != "month":
        raise ValidationError({"group_by": "Solo se soporta group_by=month en esta iteracion."})

    start_date = _parse_date_param(
        raw_value=query_params.get("start_date"), field_name="start_date"
    )
    end_date = _parse_date_param(raw_value=query_params.get("end_date"), field_name="end_date")
    if start_date and end_date and end_date < start_date:
        raise ValidationError({"end_date": "Debe ser igual o posterior a start_date."})

    return {
        "group_by": group_by,
        "start_date": start_date,
        "end_date": end_date,
        "asset_category": str(query_params.get("asset_category") or "").strip() or None,
        "liability_category": str(query_params.get("liability_category") or "").strip() or None,
    }


def _resolve_timeline_range(
    *,
    start_date: date | None,
    end_date: date | None,
    asset_dates: list[date],
    liability_dates: list[date],
) -> tuple[date, date]:
    if start_date is None:
        candidates = asset_dates + liability_dates
        start_date = min(candidates) if candidates else timezone.localdate()
    if end_date is None:
        end_date = timezone.localdate()
    if end_date < start_date:
        raise ValidationError({"end_date": "Debe ser igual o posterior a start_date."})
    return start_date, end_date


def build_net_worth_timeline(
    *,
    user,
    start_date: date | None = None,
    end_date: date | None = None,
    asset_category: str | None = None,
    liability_category: str | None = None,
) -> dict[str, object]:
    base_currency = get_base_currency_for_user(user=user)
    assets_qs = Asset.objects.filter(user=user, is_active=True).prefetch_related("improvements")
    liabilities_qs = Liability.objects.filter(user=user, is_active=True)
    if asset_category:
        assets_qs = assets_qs.filter(category=asset_category)
    if liability_category:
        liabilities_qs = liabilities_qs.filter(category=liability_category)

    assets = list(assets_qs)
    liabilities = list(liabilities_qs)
    timeline_start_date, timeline_end_date = _resolve_timeline_range(
        start_date=start_date,
        end_date=end_date,
        asset_dates=[asset.start_date for asset in assets],
        liability_dates=[liability.start_date for liability in liabilities],
    )

    # Bulk-load FX rates and position data for all involved positions
    currencies = {base_currency}
    currencies.update(a.currency for a in assets)
    currencies.update(li.currency for li in liabilities)
    fx_cache = build_fx_cache(currencies)
    pos_cache = _build_position_data_cache(assets, liabilities)

    rows: list[dict[str, object]] = []
    for point_date in _iter_month_ends(start_date=timeline_start_date, end_date=timeline_end_date):
        active_assets = [asset for asset in assets if asset.start_date <= point_date]
        active_liabilities = [
            liability for liability in liabilities if liability.start_date <= point_date
        ]
        totals = calculate_totals(
            assets_qs=active_assets,
            liabilities_qs=active_liabilities,
            base_currency=base_currency,
            as_of_date=point_date,
            fx_cache=fx_cache,
            position_cache=pos_cache,
        )
        rows.append(
            {
                "date": point_date.isoformat(),
                "total_assets": _serialize_money(totals.total_assets),
                "total_liabilities": _serialize_money(totals.total_liabilities),
                "net_worth": _serialize_money(totals.total_assets - totals.total_liabilities),
                "asset_positions": len(active_assets),
                "liability_positions": len(active_liabilities),
            }
        )

    return {
        "group_by": "month",
        "start_date": timeline_start_date.isoformat(),
        "end_date": timeline_end_date.isoformat(),
        "base_currency": base_currency,
        "filters": {
            "asset_category": asset_category,
            "liability_category": liability_category,
        },
        "rows": rows,
    }


def build_asset_timeline(*, asset: Asset, end_date: date | None = None) -> dict[str, object]:
    base_currency = get_base_currency_for_user(user=asset.user)
    timeline_end_date = end_date or timezone.localdate()
    fx_cache = build_fx_cache({base_currency, asset.currency})
    rows: list[dict[str, object]] = []
    for point_date in _iter_month_ends(start_date=asset.start_date, end_date=timeline_end_date):
        native_value = get_effective_asset_amount(asset=asset, as_of_date=point_date)
        base_value = convert_currency_cached(
            native_value, asset.currency, base_currency,
            rate_date=point_date, fx_cache=fx_cache,
        )
        rows.append(
            {
                "date": point_date.isoformat(),
                "value": _serialize_money(native_value),
                "value_base": _serialize_money(base_value),
            }
        )
    return {
        "group_by": "month",
        "position_type": "asset",
        "position_id": asset.id,
        "currency": asset.currency,
        "base_currency": base_currency,
        "rows": rows,
    }


def build_liability_timeline(
    *, liability: Liability, end_date: date | None = None
) -> dict[str, object]:
    base_currency = get_base_currency_for_user(user=liability.user)
    timeline_end_date = end_date or timezone.localdate()
    fx_cache = build_fx_cache({base_currency, liability.currency})
    rows: list[dict[str, object]] = []
    for point_date in _iter_month_ends(start_date=liability.start_date, end_date=timeline_end_date):
        native_value = get_effective_liability_amount(liability=liability, as_of_date=point_date)
        base_value = convert_currency_cached(
            native_value, liability.currency, base_currency,
            rate_date=point_date, fx_cache=fx_cache,
        )
        rows.append(
            {
                "date": point_date.isoformat(),
                "value": _serialize_money(native_value),
                "value_base": _serialize_money(base_value),
            }
        )
    return {
        "group_by": "month",
        "position_type": "liability",
        "position_id": liability.id,
        "currency": liability.currency,
        "base_currency": base_currency,
        "rows": rows,
    }


def _serialize_money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))
