from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, cast

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone as _timezone

from accounts.models import UserSettings
from core.models import InflationIndex
from core.services import (
    adjust_for_inflation as _core_adjust_for_inflation,
    convert_currency,
    convert_currency_cached,
)

from .models import Asset, Liability
from .services_assets_core import get_effective_asset_amount
from .services_liabilities_core import (
    _last_day_of_month as _liabilities_last_day_of_month,
    get_effective_liability_amount,
)

timezone = _timezone
adjust_for_inflation = _core_adjust_for_inflation
_last_day_of_month = _liabilities_last_day_of_month


@dataclass
class NetWorthTotals:
    total_assets: Decimal
    total_liabilities: Decimal
    liabilities_asset_backed: Decimal
    liabilities_unbacked: Decimal
    assets_by_category: dict[str, Decimal]
    assets_by_subcategory: dict[str, Decimal]
    liabilities_by_category: dict[str, Decimal]


def get_financed_asset_queryset_for_user(*, user):
    return Asset.objects.filter(user=user, is_active=True)


def get_liquidity_asset_queryset_for_user(*, user):
    return Asset.objects.filter(user=user, is_active=True, category=Asset.Category.CASH)


def _ensure_user_settings(user) -> None:
    """Ensure the user.settings reverse relation is loaded, creating the row if needed."""
    try:
        user.settings  # noqa: B018 – triggers Django cached descriptor
    except ObjectDoesNotExist:
        UserSettings.objects.get_or_create(user=user)


def get_base_currency_for_user(*, user) -> str:
    _ensure_user_settings(user)
    return cast(str, user.settings.base_currency)


def get_inflation_region_for_user(*, user) -> str:
    _ensure_user_settings(user)
    return cast(str, user.settings.inflation_region or InflationIndex.Region.ES)


def get_inflation_base_period(*, region: str) -> date:
    row = InflationIndex.objects.filter(region=region).order_by("period").first()
    if not row:
        raise ValidationError(f"Missing inflation index for region={region}.")
    return row.period


def _get_active_positions(*, user):
    assets_qs = Asset.objects.filter(user=user, is_active=True).prefetch_related("improvements")
    liabilities_qs = Liability.objects.filter(user=user, is_active=True)
    return assets_qs, liabilities_qs


def calculate_totals(
    *,
    assets_qs,
    liabilities_qs,
    base_currency: str,
    as_of_date: date,
    fx_cache: dict | None = None,
    position_cache=None,
) -> NetWorthTotals:
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    liabilities_asset_backed = Decimal("0")
    liabilities_unbacked = Decimal("0")
    assets_by_category: dict[str, Decimal] = {}
    assets_by_subcategory: dict[str, Decimal] = {}
    liabilities_by_category: dict[str, Decimal] = {}

    def _convert(amount: Decimal, from_cur: str) -> Decimal:
        if fx_cache is not None:
            return convert_currency_cached(
                amount,
                from_cur,
                base_currency,
                rate_date=as_of_date,
                fx_cache=fx_cache,
            )
        return convert_currency(amount, from_cur, base_currency, date=as_of_date)

    for asset in assets_qs:
        effective_amount = get_effective_asset_amount(
            asset=asset,
            as_of_date=as_of_date,
            position_cache=position_cache,
        )
        converted = _convert(effective_amount, asset.currency)
        total_assets += converted
        assets_by_category[asset.category] = (
            assets_by_category.get(asset.category, Decimal("0")) + converted
        )
        subkey = f"{asset.category}:{asset.subcategory or 'other'}"
        assets_by_subcategory[subkey] = assets_by_subcategory.get(subkey, Decimal("0")) + converted

    for liability in liabilities_qs:
        effective_amount = get_effective_liability_amount(
            liability=liability,
            as_of_date=as_of_date,
            position_cache=position_cache,
        )
        converted = _convert(effective_amount, liability.currency)
        total_liabilities += converted
        liabilities_by_category[liability.category] = (
            liabilities_by_category.get(liability.category, Decimal("0")) + converted
        )
        if liability.financed_asset_id is not None:
            liabilities_asset_backed += converted
        else:
            liabilities_unbacked += converted
    return NetWorthTotals(
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        liabilities_asset_backed=liabilities_asset_backed,
        liabilities_unbacked=liabilities_unbacked,
        assets_by_category=assets_by_category,
        assets_by_subcategory=assets_by_subcategory,
        liabilities_by_category=liabilities_by_category,
    )


def _serialize_money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_inflation_adjuster(
    *, region: str, date_value: date, base_period: date | None = None
) -> Callable[[Decimal], Decimal]:
    rows = list(
        InflationIndex.objects.filter(region=region)
        .order_by("period")
        .values_list("period", "index")
    )
    if not rows:
        raise ValidationError(f"Missing inflation index for region={region}.")

    periods = [period for period, _ in rows]
    indexes = [Decimal(index) for _, index in rows]

    def _index_for(period_value: date) -> Decimal:
        period_month = period_value.replace(day=1)
        idx = bisect_right(periods, period_month) - 1
        if idx < 0:
            idx = 0
        return indexes[idx]

    base_month = (base_period or periods[-1]).replace(day=1)
    date_month = date_value.replace(day=1)
    index_base = _index_for(base_month)
    index_date = _index_for(date_month)
    if index_date == 0:
        raise ValidationError(f"Invalid inflation index: region={region} period={date_month} is 0.")
    factor = index_base / index_date

    def _adjust(amount: Decimal) -> Decimal:
        return (Decimal(amount) * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return _adjust
