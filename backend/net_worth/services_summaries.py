from __future__ import annotations

from decimal import Decimal
from typing import cast

from django.core.exceptions import ValidationError


def _build_net_worth_summary_impl(
    *,
    user,
    get_base_currency_for_user_fn,
    get_inflation_region_for_user_fn,
    get_active_positions_fn,
    calculate_totals_fn,
    get_inflation_base_period_fn,
    timezone_localdate_fn,
    adjust_for_inflation_fn,
    build_inflation_adjuster_fn=None,
    build_fx_cache_fn=None,
    build_position_data_cache_fn=None,
) -> dict[str, object]:
    today = timezone_localdate_fn()
    base_currency = get_base_currency_for_user_fn(user=user)
    assets_qs, liabilities_qs = get_active_positions_fn(user=user)
    assets = list(assets_qs)
    liabilities = list(liabilities_qs)
    fx_cache = None
    position_cache = None
    if build_fx_cache_fn is not None:
        currencies = {base_currency}
        currencies.update(asset.currency for asset in assets)
        currencies.update(liability.currency for liability in liabilities)
        fx_cache = build_fx_cache_fn(currencies)
    if build_position_data_cache_fn is not None:
        position_cache = build_position_data_cache_fn(assets, liabilities)
    totals = calculate_totals_fn(
        assets_qs=assets,
        liabilities_qs=liabilities,
        base_currency=base_currency,
        as_of_date=today,
        fx_cache=fx_cache,
        position_cache=position_cache,
    )

    net_worth = totals.total_assets - totals.total_liabilities
    inflation_region = (
        get_inflation_region_for_user_fn(user=user) if base_currency == "EUR" else None
    )
    inflation_base_period = None
    inflation_available = False
    inflation_status = "disabled" if base_currency != "EUR" else "missing"

    total_assets_real = None
    total_liabilities_real = None
    net_worth_real = None
    assets_by_category_real = None
    liabilities_by_category_real = None
    liabilities_asset_backed_real = None
    liabilities_unbacked_real = None

    if inflation_region is not None:
        try:
            inflation_base_period = get_inflation_base_period_fn(region=inflation_region)
            inflation_adjuster = None
            if build_inflation_adjuster_fn is not None:
                try:
                    inflation_adjuster = build_inflation_adjuster_fn(
                        region=inflation_region,
                        date_value=today,
                        base_period=inflation_base_period,
                    )
                except ValidationError:
                    inflation_adjuster = None

            def _adjust(amount: Decimal) -> Decimal:
                if inflation_adjuster is not None:
                    return inflation_adjuster(amount)
                return adjust_for_inflation_fn(
                    amount,
                    date=today,
                    region=inflation_region,
                    base_period=inflation_base_period,
                )

            total_assets_real = _adjust(totals.total_assets)
            total_liabilities_real = _adjust(totals.total_liabilities)
            net_worth_real = _adjust(net_worth)
            assets_by_category_real = {
                category: _adjust(amount) for category, amount in totals.assets_by_category.items()
            }
            liabilities_by_category_real = {
                category: _adjust(amount)
                for category, amount in totals.liabilities_by_category.items()
            }
            liabilities_asset_backed_real = _adjust(totals.liabilities_asset_backed)
            liabilities_unbacked_real = _adjust(totals.liabilities_unbacked)
            inflation_available = True
            inflation_status = "available"
        except ValidationError:
            inflation_available = False
            inflation_status = "missing"

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
        "inflation_available": inflation_available,
        "inflation_status": inflation_status,
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


def build_net_worth_summary(*, user) -> dict[str, object]:
    # Local import keeps patching compatibility through `net_worth.services` during transition.
    from . import services as services_facade
    from .services_timelines import _build_position_data_cache
    from core.services import build_fx_cache

    return _build_net_worth_summary_impl(
        user=user,
        get_base_currency_for_user_fn=services_facade.get_base_currency_for_user,
        get_inflation_region_for_user_fn=services_facade.get_inflation_region_for_user,
        get_active_positions_fn=services_facade._get_active_positions,
        calculate_totals_fn=services_facade.calculate_totals,
        get_inflation_base_period_fn=services_facade.get_inflation_base_period,
        timezone_localdate_fn=services_facade.timezone.localdate,
        adjust_for_inflation_fn=services_facade.adjust_for_inflation,
        build_inflation_adjuster_fn=services_facade.build_inflation_adjuster,
        build_fx_cache_fn=build_fx_cache,
        build_position_data_cache_fn=_build_position_data_cache,
    )


def serialize_net_worth_summary(summary: dict[str, object]) -> dict[str, object]:
    assets_by_category = cast(dict[str, Decimal], summary["assets_by_category"])
    assets_by_subcategory = cast(dict[str, Decimal], summary["assets_by_subcategory"])
    liabilities_by_category = cast(dict[str, Decimal], summary["liabilities_by_category"])
    assets_by_category_real = cast(dict[str, Decimal] | None, summary["assets_by_category_real"])
    liabilities_by_category_real = cast(
        dict[str, Decimal] | None, summary["liabilities_by_category_real"]
    )

    return {
        "base_currency": summary["base_currency"],
        "total_assets": str(summary["total_assets"]),
        "total_liabilities": str(summary["total_liabilities"]),
        "net_worth": str(summary["net_worth"]),
        "assets_by_category": {k: str(v) for k, v in assets_by_category.items()},
        "assets_by_subcategory": {k: str(v) for k, v in assets_by_subcategory.items()},
        "liabilities_by_category": {k: str(v) for k, v in liabilities_by_category.items()},
        "inflation_region": summary["inflation_region"],
        "inflation_base_period": (
            str(summary["inflation_base_period"]) if summary["inflation_base_period"] else None
        ),
        "inflation_available": bool(summary["inflation_available"]),
        "inflation_status": summary["inflation_status"],
        "total_assets_real": (
            str(summary["total_assets_real"]) if summary["total_assets_real"] is not None else None
        ),
        "total_liabilities_real": (
            str(summary["total_liabilities_real"])
            if summary["total_liabilities_real"] is not None
            else None
        ),
        "net_worth_real": (
            str(summary["net_worth_real"]) if summary["net_worth_real"] is not None else None
        ),
        "assets_by_category_real": (
            {k: str(v) for k, v in assets_by_category_real.items()}
            if assets_by_category_real is not None
            else None
        ),
        "liabilities_by_category_real": (
            {k: str(v) for k, v in liabilities_by_category_real.items()}
            if liabilities_by_category_real is not None
            else None
        ),
        "liabilities_asset_backed": str(summary["liabilities_asset_backed"]),
        "liabilities_unbacked": str(summary["liabilities_unbacked"]),
        "liabilities_asset_backed_real": (
            str(summary["liabilities_asset_backed_real"])
            if summary["liabilities_asset_backed_real"] is not None
            else None
        ),
        "liabilities_unbacked_real": (
            str(summary["liabilities_unbacked_real"])
            if summary["liabilities_unbacked_real"] is not None
            else None
        ),
    }
