from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import UserSettings
from core.models import InflationIndex
from core.services import adjust_for_inflation, convert_currency

from .models import Asset, Liability, NetWorthSnapshot


@dataclass
class NetWorthTotals:
    total_assets: Decimal
    total_liabilities: Decimal
    liabilities_asset_backed: Decimal
    liabilities_unbacked: Decimal
    assets_by_category: dict[str, Decimal]
    assets_by_subcategory: dict[str, Decimal]
    liabilities_by_category: dict[str, Decimal]


def get_base_currency_for_user(*, user) -> str:
    UserSettings.objects.get_or_create(user=user)
    return user.settings.base_currency


def get_inflation_base_period(*, region: str) -> date:
    row = InflationIndex.objects.filter(region=region).order_by("period").first()
    if not row:
        raise ValidationError(f"Missing inflation index for region={region}.")
    return row.period


def _get_active_positions(*, user):
    assets_qs = Asset.objects.filter(user=user, is_active=True)
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
        converted = convert_currency(asset.amount, asset.currency, base_currency, date=as_of_date)
        total_assets += converted

        assets_by_category.setdefault(asset.category, Decimal("0"))
        assets_by_category[asset.category] += converted

        subkey = f"{asset.category}:{asset.subcategory or 'other'}"
        assets_by_subcategory.setdefault(subkey, Decimal("0"))
        assets_by_subcategory[subkey] += converted

    for liability in liabilities_qs:
        converted = convert_currency(
            liability.amount, liability.currency, base_currency, date=as_of_date
        )
        total_liabilities += converted

        liabilities_by_category.setdefault(liability.category, Decimal("0"))
        liabilities_by_category[liability.category] += converted

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


def create_or_update_snapshot_from_current(*, user) -> tuple[NetWorthSnapshot, bool]:
    snapshot_date = timezone.localdate()
    base_currency = get_base_currency_for_user(user=user)
    assets_qs, liabilities_qs = _get_active_positions(user=user)
    totals = calculate_totals(
        assets_qs=assets_qs,
        liabilities_qs=liabilities_qs,
        base_currency=base_currency,
        as_of_date=snapshot_date,
    )
    net_worth = totals.total_assets - totals.total_liabilities

    return NetWorthSnapshot.objects.update_or_create(
        user=user,
        snapshot_date=snapshot_date,
        defaults={
            "base_currency": base_currency,
            "total_assets": totals.total_assets,
            "total_liabilities": totals.total_liabilities,
            "net_worth": net_worth,
        },
    )


def build_net_worth_summary(*, user) -> dict[str, object]:
    today = timezone.localdate()
    base_currency = get_base_currency_for_user(user=user)
    assets_qs, liabilities_qs = _get_active_positions(user=user)
    totals = calculate_totals(
        assets_qs=assets_qs,
        liabilities_qs=liabilities_qs,
        base_currency=base_currency,
        as_of_date=today,
    )

    net_worth = totals.total_assets - totals.total_liabilities
    inflation_region = "ES" if base_currency == "EUR" else None
    inflation_base_period = None

    total_assets_real = None
    total_liabilities_real = None
    net_worth_real = None
    assets_by_category_real = None
    liabilities_by_category_real = None
    liabilities_asset_backed_real = None
    liabilities_unbacked_real = None

    if inflation_region is not None:
        inflation_base_period = get_inflation_base_period(region=inflation_region)

        total_assets_real = adjust_for_inflation(
            totals.total_assets,
            date=today,
            region=inflation_region,
            base_period=inflation_base_period,
        )
        total_liabilities_real = adjust_for_inflation(
            totals.total_liabilities,
            date=today,
            region=inflation_region,
            base_period=inflation_base_period,
        )
        net_worth_real = adjust_for_inflation(
            net_worth,
            date=today,
            region=inflation_region,
            base_period=inflation_base_period,
        )
        assets_by_category_real = {
            category: adjust_for_inflation(
                amount,
                date=today,
                region=inflation_region,
                base_period=inflation_base_period,
            )
            for category, amount in totals.assets_by_category.items()
        }
        liabilities_by_category_real = {
            category: adjust_for_inflation(
                amount,
                date=today,
                region=inflation_region,
                base_period=inflation_base_period,
            )
            for category, amount in totals.liabilities_by_category.items()
        }
        liabilities_asset_backed_real = adjust_for_inflation(
            totals.liabilities_asset_backed,
            date=today,
            region=inflation_region,
            base_period=inflation_base_period,
        )
        liabilities_unbacked_real = adjust_for_inflation(
            totals.liabilities_unbacked,
            date=today,
            region=inflation_region,
            base_period=inflation_base_period,
        )

    return {
        "base_currency": base_currency,
        "total_assets": totals.total_assets,
        "total_liabilities": totals.total_liabilities,
        "net_worth": net_worth,
        "assets_by_category": totals.assets_by_category,
        "assets_by_subcategory": totals.assets_by_subcategory,
        "liabilities_by_category": totals.liabilities_by_category,
        "inflation_region": inflation_region,
        "inflation_base_period": inflation_base_period,
        "total_assets_real": total_assets_real,
        "total_liabilities_real": total_liabilities_real,
        "net_worth_real": net_worth_real,
        "assets_by_category_real": assets_by_category_real,
        "liabilities_by_category_real": liabilities_by_category_real,
        "liabilities_asset_backed": totals.liabilities_asset_backed,
        "liabilities_unbacked": totals.liabilities_unbacked,
        "liabilities_asset_backed_real": liabilities_asset_backed_real,
        "liabilities_unbacked_real": liabilities_unbacked_real,
    }
