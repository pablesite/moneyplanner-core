from __future__ import annotations

import calendar
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
from .services_assets_core import (
    _get_latest_opening_balance_tx_for_accounting_asset,
    get_effective_asset_amount,
)
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
    accounting_prefix_dates: dict[int, list[date]] = field(default_factory=dict)
    accounting_prefix_debits: dict[int, list[Decimal]] = field(default_factory=dict)
    accounting_prefix_credits: dict[int, list[Decimal]] = field(default_factory=dict)
    accounting_account_types: dict[int, str] = field(default_factory=dict)
    asset_opening_booking_dates: dict[int, date] = field(default_factory=dict)
    liability_opening_booking_dates: dict[int, date] = field(default_factory=dict)
    periodic_investment_schedules: dict[tuple[int, date], list[tuple[date, Decimal]]] = field(
        default_factory=dict
    )


def _build_position_data_cache(
    assets: list[Asset],
    liabilities: list[Liability],
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

    accounting_account_ids = {
        int(account_id)
        for account_id in [
            *(
                a.accounting_account_id
                for a in assets
                if a.tracking_mode == Asset.TrackingMode.ACCOUNTING
            ),
            *(
                li.accounting_account_id
                for li in liabilities
                if li.tracking_mode == Liability.TrackingMode.ACCOUNTING
            ),
        ]
        if account_id is not None
    }
    if accounting_account_ids:
        from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
        from accounting.services_ledger import build_net_worth_opening_balance_note

        for account_id, account_type in LedgerAccount.objects.filter(
            id__in=accounting_account_ids
        ).values_list("id", "account_type"):
            cache.accounting_account_types[int(account_id)] = str(account_type)

        running_debits: dict[int, Decimal] = {}
        running_credits: dict[int, Decimal] = {}
        from django.db.models import F

        for account_id, booking_date, side, amount in (
            LedgerEntry.objects.filter(
                account_id__in=accounting_account_ids,
                transaction__status=LedgerTransaction.Status.POSTED,
                # Safety boundary: only count entries from transactions owned by
                # the same user as the account (mirrors get_account_entries).
                transaction__user_id=F("account__user_id"),
            )
            .select_related("transaction")
            .order_by("account_id", "transaction__booking_date", "id")
            .values_list("account_id", "transaction__booking_date", "side", "amount")
        ):
            account_id_int = int(account_id)
            debit_total = running_debits.get(account_id_int, Decimal("0"))
            credit_total = running_credits.get(account_id_int, Decimal("0"))
            if side == LedgerEntry.Side.DEBIT:
                debit_total += Decimal(amount)
            else:
                credit_total += Decimal(amount)
            running_debits[account_id_int] = debit_total
            running_credits[account_id_int] = credit_total
            cache.accounting_prefix_dates.setdefault(account_id_int, []).append(booking_date)
            cache.accounting_prefix_debits.setdefault(account_id_int, []).append(debit_total)
            cache.accounting_prefix_credits.setdefault(account_id_int, []).append(credit_total)

        for asset in assets:
            if (
                asset.tracking_mode != Asset.TrackingMode.ACCOUNTING
                or asset.accounting_account_id is None
                or asset.category != Asset.Category.CASH
            ):
                continue
            opening_tx = _get_latest_opening_balance_tx_for_accounting_asset(
                user_id=asset.user_id,
                asset_id=asset.id,
                account_id=asset.accounting_account_id,
            )
            if opening_tx is not None:
                cache.asset_opening_booking_dates[asset.id] = opening_tx.booking_date

        for liability in liabilities:
            if (
                liability.tracking_mode != Liability.TrackingMode.ACCOUNTING
                or liability.accounting_account_id is None
            ):
                continue
            opening_note = build_net_worth_opening_balance_note(
                position_kind="liability",
                position_id=liability.id,
            )
            opening_booking_date = (
                LedgerTransaction.objects.filter(
                    status=LedgerTransaction.Status.POSTED,
                    notes=opening_note,
                    entries__account_id=liability.accounting_account_id,
                )
                .distinct()
                .order_by("-booking_date", "-id")
                .values_list("booking_date", flat=True)
                .first()
            )
            if opening_booking_date is not None:
                cache.liability_opening_booking_dates[liability.id] = opening_booking_date

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


def _same_day_prev_month(today: date) -> date:
    prev_month = today.month - 1 if today.month > 1 else 12
    prev_year = today.year if today.month > 1 else today.year - 1
    last_day = calendar.monthrange(prev_year, prev_month)[1]
    return date(prev_year, prev_month, min(today.day, last_day))


def _build_prev_month_same_day(
    *,
    today: date,
    assets: list,
    liabilities: list,
    base_currency: str,
    fx_cache: dict,
    pos_cache: "PositionDataCache",
    timeline_start_date: date,
) -> dict[str, object] | None:
    month_end = _month_end_for(today)
    if today >= month_end:
        return None

    comparison_date = _same_day_prev_month(today)
    if comparison_date < timeline_start_date:
        return None

    active_assets = [a for a in assets if a.start_date <= comparison_date]
    active_liabilities = [li for li in liabilities if li.start_date <= comparison_date]
    totals = calculate_totals(
        assets_qs=active_assets,
        liabilities_qs=active_liabilities,
        base_currency=base_currency,
        as_of_date=comparison_date,
        fx_cache=fx_cache,
        position_cache=pos_cache,
    )
    return {
        "date": comparison_date.isoformat(),
        "total_assets": _serialize_money(totals.total_assets),
        "total_liabilities": _serialize_money(totals.total_liabilities),
        "net_worth": _serialize_money(totals.total_assets - totals.total_liabilities),
    }


def build_net_worth_timeline(
    *,
    user,
    start_date: date | None = None,
    end_date: date | None = None,
    asset_category: str | None = None,
    liability_category: str | None = None,
) -> dict[str, object]:
    base_currency = get_base_currency_for_user(user=user)
    assets_qs = Asset.objects.filter(user=user).prefetch_related(
        "improvements",
        "contribution_intervals",
    )
    liabilities_qs = Liability.objects.filter(user=user)
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
        # For the current (incomplete) month, cap the effective date at today so that
        # periodic-contribution projections don't inflate the value beyond what is known.
        effective_date = min(point_date, timeline_end_date)
        totals = calculate_totals(
            assets_qs=active_assets,
            liabilities_qs=active_liabilities,
            base_currency=base_currency,
            as_of_date=effective_date,
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

    prev_month_same_day = _build_prev_month_same_day(
        today=timeline_end_date,
        assets=assets,
        liabilities=liabilities,
        base_currency=base_currency,
        fx_cache=fx_cache,
        pos_cache=pos_cache,
        timeline_start_date=timeline_start_date,
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
        "prev_month_same_day": prev_month_same_day,
    }


def build_asset_timeline(*, asset: Asset, end_date: date | None = None) -> dict[str, object]:
    base_currency = get_base_currency_for_user(user=asset.user)
    timeline_end_date = end_date or timezone.localdate()
    fx_cache = build_fx_cache({base_currency, asset.currency})
    rows: list[dict[str, object]] = []
    for point_date in _iter_month_ends(start_date=asset.start_date, end_date=timeline_end_date):
        native_value = get_effective_asset_amount(asset=asset, as_of_date=point_date)
        base_value = convert_currency_cached(
            native_value,
            asset.currency,
            base_currency,
            rate_date=point_date,
            fx_cache=fx_cache,
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
            native_value,
            liability.currency,
            base_currency,
            rate_date=point_date,
            fx_cache=fx_cache,
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
