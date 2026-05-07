from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from core.services import convert_currency

from .models import AssetValuation, LiabilityValuation, LiquidityMonthlyCheckin

PERIMETER_INTERNAL_EXPENSE_SUBCATEGORIES = {
    "crowdlending_p2p",
}


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
    get_liquid_liability_queryset_for_user_fn,
    get_effective_asset_amount_fn,
    get_effective_liability_amount_fn,
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
    liquid_liabilities = list(
        get_liquid_liability_queryset_for_user_fn(user=user).order_by("category", "name", "id")
    )
    checkins = {
        row.asset_id: row
        for row in LiquidityMonthlyCheckin.objects.filter(
            user=user,
            fiscal_year=fiscal_year,
            month=month,
        ).select_related("asset")
    }
    asset_checkpoints = {
        row.asset_id: row
        for row in AssetValuation.objects.filter(
            user=user,
            valuation_date=summary_date,
        ).select_related("asset")
    }
    liability_checkins = {
        row.liability_id: row
        for row in LiabilityValuation.objects.filter(
            user=user,
            valuation_date=summary_date,
        ).select_related("liability")
    }

    rows: list[dict[str, object]] = []
    planned_total_base = Decimal("0")
    executed_total_base = Decimal("0")
    gross_asset_planned_total_base = Decimal("0")
    gross_asset_executed_total_base = Decimal("0")
    liquid_liability_planned_total_base = Decimal("0")
    liquid_liability_executed_total_base = Decimal("0")
    checked_count = 0
    ledger_count = 0
    ledger_available_count = 0
    fallback_count = 0
    perimeter_internal_expense_total_base = Decimal("0")
    perimeter_asset_ids = {asset.id for asset in liquid_assets}

    for asset in liquid_assets:
        planned_native = Decimal(asset.amount or 0)
        liquidity_checkin = checkins.get(asset.id)
        asset_checkpoint = asset_checkpoints.get(asset.id)
        checkin = liquidity_checkin if asset.category == "cash" else asset_checkpoint
        effective_native = get_effective_asset_amount_fn(asset=asset, as_of_date=summary_date)
        ledger_available = False
        ledger_covered = False
        if getattr(asset, "tracking_mode", None) == "accounting" and getattr(
            asset, "accounting_account_id", None
        ):
            from accounting.models import LedgerTransaction
            from accounting.services_ledger import get_user_ledger_account, has_account_entries

            accounting_account = get_user_ledger_account(
                user_id=user.id,
                account_id=asset.accounting_account_id,
                expected_type="asset",
            )
            ledger_available = (
                accounting_account is not None and accounting_account.currency == asset.currency
            )
            ledger_covered = ledger_available and has_account_entries(
                account=accounting_account,
                as_of_date=summary_date,
                status=cast(str, LedgerTransaction.Status.POSTED),
            )
        if ledger_covered and checkin is not None:
            executed_native = (
                checkin.closing_balance_real if asset.category == "cash" else asset_checkpoint.value
            )
            coverage_source = "checkin"
            fallback_count += 1
            checked_count += 1
        elif ledger_available:
            if checkin is not None:
                executed_native = (
                    checkin.closing_balance_real
                    if asset.category == "cash"
                    else asset_checkpoint.value
                )
                coverage_source = "checkin"
                fallback_count += 1
                checked_count += 1
            else:
                executed_native = effective_native
                coverage_source = "ledger"
                ledger_count += 1
                checked_count += 1
        elif checkin is not None:
            executed_native = (
                checkin.closing_balance_real if asset.category == "cash" else asset_checkpoint.value
            )
            coverage_source = "checkin"
            fallback_count += 1
            checked_count += 1
        else:
            executed_native = None
            coverage_source = "none"
        if ledger_available:
            ledger_available_count += 1

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
        gross_asset_planned_total_base += planned_base
        if executed_base is not None:
            executed_total_base += executed_base
            gross_asset_executed_total_base += executed_base

        rows.append(
            {
                "row_type": "asset",
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
                "coverage_source": coverage_source,
                "ledger_available": ledger_available,
                "checkin": (
                    {
                        "id": checkin.id,
                        "status": checkin.status if asset.category == "cash" else "adjusted",
                        "closing_balance_real": serialize_money_fn(
                            checkin.closing_balance_real
                            if asset.category == "cash"
                            else asset_checkpoint.value
                        ),
                        "note": checkin.note,
                        "confirmed_at": (
                            checkin.confirmed_at.isoformat()
                            if asset.category == "cash" and checkin.confirmed_at
                            else checkin.updated_at.isoformat()
                        )
                        if checkin.updated_at
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

    if perimeter_asset_ids:
        from accounting.models import LedgerEntry, LedgerTransaction

        internal_expense_entries = LedgerEntry.objects.filter(
            transaction__user=user,
            transaction__status=LedgerTransaction.Status.POSTED,
            transaction__booking_date__year=fiscal_year,
            transaction__booking_date__month=month,
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="financial_investments",
            subcategory_key__in=PERIMETER_INTERNAL_EXPENSE_SUBCATEGORIES,
            asset_id__in=perimeter_asset_ids,
        ).select_related("transaction")
        for entry in internal_expense_entries:
            amount = Decimal(entry.amount)
            signed_amount = amount if entry.side == LedgerEntry.Side.DEBIT else -amount
            perimeter_internal_expense_total_base += convert_currency(
                signed_amount,
                entry.currency,
                base_currency,
                date=entry.transaction.booking_date,
            )

    for liability in liquid_liabilities:
        planned_native = Decimal(liability.amount or 0)
        liability_checkin = liability_checkins.get(liability.id)
        executed_native = get_effective_liability_amount_fn(
            liability=liability,
            as_of_date=summary_date,
        )
        ledger_available = False
        if getattr(liability, "tracking_mode", None) == "accounting" and getattr(
            liability, "accounting_account_id", None
        ):
            from accounting.models import LedgerTransaction
            from accounting.services_ledger import get_user_ledger_account, has_account_entries

            accounting_account = get_user_ledger_account(
                user_id=user.id,
                account_id=liability.accounting_account_id,
                expected_type="liability",
            )
            ledger_available = (
                accounting_account is not None and accounting_account.currency == liability.currency
            )
            if ledger_available and has_account_entries(
                account=accounting_account,
                as_of_date=summary_date,
                status=cast(str, LedgerTransaction.Status.POSTED),
            ):
                ledger_count += 1
        planned_base = convert_currency(
            planned_native,
            liability.currency,
            base_currency,
            date=summary_date,
        )
        executed_base = convert_currency(
            executed_native,
            liability.currency,
            base_currency,
            date=summary_date,
        )
        deviation_base = executed_base - planned_base

        planned_total_base -= planned_base
        executed_total_base -= executed_base
        liquid_liability_planned_total_base += planned_base
        liquid_liability_executed_total_base += executed_base
        checked_count += 1
        if ledger_available:
            ledger_available_count += 1

        rows.append(
            {
                "row_type": "liability",
                "asset_id": -liability.id,
                "asset_name": liability.name,
                "asset_category": "liability",
                "asset_subcategory": liability.category,
                "liability_id": liability.id,
                "liability_name": liability.name,
                "liability_category": liability.category,
                "currency": liability.currency,
                "planned_closing_balance": serialize_money_fn(planned_native),
                "executed_closing_balance": serialize_money_fn(executed_native),
                "effective_closing_balance": serialize_money_fn(executed_native),
                "deviation": serialize_money_fn(executed_native - planned_native),
                "planned_closing_balance_base": serialize_money_fn(-planned_base),
                "executed_closing_balance_base": serialize_money_fn(-executed_base),
                "effective_closing_balance_base": serialize_money_fn(-executed_base),
                "deviation_base": serialize_money_fn(-deviation_base),
                "coverage_source": "checkin"
                if liability_checkin is not None
                else ("ledger" if ledger_available else "liability"),
                "ledger_available": ledger_available,
                "checkin": (
                    {
                        "id": liability_checkin.id,
                        "status": "adjusted",
                        "closing_balance_real": serialize_money_fn(liability_checkin.value),
                        "note": liability_checkin.note,
                        "confirmed_at": liability_checkin.updated_at.isoformat()
                        if liability_checkin.updated_at
                        else None,
                        "updated_at": liability_checkin.updated_at.isoformat()
                        if liability_checkin.updated_at
                        else None,
                    }
                    if liability_checkin is not None
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
        "gross_asset_planned_total": serialize_money_fn(gross_asset_planned_total_base),
        "gross_asset_executed_total": serialize_money_fn(gross_asset_executed_total_base),
        "liquid_liability_planned_total": serialize_money_fn(liquid_liability_planned_total_base),
        "liquid_liability_executed_total": serialize_money_fn(liquid_liability_executed_total_base),
        "perimeter_internal_expense_total": serialize_money_fn(
            perimeter_internal_expense_total_base
        ),
        "completion_ratio": completion_ratio,
        "checkins_confirmed": fallback_count,
        "checkins_expected": len(rows),
        "coverage_confirmed": checked_count,
        "coverage_expected": len(rows),
        "ledger_rows_confirmed": ledger_count,
        "fallback_rows_confirmed": fallback_count,
        "has_ledger_data": ledger_available_count > 0,
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
        get_liquid_liability_queryset_for_user_fn=services_facade.get_liquid_liability_queryset_for_user,
        get_effective_asset_amount_fn=services_facade.get_effective_asset_amount,
        get_effective_liability_amount_fn=services_facade.get_effective_liability_amount,
        last_day_of_month_fn=services_facade._last_day_of_month,
        serialize_money_fn=services_facade._serialize_money,
    )
