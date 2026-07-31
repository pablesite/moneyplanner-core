from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import cast

from django.core.exceptions import ValidationError
from django.db.models import Q
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
    OPENING_ASSET_NOTE_PREFIX,
    OPENING_BALANCE_DESCRIPTION_PREFIX,
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
    accounting_accounts: dict[int, dict[str, object]] = field(default_factory=dict)
    asset_opening_booking_dates: dict[int, date] = field(default_factory=dict)
    liability_opening_booking_dates: dict[int, date] = field(default_factory=dict)
    periodic_investment_schedules: dict[tuple[int, date], list[tuple[date, Decimal]]] = field(
        default_factory=dict
    )
    inflation_region: str | None = None
    inflation_indexes: dict[str, list[tuple[date, Decimal]]] = field(default_factory=dict)


def _cache_legacy_asset_opening_dates(
    *,
    cache: PositionDataCache,
    assets: list[Asset],
) -> set[int]:
    legacy_opening_assets = [
        asset
        for asset in assets
        if asset.tracking_mode == Asset.TrackingMode.ACCOUNTING
        and asset.accounting_account_id is not None
        and asset.category == Asset.Category.CASH
        and asset.id not in cache.asset_opening_booking_dates
        and asset.user_id is not None
    ]
    legacy_checked_asset_ids = {asset.id for asset in legacy_opening_assets}
    if not legacy_opening_assets:
        return legacy_checked_asset_ids

    from accounting.models import LedgerAccount, LedgerTransaction

    legacy_asset_by_id = {asset.id: asset for asset in legacy_opening_assets}
    legacy_assets_by_account: dict[int, list[Asset]] = {}
    for asset in legacy_opening_assets:
        legacy_assets_by_account.setdefault(int(asset.accounting_account_id), []).append(asset)
    legacy_account_ids = set(legacy_assets_by_account)
    legacy_asset_ids = set(legacy_asset_by_id)
    legacy_user_ids = {asset.user_id for asset in legacy_opening_assets}
    legacy_transactions = (
        LedgerTransaction.objects.filter(
            user_id__in=legacy_user_ids,
            status=LedgerTransaction.Status.POSTED,
            entries__account_id__in=legacy_account_ids,
        )
        .filter(
            Q(
                origin=LedgerTransaction.Origin.SYSTEM,
                notes__startswith=OPENING_ASSET_NOTE_PREFIX,
                entries__asset_id__in=legacy_asset_ids,
            )
            | Q(
                origin=LedgerTransaction.Origin.SYSTEM,
                description__startswith=OPENING_BALANCE_DESCRIPTION_PREFIX,
            )
        )
        .distinct()
        .prefetch_related("entries__account")
        .order_by("-booking_date", "-id")
    )
    for transaction in legacy_transactions:
        entries = list(transaction.entries.all())
        if len(entries) != 2:
            continue
        for position_entry in entries:
            account_id = int(position_entry.account_id)
            candidate_assets = legacy_assets_by_account.get(account_id, [])
            if position_entry.asset_id is not None:
                candidate_asset = legacy_asset_by_id.get(position_entry.asset_id)
                candidate_assets = [candidate_asset] if candidate_asset is not None else []
            if not candidate_assets:
                continue

            counterpart_entries = [entry for entry in entries if entry.id != position_entry.id]
            if len(counterpart_entries) != 1:
                continue
            counterpart_entry = counterpart_entries[0]
            for asset in candidate_assets:
                if asset.id in cache.asset_opening_booking_dates:
                    continue
                if transaction.user_id != asset.user_id:
                    continue
                if position_entry.asset_id not in (None, asset.id):
                    continue
                if counterpart_entry.account.account_type != LedgerAccount.AccountType.EQUITY:
                    continue
                if position_entry.amount != counterpart_entry.amount:
                    continue
                if position_entry.side == counterpart_entry.side:
                    continue
                cache.asset_opening_booking_dates[asset.id] = transaction.booking_date
    return legacy_checked_asset_ids


def _cache_inflation_indexes_if_needed(
    *,
    cache: PositionDataCache,
    assets: list[Asset],
) -> None:
    needs_inflation_indexes = any(
        asset.category == Asset.Category.FURNISHINGS
        and asset.currency == "EUR"
        and asset.amortization_method == Asset.AmortizationMethod.STRAIGHT_LINE
        for asset in assets
    )
    if not needs_inflation_indexes:
        return

    from accounts.models import UserSettings
    from core.models import InflationIndex

    user_ids = {asset.user_id for asset in assets if asset.user_id is not None}
    region = cast(str, InflationIndex.Region.ES)
    if user_ids:
        selected_region = (
            UserSettings.objects.filter(user_id__in=user_ids)
            .values_list("inflation_region", flat=True)
            .first()
        )
        normalized_region = str(selected_region or "").strip().upper()
        if normalized_region:
            region = normalized_region

    cache.inflation_region = region
    cache.inflation_indexes[region] = [
        (period, Decimal(index))
        for period, index in InflationIndex.objects.filter(region=region)
        .order_by("period")
        .values_list("period", "index")
    ]


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

        for (
            account_id,
            account_type,
            currency,
            asset_id,
            liability_id,
        ) in LedgerAccount.objects.filter(id__in=accounting_account_ids).values_list(
            "id", "account_type", "currency", "asset_id", "liability_id"
        ):
            cache.accounting_account_types[int(account_id)] = str(account_type)
            cache.accounting_accounts[int(account_id)] = {
                "account_type": str(account_type),
                "currency": str(currency),
                "asset_id": asset_id,
                "liability_id": liability_id,
            }

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

        asset_opening_note_by_id = {
            asset.id: build_net_worth_opening_balance_note(
                position_kind="asset",
                position_id=asset.id,
            )
            for asset in assets
            if asset.tracking_mode == Asset.TrackingMode.ACCOUNTING
            and asset.accounting_account_id is not None
            and asset.category == Asset.Category.CASH
        }
        liability_opening_note_by_id = {
            liability.id: build_net_worth_opening_balance_note(
                position_kind="liability",
                position_id=liability.id,
            )
            for liability in liabilities
            if liability.tracking_mode == Liability.TrackingMode.ACCOUNTING
            and liability.accounting_account_id is not None
        }
        note_to_target = {
            **{
                note: ("asset", position_id)
                for position_id, note in asset_opening_note_by_id.items()
            },
            **{
                note: ("liability", position_id)
                for position_id, note in liability_opening_note_by_id.items()
            },
        }
        note_to_account_id = {
            **{
                note: asset.accounting_account_id
                for asset in assets
                if (note := asset_opening_note_by_id.get(asset.id)) is not None
            },
            **{
                note: liability.accounting_account_id
                for liability in liabilities
                if (note := liability_opening_note_by_id.get(liability.id)) is not None
            },
        }
        opening_notes = list(note_to_target)
        if opening_notes:
            seen_notes: set[str] = set()
            opening_rows = (
                LedgerTransaction.objects.filter(
                    status=LedgerTransaction.Status.POSTED,
                    notes__in=opening_notes,
                    entries__account_id__in=accounting_account_ids,
                )
                .order_by("notes", "-booking_date", "-id")
                .values_list("notes", "booking_date", "entries__account_id")
            )
            for note, booking_date, account_id in opening_rows:
                if note in seen_notes or int(account_id) != int(note_to_account_id[note]):
                    continue
                target_kind, target_id = note_to_target[note]
                if target_kind == "asset":
                    cache.asset_opening_booking_dates[target_id] = booking_date
                else:
                    cache.liability_opening_booking_dates[target_id] = booking_date
                seen_notes.add(note)

        legacy_checked_asset_ids = _cache_legacy_asset_opening_dates(
            cache=cache,
            assets=assets,
        )

        for asset in assets:
            if (
                asset.tracking_mode != Asset.TrackingMode.ACCOUNTING
                or asset.accounting_account_id is None
                or asset.category != Asset.Category.CASH
                or asset.id in cache.asset_opening_booking_dates
                or asset.id in legacy_checked_asset_ids
            ):
                continue
            opening_tx = _get_latest_opening_balance_tx_for_accounting_asset(
                user_id=asset.user_id,
                asset_id=asset.id,
                account_id=asset.accounting_account_id,
            )
            if opening_tx is not None:
                cache.asset_opening_booking_dates[asset.id] = opening_tx.booking_date

    _cache_inflation_indexes_if_needed(
        cache=cache,
        assets=assets,
    )

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


def _same_day_prev_month(today: date) -> date | None:
    prev_month = today.month - 1 if today.month > 1 else 12
    prev_year = today.year if today.month > 1 else today.year - 1
    last_day = calendar.monthrange(prev_year, prev_month)[1]
    if today.day > last_day:
        return None
    return date(prev_year, prev_month, today.day)


def _same_day_prev_year(today: date) -> date | None:
    try:
        return today.replace(year=today.year - 1)
    except ValueError:
        return None


def _serialize_timeline_point(
    *,
    comparison_date: date | None,
    assets: list,
    liabilities: list,
    base_currency: str,
    fx_cache: dict,
    pos_cache: "PositionDataCache",
    timeline_start_date: date,
) -> dict[str, object] | None:
    if comparison_date is None or comparison_date < timeline_start_date:
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


def _build_timeline_comparison_points(
    *,
    today: date,
    assets: list,
    liabilities: list,
    base_currency: str,
    fx_cache: dict,
    pos_cache: "PositionDataCache",
    timeline_start_date: date,
) -> dict[str, object | None]:
    start_of_month = date(today.year, today.month, 1)
    previous_month_close = start_of_month.fromordinal(start_of_month.toordinal() - 1)
    previous_year_close = date(today.year - 1, 12, 31)

    return {
        "previous_month_close": _serialize_timeline_point(
            comparison_date=previous_month_close,
            assets=assets,
            liabilities=liabilities,
            base_currency=base_currency,
            fx_cache=fx_cache,
            pos_cache=pos_cache,
            timeline_start_date=timeline_start_date,
        ),
        "same_day_previous_month": _serialize_timeline_point(
            comparison_date=_same_day_prev_month(today),
            assets=assets,
            liabilities=liabilities,
            base_currency=base_currency,
            fx_cache=fx_cache,
            pos_cache=pos_cache,
            timeline_start_date=timeline_start_date,
        ),
        "previous_year_close": _serialize_timeline_point(
            comparison_date=previous_year_close,
            assets=assets,
            liabilities=liabilities,
            base_currency=base_currency,
            fx_cache=fx_cache,
            pos_cache=pos_cache,
            timeline_start_date=timeline_start_date,
        ),
        "same_day_previous_year": _serialize_timeline_point(
            comparison_date=_same_day_prev_year(today),
            assets=assets,
            liabilities=liabilities,
            base_currency=base_currency,
            fx_cache=fx_cache,
            pos_cache=pos_cache,
            timeline_start_date=timeline_start_date,
        ),
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
                "assets_by_category": {
                    category: _serialize_money(amount)
                    for category, amount in totals.assets_by_category.items()
                },
                "asset_positions": len(active_assets),
                "liability_positions": len(active_liabilities),
            }
        )

    comparisons = _build_timeline_comparison_points(
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
        "comparisons": comparisons,
        "prev_month_same_day": comparisons["same_day_previous_month"],
    }


def build_asset_timeline(*, asset: Asset, end_date: date | None = None) -> dict[str, object]:
    asset = (
        Asset.objects.select_related("user")
        .prefetch_related("improvements", "contribution_intervals")
        .get(id=asset.id)
    )
    base_currency = get_base_currency_for_user(user=asset.user)
    timeline_end_date = end_date or timezone.localdate()
    fx_cache = build_fx_cache({base_currency, asset.currency})
    pos_cache = _build_position_data_cache([asset], [])
    rows: list[dict[str, object]] = []
    for point_date in _iter_month_ends(start_date=asset.start_date, end_date=timeline_end_date):
        native_value = get_effective_asset_amount(
            asset=asset,
            as_of_date=point_date,
            position_cache=pos_cache,
        )
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
    liability = Liability.objects.select_related("user").get(id=liability.id)
    base_currency = get_base_currency_for_user(user=liability.user)
    timeline_end_date = end_date or timezone.localdate()
    fx_cache = build_fx_cache({base_currency, liability.currency})
    pos_cache = _build_position_data_cache([], [liability])
    rows: list[dict[str, object]] = []
    for point_date in _iter_month_ends(start_date=liability.start_date, end_date=timeline_end_date):
        native_value = get_effective_liability_amount(
            liability=liability,
            as_of_date=point_date,
            position_cache=pos_cache,
        )
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
