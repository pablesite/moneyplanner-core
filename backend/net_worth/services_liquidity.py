from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import cast

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from core.services import convert_currency

from .models import AssetValuation, LiabilityValuation, LiquidityMonthlyCheckin


ZERO = Decimal("0")


@dataclass
class LiquiditySummaryInputs:
    base_currency: str
    summary_date: date
    liquid_assets: list
    liquid_liabilities: list
    checkins: dict[int, LiquidityMonthlyCheckin]
    asset_checkpoints: dict[int, AssetValuation]
    liability_checkins: dict[int, LiabilityValuation]


@dataclass
class LiquiditySummaryTotals:
    planned_total_base: Decimal = ZERO
    executed_total_base: Decimal = ZERO
    gross_asset_planned_total_base: Decimal = ZERO
    gross_asset_executed_total_base: Decimal = ZERO
    liquid_liability_planned_total_base: Decimal = ZERO
    liquid_liability_executed_total_base: Decimal = ZERO
    perimeter_internal_expense_total_base: Decimal = ZERO
    checked_count: int = 0
    ledger_count: int = 0
    ledger_available_count: int = 0
    fallback_count: int = 0

    def add_asset(
        self,
        *,
        planned_base: Decimal,
        executed_base: Decimal | None,
        ledger_available: bool,
        checked: bool,
        ledger_confirmed: bool,
        fallback_confirmed: bool,
    ) -> None:
        self.planned_total_base += planned_base
        self.gross_asset_planned_total_base += planned_base
        if executed_base is not None:
            self.executed_total_base += executed_base
            self.gross_asset_executed_total_base += executed_base
        self._add_coverage_counts(
            ledger_available=ledger_available,
            checked=checked,
            ledger_confirmed=ledger_confirmed,
            fallback_confirmed=fallback_confirmed,
        )

    def add_liability(
        self,
        *,
        planned_base: Decimal,
        executed_base: Decimal,
        ledger_available: bool,
        ledger_confirmed: bool,
    ) -> None:
        self.planned_total_base -= planned_base
        self.executed_total_base -= executed_base
        self.liquid_liability_planned_total_base += planned_base
        self.liquid_liability_executed_total_base += executed_base
        self._add_coverage_counts(
            ledger_available=ledger_available,
            checked=True,
            ledger_confirmed=ledger_confirmed,
            fallback_confirmed=False,
        )

    def _add_coverage_counts(
        self,
        *,
        ledger_available: bool,
        checked: bool,
        ledger_confirmed: bool,
        fallback_confirmed: bool,
    ) -> None:
        if checked:
            self.checked_count += 1
        if ledger_available:
            self.ledger_available_count += 1
        if ledger_confirmed:
            self.ledger_count += 1
        if fallback_confirmed:
            self.fallback_count += 1


@dataclass(frozen=True)
class PositionCoverage:
    ledger_available: bool
    ledger_covered: bool


@dataclass(frozen=True)
class AssetExecution:
    executed_native: Decimal | None
    coverage_source: str
    checked: bool
    ledger_confirmed: bool
    fallback_confirmed: bool


@dataclass
class LiquiditySummaryBuild:
    rows: list[dict[str, object]] = field(default_factory=list)
    totals: LiquiditySummaryTotals = field(default_factory=LiquiditySummaryTotals)


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

    inputs = _load_liquidity_summary_inputs(
        user=user,
        fiscal_year=fiscal_year,
        month=month,
        get_base_currency_for_user_fn=get_base_currency_for_user_fn,
        get_liquidity_asset_queryset_for_user_fn=get_liquidity_asset_queryset_for_user_fn,
        get_liquid_liability_queryset_for_user_fn=get_liquid_liability_queryset_for_user_fn,
        last_day_of_month_fn=last_day_of_month_fn,
    )
    build = _build_liquidity_summary_rows(
        user=user,
        fiscal_year=fiscal_year,
        month=month,
        inputs=inputs,
        get_effective_asset_amount_fn=get_effective_asset_amount_fn,
        get_effective_liability_amount_fn=get_effective_liability_amount_fn,
        serialize_money_fn=serialize_money_fn,
    )

    totals = build.totals
    deviation_total_base = totals.executed_total_base - totals.planned_total_base
    completion_ratio = (totals.checked_count / len(build.rows)) if build.rows else 0.0

    return {
        "fiscal_year": fiscal_year,
        "month": month,
        "base_currency": inputs.base_currency,
        "planned_total": serialize_money_fn(totals.planned_total_base),
        "executed_total": serialize_money_fn(totals.executed_total_base),
        "deviation_total": serialize_money_fn(deviation_total_base),
        "gross_asset_planned_total": serialize_money_fn(totals.gross_asset_planned_total_base),
        "gross_asset_executed_total": serialize_money_fn(totals.gross_asset_executed_total_base),
        "liquid_liability_planned_total": serialize_money_fn(
            totals.liquid_liability_planned_total_base
        ),
        "liquid_liability_executed_total": serialize_money_fn(
            totals.liquid_liability_executed_total_base
        ),
        "perimeter_internal_expense_total": serialize_money_fn(
            totals.perimeter_internal_expense_total_base
        ),
        "completion_ratio": completion_ratio,
        "checkins_confirmed": totals.fallback_count,
        "checkins_expected": len(build.rows),
        "coverage_confirmed": totals.checked_count,
        "coverage_expected": len(build.rows),
        "ledger_rows_confirmed": totals.ledger_count,
        "fallback_rows_confirmed": totals.fallback_count,
        "has_ledger_data": totals.ledger_available_count > 0,
        "rows": build.rows,
    }


def _load_liquidity_summary_inputs(
    *,
    user,
    fiscal_year: int,
    month: int,
    get_base_currency_for_user_fn,
    get_liquidity_asset_queryset_for_user_fn,
    get_liquid_liability_queryset_for_user_fn,
    last_day_of_month_fn,
) -> LiquiditySummaryInputs:
    summary_date = date(fiscal_year, month, last_day_of_month_fn(fiscal_year, month))
    return LiquiditySummaryInputs(
        base_currency=get_base_currency_for_user_fn(user=user),
        summary_date=summary_date,
        liquid_assets=list(
            get_liquidity_asset_queryset_for_user_fn(user=user).order_by(
                "subcategory", "name", "id"
            )
        ),
        liquid_liabilities=list(
            get_liquid_liability_queryset_for_user_fn(user=user).order_by("category", "name", "id")
        ),
        checkins={
            row.asset_id: row
            for row in LiquidityMonthlyCheckin.objects.filter(
                user=user,
                fiscal_year=fiscal_year,
                month=month,
            ).select_related("asset")
        },
        asset_checkpoints={
            row.asset_id: row
            for row in AssetValuation.objects.filter(
                user=user,
                valuation_date=summary_date,
            ).select_related("asset")
        },
        liability_checkins={
            row.liability_id: row
            for row in LiabilityValuation.objects.filter(
                user=user,
                valuation_date=summary_date,
            ).select_related("liability")
        },
    )


def _build_liquidity_summary_rows(
    *,
    user,
    fiscal_year: int,
    month: int,
    inputs: LiquiditySummaryInputs,
    get_effective_asset_amount_fn,
    get_effective_liability_amount_fn,
    serialize_money_fn,
) -> LiquiditySummaryBuild:
    build = LiquiditySummaryBuild()
    for asset in inputs.liquid_assets:
        row = _build_asset_summary_row(
            user=user,
            asset=asset,
            inputs=inputs,
            get_effective_asset_amount_fn=get_effective_asset_amount_fn,
            serialize_money_fn=serialize_money_fn,
            totals=build.totals,
        )
        build.rows.append(row)

    build.totals.perimeter_internal_expense_total_base = (
        _compute_perimeter_internal_expense_total_base(
            user=user,
            fiscal_year=fiscal_year,
            month=month,
            inputs=inputs,
        )
    )

    for liability in inputs.liquid_liabilities:
        row = _build_liability_summary_row(
            user=user,
            liability=liability,
            inputs=inputs,
            get_effective_liability_amount_fn=get_effective_liability_amount_fn,
            serialize_money_fn=serialize_money_fn,
            totals=build.totals,
        )
        build.rows.append(row)
    return build


def _resolve_position_accounting_coverage(
    *,
    user,
    position,
    summary_date: date,
    expected_type: str,
) -> PositionCoverage:
    if not getattr(position, "tracking_mode", None) == "accounting":
        return PositionCoverage(ledger_available=False, ledger_covered=False)
    if not getattr(position, "accounting_account_id", None):
        return PositionCoverage(ledger_available=False, ledger_covered=False)

    from accounting.models import LedgerTransaction
    from accounting.services_ledger import get_user_ledger_account, has_account_entries

    accounting_account = get_user_ledger_account(
        user_id=user.id,
        account_id=position.accounting_account_id,
        expected_type=expected_type,
    )
    ledger_available = (
        accounting_account is not None and accounting_account.currency == position.currency
    )
    ledger_covered = ledger_available and has_account_entries(
        account=accounting_account,
        as_of_date=summary_date,
        status=cast(str, LedgerTransaction.Status.POSTED),
    )
    return PositionCoverage(
        ledger_available=ledger_available,
        ledger_covered=ledger_covered,
    )


def _select_asset_checkin(*, asset, inputs: LiquiditySummaryInputs):
    if asset.category == "cash":
        return inputs.checkins.get(asset.id)
    return inputs.asset_checkpoints.get(asset.id)


def _asset_checkin_value(*, asset, checkin) -> Decimal:
    return checkin.closing_balance_real if asset.category == "cash" else checkin.value


def _resolve_asset_execution(
    *,
    asset,
    checkin,
    effective_native: Decimal,
    coverage: PositionCoverage,
) -> AssetExecution:
    if coverage.ledger_covered and checkin is not None:
        return AssetExecution(
            executed_native=_asset_checkin_value(asset=asset, checkin=checkin),
            coverage_source="checkin",
            checked=True,
            ledger_confirmed=False,
            fallback_confirmed=True,
        )
    if coverage.ledger_available:
        if checkin is not None:
            return AssetExecution(
                executed_native=_asset_checkin_value(asset=asset, checkin=checkin),
                coverage_source="checkin",
                checked=True,
                ledger_confirmed=False,
                fallback_confirmed=True,
            )
        return AssetExecution(
            executed_native=effective_native,
            coverage_source="ledger",
            checked=True,
            ledger_confirmed=True,
            fallback_confirmed=False,
        )
    if checkin is not None:
        return AssetExecution(
            executed_native=_asset_checkin_value(asset=asset, checkin=checkin),
            coverage_source="checkin",
            checked=True,
            ledger_confirmed=False,
            fallback_confirmed=True,
        )
    return AssetExecution(
        executed_native=None,
        coverage_source="none",
        checked=False,
        ledger_confirmed=False,
        fallback_confirmed=False,
    )


def _build_asset_summary_row(
    *,
    user,
    asset,
    inputs: LiquiditySummaryInputs,
    get_effective_asset_amount_fn,
    serialize_money_fn,
    totals: LiquiditySummaryTotals,
) -> dict[str, object]:
    planned_native = Decimal(asset.amount or 0)
    checkin = _select_asset_checkin(asset=asset, inputs=inputs)
    effective_native = get_effective_asset_amount_fn(
        asset=asset,
        as_of_date=inputs.summary_date,
    )
    coverage = _resolve_position_accounting_coverage(
        user=user,
        position=asset,
        summary_date=inputs.summary_date,
        expected_type="asset",
    )
    execution = _resolve_asset_execution(
        asset=asset,
        checkin=checkin,
        effective_native=effective_native,
        coverage=coverage,
    )

    planned_base = convert_currency(
        planned_native,
        asset.currency,
        inputs.base_currency,
        date=inputs.summary_date,
    )
    executed_base = (
        convert_currency(
            execution.executed_native,
            asset.currency,
            inputs.base_currency,
            date=inputs.summary_date,
        )
        if execution.executed_native is not None
        else None
    )
    effective_base = convert_currency(
        effective_native,
        asset.currency,
        inputs.base_currency,
        date=inputs.summary_date,
    )
    deviation_base = (executed_base - planned_base) if executed_base is not None else ZERO
    totals.add_asset(
        planned_base=planned_base,
        executed_base=executed_base,
        ledger_available=coverage.ledger_available,
        checked=execution.checked,
        ledger_confirmed=execution.ledger_confirmed,
        fallback_confirmed=execution.fallback_confirmed,
    )

    return {
        "row_type": "asset",
        "asset_id": asset.id,
        "asset_name": asset.name,
        "asset_category": asset.category,
        "asset_subcategory": asset.subcategory,
        "annual_interest_tae": serialize_money_fn(asset.annual_interest_tae),
        "currency": asset.currency,
        "planned_closing_balance": serialize_money_fn(planned_native),
        "executed_closing_balance": serialize_money_fn(execution.executed_native),
        "effective_closing_balance": serialize_money_fn(effective_native),
        "deviation": serialize_money_fn(
            (execution.executed_native - planned_native)
            if execution.executed_native is not None
            else ZERO
        ),
        "planned_closing_balance_base": serialize_money_fn(planned_base),
        "executed_closing_balance_base": serialize_money_fn(executed_base),
        "effective_closing_balance_base": serialize_money_fn(effective_base),
        "deviation_base": serialize_money_fn(deviation_base),
        "coverage_source": execution.coverage_source,
        "ledger_available": coverage.ledger_available,
        "checkin": _serialize_asset_checkin(
            asset=asset,
            checkin=checkin,
            serialize_money_fn=serialize_money_fn,
        ),
    }


def _serialize_asset_checkin(*, asset, checkin, serialize_money_fn) -> dict | None:
    if checkin is None:
        return None
    return {
        "id": checkin.id,
        "status": checkin.status if asset.category == "cash" else "adjusted",
        "closing_balance_real": serialize_money_fn(
            _asset_checkin_value(asset=asset, checkin=checkin)
        ),
        "note": checkin.note,
        "confirmed_at": (
            checkin.confirmed_at.isoformat()
            if asset.category == "cash" and checkin.confirmed_at
            else checkin.updated_at.isoformat()
        )
        if checkin.updated_at
        else None,
        "updated_at": checkin.updated_at.isoformat() if checkin.updated_at else None,
    }


def _compute_perimeter_internal_expense_total_base(
    *,
    user,
    fiscal_year: int,
    month: int,
    inputs: LiquiditySummaryInputs,
) -> Decimal:
    perimeter_asset_ids = {asset.id for asset in inputs.liquid_assets}
    if not perimeter_asset_ids:
        return ZERO

    from accounting.models import LedgerEntry, LedgerTransaction

    internal_expense_entries = LedgerEntry.objects.filter(
        transaction__user=user,
        transaction__status=LedgerTransaction.Status.POSTED,
        transaction__booking_date__year=fiscal_year,
        transaction__booking_date__month=month,
        flow_family=LedgerEntry.FlowFamily.EXPENSE,
        category_key="financial_investments",
        asset_id__in=perimeter_asset_ids,
    ).select_related("transaction")

    total = ZERO
    for entry in internal_expense_entries:
        amount = Decimal(entry.amount)
        signed_amount = amount if entry.side == LedgerEntry.Side.DEBIT else -amount
        total += convert_currency(
            signed_amount,
            entry.currency,
            inputs.base_currency,
            date=entry.transaction.booking_date,
        )
    return total


def _build_liability_summary_row(
    *,
    user,
    liability,
    inputs: LiquiditySummaryInputs,
    get_effective_liability_amount_fn,
    serialize_money_fn,
    totals: LiquiditySummaryTotals,
) -> dict[str, object]:
    planned_native = Decimal(liability.amount or 0)
    liability_checkin = inputs.liability_checkins.get(liability.id)
    executed_native = get_effective_liability_amount_fn(
        liability=liability,
        as_of_date=inputs.summary_date,
    )
    coverage = _resolve_position_accounting_coverage(
        user=user,
        position=liability,
        summary_date=inputs.summary_date,
        expected_type="liability",
    )

    planned_base = convert_currency(
        planned_native,
        liability.currency,
        inputs.base_currency,
        date=inputs.summary_date,
    )
    executed_base = convert_currency(
        executed_native,
        liability.currency,
        inputs.base_currency,
        date=inputs.summary_date,
    )
    deviation_base = executed_base - planned_base
    totals.add_liability(
        planned_base=planned_base,
        executed_base=executed_base,
        ledger_available=coverage.ledger_available,
        ledger_confirmed=coverage.ledger_covered,
    )

    return {
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
        else ("ledger" if coverage.ledger_available else "liability"),
        "ledger_available": coverage.ledger_available,
        "checkin": _serialize_liability_checkin(
            liability_checkin=liability_checkin,
            serialize_money_fn=serialize_money_fn,
        ),
    }


def _serialize_liability_checkin(*, liability_checkin, serialize_money_fn) -> dict | None:
    if liability_checkin is None:
        return None
    return {
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
