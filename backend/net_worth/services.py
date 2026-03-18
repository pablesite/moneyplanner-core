from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import cast

from django.core.exceptions import ValidationError
from django.utils import timezone as _timezone

from accounts.models import UserSettings
from core.models import InflationIndex
from core.services import adjust_for_inflation as _core_adjust_for_inflation, convert_currency

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


def get_base_currency_for_user(*, user) -> str:
    UserSettings.objects.get_or_create(user=user)
    return cast(str, user.settings.base_currency)


def get_inflation_region_for_user(*, user) -> str:
    UserSettings.objects.get_or_create(user=user)
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
    *, assets_qs, liabilities_qs, base_currency: str, as_of_date: date
) -> NetWorthTotals:
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    liabilities_asset_backed = Decimal("0")
    liabilities_unbacked = Decimal("0")
    assets_by_category: dict[str, Decimal] = {}
    assets_by_subcategory: dict[str, Decimal] = {}
    liabilities_by_category: dict[str, Decimal] = {}

    for asset in assets_qs:
        effective_amount = get_effective_asset_amount(asset=asset, as_of_date=as_of_date)
        converted = convert_currency(
            effective_amount, asset.currency, base_currency, date=as_of_date
        )
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
        )
        converted = convert_currency(
            effective_amount, liability.currency, base_currency, date=as_of_date
        )
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
