from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from decimal import ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.utils import timezone as _timezone

from accounts.models import UserSettings
from core.models import InflationIndex
from core.services import adjust_for_inflation as _core_adjust_for_inflation, convert_currency

from .services_assets import (
    create_asset_for_user as _create_asset_for_user,
    get_amount_base_value as _asset_get_amount_base_value,
    validate_asset_payload as _validate_asset_payload,
)
from .services_liquidity import (
    build_liquidity_monthly_summary as _build_liquidity_monthly_summary,
    parse_liquidity_monthly_summary_period as _parse_liquidity_monthly_summary_period,
)
from .services_liabilities import (
    _last_day_of_month as _liab_last_day_of_month,
    build_liability_installment_schedule_simple as _liab_build_liability_installment_schedule_simple,
    estimate_liability_monthly_payment_simple as _liab_estimate_liability_monthly_payment_simple,
    estimate_liability_outstanding_amount_simple as _liab_estimate_liability_outstanding_amount_simple,
    get_effective_liability_amount as _liab_get_effective_liability_amount,
    get_generated_liability_expense_profile as _liab_get_generated_liability_expense_profile,
    get_liability_first_payment_date as _liab_get_liability_first_payment_date,
    infer_liability_is_asset_backed as _liab_infer_liability_is_asset_backed,
    sync_generated_budget_commitments_for_liability as _liab_sync_generated_budget_commitments_for_liability,
    validate_liability_payload as _liab_validate_liability_payload,
    create_liability_for_user as _create_liability_for_user,
)
from .services_snapshots import (
    create_or_update_snapshot_from_current as _create_or_update_snapshot_from_current,
    create_snapshot_for_user as _create_snapshot_for_user,
    import_snapshots_bulk_for_user as _import_snapshots_bulk_for_user,
    validate_snapshot_payload as _validate_snapshot_payload,
)
from .services_summaries import (
    build_net_worth_summary as _build_net_worth_summary,
    serialize_net_worth_summary as _serialize_net_worth_summary,
)
from .models import (
    Asset,
    Liability,
)


@dataclass
class NetWorthTotals:
    total_assets: Decimal
    total_liabilities: Decimal
    liabilities_asset_backed: Decimal
    liabilities_unbacked: Decimal
    assets_by_category: dict[str, Decimal]
    assets_by_subcategory: dict[str, Decimal]
    liabilities_by_category: dict[str, Decimal]


# Re-export split subdomain functions while keeping `net_worth.services` as compatibility facade.
timezone = _timezone
parse_liquidity_monthly_summary_period = _parse_liquidity_monthly_summary_period
adjust_for_inflation = _core_adjust_for_inflation
validate_asset_payload = _validate_asset_payload
validate_liability_payload = _liab_validate_liability_payload
infer_liability_is_asset_backed = _liab_infer_liability_is_asset_backed
estimate_liability_monthly_payment_simple = _liab_estimate_liability_monthly_payment_simple
_last_day_of_month = _liab_last_day_of_month
get_liability_first_payment_date = _liab_get_liability_first_payment_date
build_liability_installment_schedule_simple = _liab_build_liability_installment_schedule_simple
estimate_liability_outstanding_amount_simple = _liab_estimate_liability_outstanding_amount_simple
get_effective_liability_amount = _liab_get_effective_liability_amount
get_generated_liability_expense_profile = _liab_get_generated_liability_expense_profile
sync_generated_budget_commitments_for_liability = (
    _liab_sync_generated_budget_commitments_for_liability
)
create_asset_for_user = _create_asset_for_user
create_liability_for_user = _create_liability_for_user
create_or_update_snapshot_from_current = _create_or_update_snapshot_from_current
create_snapshot_for_user = _create_snapshot_for_user
import_snapshots_bulk_for_user = _import_snapshots_bulk_for_user
validate_snapshot_payload = _validate_snapshot_payload
build_liquidity_monthly_summary = _build_liquidity_monthly_summary
build_net_worth_summary = _build_net_worth_summary
serialize_net_worth_summary = _serialize_net_worth_summary
get_amount_base_value = _asset_get_amount_base_value


def get_financed_asset_queryset_for_user(*, user):
    return Asset.objects.filter(user=user, is_active=True)


def get_liquidity_asset_queryset_for_user(*, user):
    return Asset.objects.filter(user=user, is_active=True, category=Asset.Category.CASH)


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
        effective_amount = get_effective_liability_amount(
            liability=liability, as_of_date=as_of_date
        )
        converted = convert_currency(
            effective_amount, liability.currency, base_currency, date=as_of_date
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


def _serialize_money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
