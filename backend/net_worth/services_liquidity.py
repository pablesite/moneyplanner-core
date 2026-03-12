from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from core.services import convert_currency

from .models import LiquidityMonthlyCheckin


def parse_liquidity_monthly_summary_period(*, query_params) -> tuple[int, int]:
    try:
        fiscal_year = int(query_params.get("year") or timezone.localdate().year)
        month = int(query_params.get("month") or timezone.localdate().month)
    except (TypeError, ValueError) as err:
        raise DRFValidationError({"detail": "year y month deben ser enteros."}) from err
    return fiscal_year, month


def _build_liquidity_monthly_summary_impl(
    *,
    user,
    fiscal_year: int,
    month: int,
    get_base_currency_for_user_fn,
    get_liquidity_asset_queryset_for_user_fn,
    get_effective_asset_amount_fn,
    last_day_of_month_fn,
    serialize_money_fn,
) -> dict[str, object]:
    if month < 1 or month > 12:
        raise ValidationError({"month": "month debe estar entre 1 y 12."})

    base_currency = get_base_currency_for_user_fn(user=user)
    summary_date = date(fiscal_year, month, last_day_of_month_fn(fiscal_year, month))
    liquid_assets = list(
        get_liquidity_asset_queryset_for_user_fn(user=user).order_by("subcategory", "name", "id")
    )
    checkins = {
        row.asset_id: row
        for row in LiquidityMonthlyCheckin.objects.filter(
            user=user,
            fiscal_year=fiscal_year,
            month=month,
        ).select_related("asset")
    }

    rows: list[dict[str, object]] = []
    planned_total_base = Decimal("0")
    executed_total_base = Decimal("0")
    checked_count = 0

    for asset in liquid_assets:
        planned_native = Decimal(asset.amount or 0)
        checkin = checkins.get(asset.id)
        executed_native = checkin.closing_balance_real if checkin is not None else None
        effective_native = (
            executed_native
            if executed_native is not None
            else get_effective_asset_amount_fn(asset=asset, as_of_date=summary_date)
        )

        planned_base = convert_currency(
            planned_native, asset.currency, base_currency, date=summary_date
        )
        executed_base = (
            convert_currency(executed_native, asset.currency, base_currency, date=summary_date)
            if executed_native is not None
            else None
        )
        effective_base = convert_currency(
            effective_native, asset.currency, base_currency, date=summary_date
        )
        deviation_base = (
            (executed_base - planned_base) if executed_base is not None else Decimal("0")
        )

        planned_total_base += planned_base
        executed_total_base += effective_base
        if checkin is not None:
            checked_count += 1

        rows.append(
            {
                "asset_id": asset.id,
                "asset_name": asset.name,
                "asset_category": asset.category,
                "asset_subcategory": asset.subcategory,
                "currency": asset.currency,
                "planned_closing_balance": serialize_money_fn(planned_native),
                "executed_closing_balance": serialize_money_fn(executed_native),
                "effective_closing_balance": serialize_money_fn(effective_native),
                "deviation": serialize_money_fn(
                    (executed_native - planned_native)
                    if executed_native is not None
                    else Decimal("0")
                ),
                "planned_closing_balance_base": serialize_money_fn(planned_base),
                "executed_closing_balance_base": serialize_money_fn(executed_base),
                "effective_closing_balance_base": serialize_money_fn(effective_base),
                "deviation_base": serialize_money_fn(deviation_base),
                "checkin": (
                    {
                        "id": checkin.id,
                        "status": checkin.status,
                        "closing_balance_real": serialize_money_fn(checkin.closing_balance_real),
                        "note": checkin.note,
                        "confirmed_at": checkin.confirmed_at.isoformat()
                        if checkin.confirmed_at
                        else None,
                        "updated_at": checkin.updated_at.isoformat()
                        if checkin.updated_at
                        else None,
                    }
                    if checkin is not None
                    else None
                ),
            }
        )

    deviation_total_base = executed_total_base - planned_total_base
    completion_ratio = (checked_count / len(rows)) if rows else 0.0

    return {
        "fiscal_year": fiscal_year,
        "month": month,
        "base_currency": base_currency,
        "planned_total": serialize_money_fn(planned_total_base),
        "executed_total": serialize_money_fn(executed_total_base),
        "deviation_total": serialize_money_fn(deviation_total_base),
        "completion_ratio": completion_ratio,
        "checkins_confirmed": checked_count,
        "checkins_expected": len(rows),
        "rows": rows,
    }


def build_liquidity_monthly_summary(*, user, fiscal_year: int, month: int) -> dict[str, object]:
    # Local import avoids hard import cycles while exposing a convenient public API.
    from . import services as services_facade

    return _build_liquidity_monthly_summary_impl(
        user=user,
        fiscal_year=fiscal_year,
        month=month,
        get_base_currency_for_user_fn=services_facade.get_base_currency_for_user,
        get_liquidity_asset_queryset_for_user_fn=services_facade.get_liquidity_asset_queryset_for_user,
        get_effective_asset_amount_fn=services_facade.get_effective_asset_amount,
        last_day_of_month_fn=services_facade._last_day_of_month,
        serialize_money_fn=services_facade._serialize_money,
    )
