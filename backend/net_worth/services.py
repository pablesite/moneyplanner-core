from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import timedelta
from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_HALF_UP
from typing import cast

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from accounts.models import UserSettings
from core.models import InflationIndex
from core.services import adjust_for_inflation, convert_currency

from .models import (
    ASSET_SUBCATEGORY_MAP,
    Asset,
    Liability,
    LiquidityMonthlyCheckin,
    NetWorthSnapshot,
)

LIABILITY_CATEGORIES_REQUIRING_TAE = {
    Liability.Category.MORTGAGE,
    Liability.Category.PERSONAL_LOAN,
    Liability.Category.CREDIT_CARD,
}

ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE = {
    Asset.Subcategory.BANK_ACCOUNT,
    Asset.Subcategory.CRYPTO_SPOT_EARN,
    Asset.Subcategory.OTHER,
}


@dataclass
class NetWorthTotals:
    total_assets: Decimal
    total_liabilities: Decimal
    liabilities_asset_backed: Decimal
    liabilities_unbacked: Decimal
    assets_by_category: dict[str, Decimal]
    assets_by_subcategory: dict[str, Decimal]
    liabilities_by_category: dict[str, Decimal]


def validate_asset_payload(
    *,
    tracking_mode: str | None,
    accounting_account_id,
    category,
    subcategory,
    annual_interest_tae,
    amortization_method,
    amortization_term_years,
    initial_purchase_value,
) -> None:
    if tracking_mode == Asset.TrackingMode.ACCOUNTING and not accounting_account_id:
        raise DRFValidationError(
            {
                "accounting_account_id": (
                    "Requerido si tracking_mode=accounting "
                    "(placeholder hasta que exista contabilidad)."
                )
            }
        )

    if category and subcategory:
        allowed = ASSET_SUBCATEGORY_MAP.get(category)
        if allowed and subcategory not in allowed:
            raise DRFValidationError({"subcategory": "Subcategoria invalida para esta categoria."})

    requires_tae = (
        category == Asset.Category.CASH and subcategory in ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE
    )
    if requires_tae and annual_interest_tae is None:
        raise DRFValidationError(
            {
                "annual_interest_tae": (
                    "Requerido para liquidez en cuenta bancaria, spot/earn cripto y otros."
                )
            }
        )

    if amortization_method and amortization_method != Asset.AmortizationMethod.NONE:
        if initial_purchase_value is None:
            raise DRFValidationError(
                {"initial_purchase_value": ("Requerido si se define amortizacion del activo.")}
            )
        if amortization_term_years is None:
            raise DRFValidationError(
                {"amortization_term_years": ("Requerido si se define amortizacion del activo.")}
            )


def validate_liability_payload(
    *,
    tracking_mode: str | None,
    accounting_account_id,
    category: str | None,
    annual_interest_tae,
    start_date,
    expected_end_date,
    payment_frequency: str | None = None,
    term_months=None,
) -> None:
    if tracking_mode == Liability.TrackingMode.ACCOUNTING and not accounting_account_id:
        raise DRFValidationError(
            {
                "accounting_account_id": (
                    "Requerido si tracking_mode=accounting "
                    "(placeholder hasta que exista contabilidad)."
                )
            }
        )

    requires_tae = category in LIABILITY_CATEGORIES_REQUIRING_TAE
    if requires_tae and annual_interest_tae is None:
        raise DRFValidationError(
            {"annual_interest_tae": "Requerido para hipoteca, prestamo personal y tarjeta."}
        )

    if start_date and expected_end_date and expected_end_date < start_date:
        raise DRFValidationError({"expected_end_date": "Debe ser igual o posterior a start_date."})

    if payment_frequency == Liability.PaymentFrequency.QUARTERLY and term_months not in (None, ""):
        try:
            term = int(term_months)
        except (TypeError, ValueError):
            term = None
        if term is not None and term > 0 and term % 3 != 0:
            raise DRFValidationError(
                {"term_months": "Para frecuencia trimestral, term_months debe ser multiplo de 3."}
            )


def infer_liability_is_asset_backed(*, financed_asset) -> bool:
    return financed_asset is not None


def estimate_liability_monthly_payment_simple(
    *,
    amount,
    annual_interest_tae,
    term_months,
    payment_frequency,
    rate_type,
    amortization_system,
) -> Decimal | None:
    if amount is None or annual_interest_tae is None or term_months is None:
        return None

    if payment_frequency not in (None, "", Liability.PaymentFrequency.MONTHLY):
        return None
    if rate_type not in (None, "", Liability.RateType.FIXED):
        return None
    if amortization_system not in (
        None,
        "",
        Liability.AmortizationSystem.FRENCH,
        Liability.AmortizationSystem.MANUAL,
    ):
        return None

    try:
        principal = Decimal(amount)
        tae_pct = Decimal(annual_interest_tae)
        n = int(term_months)
    except (InvalidOperation, TypeError, ValueError):
        return None

    if principal <= 0 or tae_pct < 0 or n <= 0:
        return None

    if tae_pct == 0:
        return (principal / Decimal(n)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    monthly_rate = (tae_pct / Decimal("100")) / Decimal("12")
    # French amortization (constant installment), simplified with fixed monthly rate.
    denominator = Decimal("1") - (Decimal("1") + monthly_rate) ** Decimal(-n)
    if denominator == 0:
        return None
    payment = principal * monthly_rate / denominator
    return payment.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _liability_period_months(*, payment_frequency: str | None) -> int | None:
    if payment_frequency in (None, "", Liability.PaymentFrequency.MONTHLY):
        return 1
    if payment_frequency == Liability.PaymentFrequency.QUARTERLY:
        return 3
    return None


def _liability_periods_per_year(*, payment_frequency: str | None) -> int | None:
    if payment_frequency in (None, "", Liability.PaymentFrequency.MONTHLY):
        return 12
    if payment_frequency == Liability.PaymentFrequency.QUARTERLY:
        return 4
    return None


def _estimate_liability_periodic_payment_simple(
    *,
    amount,
    annual_interest_tae,
    term_months,
    payment_frequency,
    rate_type,
    amortization_system,
) -> Decimal | None:
    if amount is None or annual_interest_tae is None or term_months is None:
        return None

    period_months = _liability_period_months(payment_frequency=payment_frequency)
    periods_per_year = _liability_periods_per_year(payment_frequency=payment_frequency)
    if period_months is None or periods_per_year is None:
        return None
    if rate_type not in (None, "", Liability.RateType.FIXED):
        return None
    if amortization_system not in (
        None,
        "",
        Liability.AmortizationSystem.FRENCH,
        Liability.AmortizationSystem.MANUAL,
    ):
        return None

    try:
        principal = Decimal(amount)
        tae_pct = Decimal(annual_interest_tae)
        term_months_int = int(term_months)
    except (InvalidOperation, TypeError, ValueError):
        return None

    if principal <= 0 or tae_pct < 0 or term_months_int <= 0:
        return None
    if term_months_int % period_months != 0:
        return None

    n = term_months_int // period_months
    if n <= 0:
        return None

    if tae_pct == 0:
        return (principal / Decimal(n)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    periodic_rate = (tae_pct / Decimal("100")) / Decimal(periods_per_year)
    denominator = Decimal("1") - (Decimal("1") + periodic_rate) ** Decimal(-n)
    if denominator == 0:
        return None
    payment = principal * periodic_rate / denominator
    return payment.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - timedelta(days=1)).day


def _add_months_preserve_day(value: date, months: int) -> date:
    total_month = (value.month - 1) + months
    year = value.year + total_month // 12
    month = (total_month % 12) + 1
    day = min(value.day, _last_day_of_month(year, month))
    return date(year, month, day)


def get_liability_first_payment_date(
    *, start_date: date, payment_frequency: str | None = None
) -> date:
    # v1 convention: start_date is acquisition date; first installment is due next period same day.
    period_months = _liability_period_months(payment_frequency=payment_frequency) or 1
    return _add_months_preserve_day(start_date, period_months)


def build_liability_installment_schedule_simple(
    *, liability: Liability
) -> list[tuple[date, Decimal]]:
    period_months = _liability_period_months(payment_frequency=liability.payment_frequency)
    periods_per_year = _liability_periods_per_year(payment_frequency=liability.payment_frequency)
    if (
        period_months is None
        or periods_per_year is None
        or liability.rate_type != Liability.RateType.FIXED
        or not liability.term_months
    ):
        return []

    principal = liability.principal_amount or liability.amount
    if principal is None or liability.annual_interest_tae is None or liability.start_date is None:
        return []

    periodic_payment = _estimate_liability_periodic_payment_simple(
        amount=principal,
        annual_interest_tae=liability.annual_interest_tae,
        term_months=liability.term_months,
        payment_frequency=liability.payment_frequency,
        rate_type=liability.rate_type,
        amortization_system=liability.amortization_system,
    )
    if periodic_payment is None:
        return []

    try:
        principal_dec = Decimal(principal)
        tae_pct = Decimal(liability.annual_interest_tae)
    except (InvalidOperation, TypeError):
        return []

    if principal_dec <= 0:
        return []

    schedule: list[tuple[date, Decimal]] = []
    balance = principal_dec
    periodic_rate = (tae_pct / Decimal("100")) / Decimal(periods_per_year)
    term_months_int = int(liability.term_months)
    if term_months_int % period_months != 0:
        return []
    total_installments = term_months_int // period_months
    first_due = get_liability_first_payment_date(
        start_date=liability.start_date, payment_frequency=liability.payment_frequency
    )

    for idx in range(total_installments):
        due_date = _add_months_preserve_day(first_due, idx * period_months)
        if periodic_rate == 0:
            installment = (balance if idx == total_installments - 1 else periodic_payment).quantize(
                Decimal("0.00000001"), rounding=ROUND_HALF_UP
            )
            principal_component = installment
        else:
            interest = (balance * periodic_rate).quantize(
                Decimal("0.00000001"), rounding=ROUND_HALF_UP
            )
            installment = periodic_payment
            principal_component = installment - interest
            if idx == total_installments - 1:
                installment = (balance + interest).quantize(
                    Decimal("0.00000001"), rounding=ROUND_HALF_UP
                )
                principal_component = balance

        if principal_component > balance:
            principal_component = balance
        balance = (balance - principal_component).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )
        if balance < 0:
            balance = Decimal("0")
        schedule.append(
            (due_date, installment.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))
        )

    return schedule


def estimate_liability_outstanding_amount_simple(
    *, liability: Liability, as_of_date: date | None = None
) -> Decimal | None:
    schedule = build_liability_installment_schedule_simple(liability=liability)
    if not schedule:
        return None
    ref_date = as_of_date or timezone.localdate()
    paid_installments = sum(1 for due_date, _amount in schedule if due_date <= ref_date)

    principal = liability.principal_amount or liability.amount
    if principal is None or liability.annual_interest_tae is None or not liability.term_months:
        return None
    try:
        balance = Decimal(principal)
        tae_pct = Decimal(liability.annual_interest_tae)
    except (InvalidOperation, TypeError):
        return None

    period_months = _liability_period_months(payment_frequency=liability.payment_frequency)
    periods_per_year = _liability_periods_per_year(payment_frequency=liability.payment_frequency)
    if period_months is None or periods_per_year is None:
        return None
    term_months_int = int(liability.term_months)
    if term_months_int % period_months != 0:
        return None
    total_installments = term_months_int // period_months
    paid_installments = max(0, min(paid_installments, total_installments))
    periodic_payment = _estimate_liability_periodic_payment_simple(
        amount=principal,
        annual_interest_tae=liability.annual_interest_tae,
        term_months=liability.term_months,
        payment_frequency=liability.payment_frequency,
        rate_type=liability.rate_type,
        amortization_system=liability.amortization_system,
    )
    if periodic_payment is None:
        return None

    periodic_rate = (tae_pct / Decimal("100")) / Decimal(periods_per_year)
    for idx in range(paid_installments):
        if balance <= 0:
            balance = Decimal("0")
            break
        if periodic_rate == 0:
            installment = balance if idx == total_installments - 1 else periodic_payment
            principal_component = installment
        else:
            interest = (balance * periodic_rate).quantize(
                Decimal("0.00000001"), rounding=ROUND_HALF_UP
            )
            installment = periodic_payment
            principal_component = installment - interest
            if idx == total_installments - 1:
                principal_component = balance
        if principal_component > balance:
            principal_component = balance
        balance = (balance - principal_component).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )
    if balance < 0:
        balance = Decimal("0")
    return balance.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def get_effective_liability_amount(
    *, liability: Liability, as_of_date: date | None = None
) -> Decimal:
    estimated = estimate_liability_outstanding_amount_simple(
        liability=liability, as_of_date=as_of_date
    )
    return estimated if estimated is not None else liability.amount


def get_generated_liability_expense_profile(*, liability: Liability) -> dict[str, str]:
    from budget.models import AnnualExpenseEntry

    # Debt installments generated from liabilities represent a temporary commitment
    # cash-flow, even when the financed target is an asset purchase.
    temporary_commitment_role = AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT
    financed_asset = getattr(liability, "financed_asset", None)
    if financed_asset is None:
        return {
            "category": AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            "subcategory": "financial_commitments",
            "cashflow_role": temporary_commitment_role,
        }

    if financed_asset.category == Asset.Category.REAL_ESTATE:
        return {
            "category": AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS,
            "subcategory": "property_purchase",
            "cashflow_role": temporary_commitment_role,
        }

    if financed_asset.category == Asset.Category.VEHICLE:
        return {
            "category": AnnualExpenseEntry.Category.TANGIBLE_ASSETS,
            "subcategory": "vehicle_purchase",
            "cashflow_role": temporary_commitment_role,
        }

    if financed_asset.category == Asset.Category.FURNISHINGS:
        furnishings_map = {
            Asset.Subcategory.VEHICLES: "vehicle_purchase",
            Asset.Subcategory.HOME_FURNISHINGS: "home_furniture_appliances",
            Asset.Subcategory.TECHNOLOGY: "technology_devices",
            Asset.Subcategory.JEWELRY: "jewelry_collectibles",
        }
        return {
            "category": AnnualExpenseEntry.Category.TANGIBLE_ASSETS,
            "subcategory": furnishings_map.get(financed_asset.subcategory, "other_tangible_assets"),
            "cashflow_role": temporary_commitment_role,
        }

    if financed_asset.category == Asset.Category.INVESTMENTS:
        investments_map = {
            Asset.Subcategory.FUNDS: "index_funds_etf",
            Asset.Subcategory.ETFS: "index_funds_etf",
            Asset.Subcategory.PENSION_PLANS: "pension_plan",
            Asset.Subcategory.STOCKS: "stocks_dividends",
            Asset.Subcategory.CRYPTOCURRENCIES: "crypto",
            Asset.Subcategory.CROWDLENDING: "crowdlending_p2p",
            Asset.Subcategory.ROBOADVISOR: "roboadvisor",
        }
        return {
            "category": AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
            "subcategory": investments_map.get(
                financed_asset.subcategory, "other_financial_investments"
            ),
            "cashflow_role": temporary_commitment_role,
        }

    if financed_asset.category == Asset.Category.CASH:
        return {
            "category": AnnualExpenseEntry.Category.SAVINGS_ALLOCATION,
            "subcategory": "cash_reserve",
            "cashflow_role": temporary_commitment_role,
        }

    return {
        "category": AnnualExpenseEntry.Category.TANGIBLE_ASSETS,
        "subcategory": "other_tangible_assets",
        "cashflow_role": temporary_commitment_role,
    }


def sync_generated_budget_commitments_for_liability(*, liability: Liability) -> None:
    from budget.models import AnnualExpenseEntry

    if not liability.is_active:
        return

    schedule = build_liability_installment_schedule_simple(liability=liability)
    if not schedule:
        return

    totals_by_year: dict[int, Decimal] = {}
    final_due_year = schedule[-1][0].year
    for due_date, installment in schedule:
        totals_by_year.setdefault(due_date.year, Decimal("0"))
        totals_by_year[due_date.year] += installment

    expense_profile = get_generated_liability_expense_profile(liability=liability)

    for year, annual_total in totals_by_year.items():
        generated_defaults = {
            "name": f"Compromiso pasivo: {liability.name}",
            "category": expense_profile["category"],
            "subcategory": expense_profile["subcategory"],
            "owner_name": "",
            "expense_type": AnnualExpenseEntry.ExpenseType.RECURRENT,
            "time_profile": AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            "cashflow_role": expense_profile["cashflow_role"],
            "event_group": f"liability_{liability.id}",
            "term_end_year": final_due_year,
            "amount_annual": annual_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "currency": liability.currency,
            "notes": "Generado automaticamente desde pasivo (editable).",
            "is_active": True,
        }
        row, created = AnnualExpenseEntry.objects.get_or_create(
            user=liability.user,
            source_liability=liability,
            is_system_generated=True,
            fiscal_year=year,
            defaults=generated_defaults,
        )
        if created:
            continue

        # If the generated row was customized (e.g. user changed name/notes/classification),
        # avoid overwriting the annual amount. We still refresh structural linkage fields.
        customization_marker_fields = (
            "name",
            "category",
            "subcategory",
            "owner_name",
            "expense_type",
            "time_profile",
            "cashflow_role",
            "notes",
        )
        is_customized = any(
            getattr(row, field_name) != generated_defaults[field_name]
            for field_name in customization_marker_fields
        )

        system_owned_fields = ["term_end_year", "currency", "event_group", "is_active"]
        if not is_customized:
            system_owned_fields.append("amount_annual")
        update_fields: list[str] = []
        for field_name in system_owned_fields:
            expected = generated_defaults[field_name]
            if getattr(row, field_name) != expected:
                setattr(row, field_name, expected)
                update_fields.append(field_name)
        if update_fields:
            row.save(update_fields=update_fields)

    # Remove obsolete generated rows when the debt schedule shrinks (for example, term reduction).
    AnnualExpenseEntry.objects.filter(
        user=liability.user,
        source_liability=liability,
        is_system_generated=True,
    ).exclude(fiscal_year__in=list(totals_by_year.keys())).delete()


def create_asset_for_user(*, user, validated_data: dict) -> Asset:
    return Asset.objects.create(user=user, **validated_data)


def create_liability_for_user(*, user, validated_data: dict) -> Liability:
    return Liability.objects.create(user=user, **validated_data)


def create_snapshot_for_user(*, user, validated_data: dict) -> NetWorthSnapshot:
    return NetWorthSnapshot.objects.create(user=user, **validated_data)


def validate_snapshot_payload(*, total_assets, total_liabilities, net_worth):
    if total_assets is None or total_liabilities is None:
        return net_worth

    computed = (total_assets or Decimal("0")) - (total_liabilities or Decimal("0"))
    if net_worth is None:
        return computed
    if net_worth != computed:
        raise ValidationError({"net_worth": "net_worth debe ser total_assets - total_liabilities"})
    return net_worth


def get_financed_asset_queryset_for_user(*, user):
    return Asset.objects.filter(user=user, is_active=True)


def get_liquidity_asset_queryset_for_user(*, user):
    return Asset.objects.filter(user=user, is_active=True, category=Asset.Category.CASH)


def get_amount_base_value(
    *, amount, currency: str, base_currency: str | None, as_of_date: date | None = None
):
    if not base_currency:
        return None
    try:
        ref_date = as_of_date or timezone.localdate()
        return str(convert_currency(amount, currency, base_currency, date=ref_date))
    except Exception:
        return None


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


def _serialize_money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_liquidity_monthly_summary(*, user, fiscal_year: int, month: int) -> dict[str, object]:
    if month < 1 or month > 12:
        raise ValidationError({"month": "month debe estar entre 1 y 12."})

    base_currency = get_base_currency_for_user(user=user)
    summary_date = date(fiscal_year, month, _last_day_of_month(fiscal_year, month))
    liquid_assets = list(
        get_liquidity_asset_queryset_for_user(user=user).order_by("subcategory", "name", "id")
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
        effective_native = executed_native if executed_native is not None else planned_native

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
                "planned_closing_balance": _serialize_money(planned_native),
                "executed_closing_balance": _serialize_money(executed_native),
                "effective_closing_balance": _serialize_money(effective_native),
                "deviation": _serialize_money(
                    (executed_native - planned_native)
                    if executed_native is not None
                    else Decimal("0")
                ),
                "planned_closing_balance_base": _serialize_money(planned_base),
                "executed_closing_balance_base": _serialize_money(executed_base),
                "effective_closing_balance_base": _serialize_money(effective_base),
                "deviation_base": _serialize_money(deviation_base),
                "checkin": (
                    {
                        "id": checkin.id,
                        "status": checkin.status,
                        "closing_balance_real": _serialize_money(checkin.closing_balance_real),
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
        "planned_total": _serialize_money(planned_total_base),
        "executed_total": _serialize_money(executed_total_base),
        "deviation_total": _serialize_money(deviation_total_base),
        "completion_ratio": completion_ratio,
        "checkins_confirmed": checked_count,
        "checkins_expected": len(rows),
        "rows": rows,
    }


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
