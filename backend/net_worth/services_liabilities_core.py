from __future__ import annotations

from bisect import bisect_right
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import cast

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from .models import Asset, Liability, LiabilityEvent, LiabilityValuation

LIABILITY_CATEGORIES_REQUIRING_TAE = {
    Liability.Category.MORTGAGE,
    Liability.Category.PERSONAL_LOAN,
    Liability.Category.CREDIT_CARD,
}

UNBACKED_LIABILITY_EXPENSE_SUBCATEGORY_OPTIONS = {
    cast(str, Liability.ExpenseSubcategoryOverride.HOUSING_HOME),
    cast(str, Liability.ExpenseSubcategoryOverride.LIVING_EXPENSES),
    cast(str, Liability.ExpenseSubcategoryOverride.FAMILY_CHILDCARE),
    cast(str, Liability.ExpenseSubcategoryOverride.TRANSPORT_MOBILITY),
    cast(str, Liability.ExpenseSubcategoryOverride.HEALTH_WELLBEING),
    cast(str, Liability.ExpenseSubcategoryOverride.EDUCATION_GROWTH),
    cast(str, Liability.ExpenseSubcategoryOverride.LEISURE_LIFESTYLE),
    cast(str, Liability.ExpenseSubcategoryOverride.GIFTS_DONATIONS),
    cast(str, Liability.ExpenseSubcategoryOverride.FINANCIAL_COMMITMENTS),
    cast(str, Liability.ExpenseSubcategoryOverride.OTHER_CONSUMPTION_EXPENSES),
}

FURNISHINGS_SUBCATEGORY_TO_EXPENSE_SUBCATEGORY: dict[str, str] = {
    cast(str, Asset.Subcategory.VEHICLES): "vehicle_purchase",
    cast(str, Asset.Subcategory.HOME_FURNISHINGS): "home_furniture_appliances",
    cast(str, Asset.Subcategory.TECHNOLOGY): "technology_devices",
    cast(str, Asset.Subcategory.JEWELRY): "jewelry_collectibles",
}

INVESTMENTS_SUBCATEGORY_TO_EXPENSE_SUBCATEGORY: dict[str, str] = {
    cast(str, Asset.Subcategory.FUNDS): "index_funds",
    cast(str, Asset.Subcategory.ETFS): "etf_indexed",
    cast(str, Asset.Subcategory.PENSION_PLANS): "pension_plan",
    cast(str, Asset.Subcategory.STOCKS): "stocks_dividends",
    cast(str, Asset.Subcategory.CRYPTOCURRENCIES): "crypto",
    cast(str, Asset.Subcategory.REAL_ESTATE_CROWD): "crowdfunding_real_estate",
    cast(str, Asset.Subcategory.CROWDLENDING): "crowdlending_p2p",
    cast(str, Asset.Subcategory.ROBOADVISOR): "roboadvisor",
}


class AccountingIntegrationState:
    LINKED = "linked"
    AUTO_CREATED = "auto_created"
    NEEDS_REVIEW = "needs_review"


def _get_accounting_liability_account(*, user_id: int, account_id: int | None):
    from accounting.models import LedgerAccount
    from accounting.services_ledger import get_user_ledger_account

    return get_user_ledger_account(
        user_id=user_id,
        account_id=account_id,
        expected_type=cast(str, LedgerAccount.AccountType.LIABILITY),
    )


@transaction.atomic
def ensure_liability_accounting_account(*, liability: Liability) -> str | None:
    if liability.tracking_mode != Liability.TrackingMode.ACCOUNTING:
        return None

    from accounting.models import LedgerAccount
    from accounting.services_ledger import normalize_currency_code

    normalized_currency = normalize_currency_code(liability.currency)
    if len(normalized_currency) != 3:
        return AccountingIntegrationState.NEEDS_REVIEW

    if liability.accounting_account_id:
        account = _get_accounting_liability_account(
            user_id=liability.user_id,
            account_id=liability.accounting_account_id,
        )
        if (
            account is None
            or account.currency != normalized_currency
            or account.liability_id not in (None, liability.id)
        ):
            return AccountingIntegrationState.NEEDS_REVIEW

        update_fields: list[str] = []
        if account.liability_id is None:
            account.liability_id = liability.id
            update_fields.append("liability")
        if not account.is_active and liability.is_active:
            account.is_active = True
            update_fields.append("is_active")
        if update_fields:
            account.save(update_fields=update_fields)
        return AccountingIntegrationState.LINKED

    existing_accounts = list(
        LedgerAccount.objects.filter(
            user_id=liability.user_id,
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency=normalized_currency,
            liability_id=liability.id,
        )
        .order_by("id")
        .only("id")
    )
    if len(existing_accounts) == 1:
        liability.accounting_account_id = existing_accounts[0].id
        liability.save(update_fields=["accounting_account_id"])
        return AccountingIntegrationState.LINKED
    if len(existing_accounts) > 1:
        return AccountingIntegrationState.NEEDS_REVIEW

    account = LedgerAccount.objects.create(
        user=liability.user,
        name=liability.name[:120] or f"Pasivo {liability.id}",
        account_type=LedgerAccount.AccountType.LIABILITY,
        currency=normalized_currency,
        origin=LedgerAccount.Origin.SYSTEM,
        liability=liability,
        is_active=True,
    )
    liability.accounting_account_id = account.id
    liability.save(update_fields=["accounting_account_id"])
    return AccountingIntegrationState.AUTO_CREATED


def _validate_accounting_liability_account_link(
    *,
    user_id: int | None,
    accounting_account_id,
    current_liability_id: int | None,
    currency: str | None,
) -> None:
    if user_id is None:
        return

    accounting_account = _get_accounting_liability_account(
        user_id=user_id,
        account_id=accounting_account_id,
    )
    if accounting_account is None:
        raise DRFValidationError(
            {
                "accounting_account_id": (
                    "La cuenta contable no existe, no pertenece al usuario o no es de tipo liability."
                )
            }
        )
    normalized_currency = str(currency or "").strip().upper()
    if normalized_currency and accounting_account.currency != normalized_currency:
        raise DRFValidationError(
            {"accounting_account_id": "La cuenta contable debe usar la misma moneda que el pasivo."}
        )
    if accounting_account.liability_id not in (None, current_liability_id):
        raise DRFValidationError(
            {"accounting_account_id": "La cuenta contable ya esta vinculada a otro pasivo."}
        )


def validate_liability_payload(
    *,
    tracking_mode: str | None,
    accounting_account_id,
    category: str | None,
    annual_interest_tae,
    start_date,
    payment_start_date=None,
    expected_end_date,
    payment_frequency: str | None = None,
    term_months=None,
    cancellation_forecast_enabled: bool | None = None,
    cancellation_date=None,
    cancellation_include_payment_month: bool | None = None,
    cancellation_fee_amount=None,
    expense_subcategory_override: str | None = None,
    financed_asset=None,
    user_id: int | None = None,
    current_liability_id: int | None = None,
    currency: str | None = None,
) -> None:
    if (
        tracking_mode == Liability.TrackingMode.ACCOUNTING
        and accounting_account_id is not None
        and user_id is not None
    ):
        _validate_accounting_liability_account_link(
            user_id=user_id,
            accounting_account_id=accounting_account_id,
            current_liability_id=current_liability_id,
            currency=currency,
        )

    requires_tae = category in LIABILITY_CATEGORIES_REQUIRING_TAE
    if requires_tae and annual_interest_tae is None:
        raise DRFValidationError(
            {"annual_interest_tae": "Requerido para hipoteca, prestamo personal y tarjeta."}
        )

    if start_date and payment_start_date and payment_start_date < start_date:
        raise DRFValidationError({"payment_start_date": "Debe ser igual o posterior a start_date."})

    schedule_anchor_date = payment_start_date or start_date
    if schedule_anchor_date and expected_end_date and expected_end_date < schedule_anchor_date:
        raise DRFValidationError(
            {"expected_end_date": "Debe ser igual o posterior a payment_start_date."}
        )

    _validate_liability_cancellation_payload(
        category=category,
        start_date=start_date,
        cancellation_forecast_enabled=cancellation_forecast_enabled,
        cancellation_date=cancellation_date,
        cancellation_include_payment_month=cancellation_include_payment_month,
    )

    if cancellation_fee_amount not in (None, ""):
        try:
            fee_amount = Decimal(cancellation_fee_amount)
        except (InvalidOperation, TypeError):
            raise DRFValidationError(
                {"cancellation_fee_amount": "Importe de comision de cancelacion invalido."}
            ) from None
        if fee_amount < 0:
            raise DRFValidationError({"cancellation_fee_amount": "Debe ser mayor o igual que 0."})

    if payment_frequency == Liability.PaymentFrequency.QUARTERLY and term_months not in (None, ""):
        try:
            term = int(term_months)
        except (TypeError, ValueError):
            term = None
        if term is not None and term > 0 and term % 3 != 0:
            raise DRFValidationError(
                {"term_months": "Para frecuencia trimestral, term_months debe ser multiplo de 3."}
            )

    if expense_subcategory_override not in (None, ""):
        if financed_asset is not None:
            raise DRFValidationError(
                {
                    "expense_subcategory_override": (
                        "Solo aplica a pasivos sin activo financiado asociado."
                    )
                }
            )
        if category == Liability.Category.MORTGAGE:
            raise DRFValidationError(
                {
                    "expense_subcategory_override": (
                        "No aplica a hipotecas, que generan amortizacion principal."
                    )
                }
            )
        if expense_subcategory_override not in UNBACKED_LIABILITY_EXPENSE_SUBCATEGORY_OPTIONS:
            raise DRFValidationError(
                {
                    "expense_subcategory_override": (
                        "Subcategoria invalida para el destino de la salida generada."
                    )
                }
            )


def _validate_liability_cancellation_payload(
    *,
    category: str | None,
    start_date,
    cancellation_forecast_enabled: bool | None,
    cancellation_date,
    cancellation_include_payment_month: bool | None,
) -> None:
    if cancellation_forecast_enabled:
        if category != Liability.Category.MORTGAGE:
            raise DRFValidationError(
                {
                    "cancellation_forecast_enabled": (
                        "La prevision de cancelacion anticipada solo aplica a hipotecas."
                    )
                }
            )
        if cancellation_date is None:
            raise DRFValidationError(
                {"cancellation_date": "Requerida si cancellation_forecast_enabled=true."}
            )
        if start_date and cancellation_date < start_date:
            raise DRFValidationError(
                {"cancellation_date": "Debe ser igual o posterior a start_date."}
            )
        return
    if cancellation_date is not None:
        raise DRFValidationError(
            {"cancellation_date": "Solo se permite si cancellation_forecast_enabled=true."}
        )
    if cancellation_include_payment_month not in (None, True):
        raise DRFValidationError(
            {
                "cancellation_include_payment_month": (
                    "Solo se permite si cancellation_forecast_enabled=true."
                )
            }
        )


def infer_liability_is_asset_backed(*, financed_asset) -> bool:
    return financed_asset is not None


def create_liability_for_user(*, user, validated_data: dict) -> Liability:
    return Liability.objects.create(user=user, **validated_data)


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
    *,
    start_date: date,
    payment_frequency: str | None = None,
    payment_start_date: date | None = None,
) -> date:
    if payment_start_date is not None:
        return payment_start_date
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
        start_date=liability.start_date,
        payment_frequency=liability.payment_frequency,
        payment_start_date=getattr(liability, "payment_start_date", None),
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
    if (
        liability.cancellation_forecast_enabled
        and liability.cancellation_date is not None
        and ref_date >= liability.cancellation_date
    ):
        return Decimal("0.00000000")
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
    *,
    liability: Liability,
    as_of_date: date | None = None,
    position_cache=None,
) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    if liability.tracking_mode == Liability.TrackingMode.ACCOUNTING:
        integration_state = ensure_liability_accounting_account(liability=liability)
        if integration_state == AccountingIntegrationState.NEEDS_REVIEW:
            return liability.amount

        from accounting.models import LedgerTransaction
        from accounting.services_ledger import (
            build_net_worth_opening_balance_note,
            compute_account_balance_from_totals,
            compute_entry_balance_totals,
            get_account_entries,
            get_account_balance,
            has_account_entries,
        )

        accounting_account = _get_accounting_liability_account(
            user_id=liability.user_id,
            account_id=liability.accounting_account_id,
        )
        if accounting_account is not None and accounting_account.currency == liability.currency:
            posted_status = cast(str, LedgerTransaction.Status.POSTED)
            opening_note = build_net_worth_opening_balance_note(
                position_kind="liability",
                position_id=liability.id,
            )
            if position_cache is not None:
                dates = position_cache.accounting_prefix_dates.get(accounting_account.id, [])
                if dates:
                    idx = bisect_right(dates, ref_date) - 1
                    if idx >= 0:
                        debit_total = position_cache.accounting_prefix_debits[
                            accounting_account.id
                        ][idx]
                        credit_total = position_cache.accounting_prefix_credits[
                            accounting_account.id
                        ][idx]
                        raw_full = credit_total - debit_total

                        opening_date = position_cache.liability_opening_booking_dates.get(
                            liability.id
                        )
                        if opening_date is not None and ref_date >= opening_date:
                            before_opening_idx = (
                                bisect_right(dates, opening_date - timedelta(days=1)) - 1
                            )
                            if before_opening_idx >= 0:
                                before_debit_total = position_cache.accounting_prefix_debits[
                                    accounting_account.id
                                ][before_opening_idx]
                                before_credit_total = position_cache.accounting_prefix_credits[
                                    accounting_account.id
                                ][before_opening_idx]
                                raw_full -= before_credit_total - before_debit_total
                        return max(Decimal("0"), raw_full)

            if has_account_entries(
                account=accounting_account,
                as_of_date=ref_date,
                status=posted_status,
            ):
                opening_tx = (
                    LedgerTransaction.objects.filter(
                        user_id=liability.user_id,
                        status=posted_status,
                        notes=opening_note,
                        entries__account_id=accounting_account.id,
                    )
                    .distinct()
                    .order_by("-booking_date", "-id")
                    .first()
                )
                if opening_tx is not None and ref_date >= opening_tx.booking_date:
                    anchored_entries = get_account_entries(
                        account=accounting_account,
                        as_of_date=ref_date,
                        status=posted_status,
                    ).filter(transaction__booking_date__gte=opening_tx.booking_date)
                    if anchored_entries.exists():
                        totals = compute_entry_balance_totals(
                            anchored_entries,
                            account_id=accounting_account.id,
                        )
                        raw = compute_account_balance_from_totals(
                            account_type=accounting_account.account_type,
                            totals=totals,
                        )
                        return max(Decimal("0"), raw)

                raw = get_account_balance(
                    account=accounting_account,
                    as_of_date=ref_date,
                    status=cast(str, LedgerTransaction.Status.POSTED),
                )
                return max(Decimal("0"), raw)

    if position_cache is not None:
        cached_vals = position_cache.liability_valuations.get(liability.id, [])
        valuation = next(
            (v for v in cached_vals if v.valuation_date <= ref_date),
            None,
        )
    else:
        valuation = (
            LiabilityValuation.objects.filter(liability=liability, valuation_date__lte=ref_date)
            .order_by("-valuation_date", "-updated_at", "-id")
            .first()
        )
    if valuation is not None:
        return Decimal(valuation.value) + get_liability_events_delta(
            liability=liability,
            from_date=valuation.valuation_date,
            as_of_date=ref_date,
            position_cache=position_cache,
        )
    if liability.category == Liability.Category.CREDIT_CARD:
        return Decimal(liability.amount) + get_liability_events_delta(
            liability=liability,
            as_of_date=ref_date,
            position_cache=position_cache,
        )
    estimated = estimate_liability_outstanding_amount_simple(
        liability=liability, as_of_date=ref_date
    )
    return estimated if estimated is not None else liability.amount


def validate_liability_event_payload(
    *,
    liability: Liability | None,
    event_date: date | None = None,
    event_type: str | None,
    amount,
) -> None:
    if liability is None:
        raise DRFValidationError({"liability_id": "Requerido."})
    if event_type not in {
        LiabilityEvent.EventType.CHARGE,
        LiabilityEvent.EventType.PAYMENT,
        LiabilityEvent.EventType.FEE,
        LiabilityEvent.EventType.INTEREST,
        LiabilityEvent.EventType.ADJUSTMENT,
    }:
        raise DRFValidationError({"event_type": "Tipo de movimiento invalido."})
    if amount is None or Decimal(str(amount)) <= 0:
        raise DRFValidationError({"amount": "Debe ser mayor que 0."})
    if event_date is not None and event_date < liability.start_date:
        raise DRFValidationError(
            {"event_date": "Debe ser igual o posterior a start_date del pasivo."}
        )


def get_liability_events_delta(
    *,
    liability: Liability,
    from_date: date | None = None,
    as_of_date: date | None = None,
    position_cache=None,
) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    delta = Decimal("0")
    if position_cache is not None:
        all_events = position_cache.liability_events.get(liability.id, [])
        events = [
            e
            for e in all_events
            if e.event_date <= ref_date and (from_date is None or e.event_date > from_date)
        ]
    else:
        events = LiabilityEvent.objects.filter(liability=liability, event_date__lte=ref_date)
        if from_date is not None:
            events = events.filter(event_date__gt=from_date)
    for event in events:
        amount = Decimal(event.amount)
        if event.event_type in (
            LiabilityEvent.EventType.CHARGE,
            LiabilityEvent.EventType.FEE,
            LiabilityEvent.EventType.INTEREST,
            LiabilityEvent.EventType.ADJUSTMENT,
        ):
            delta += amount
        else:
            delta -= amount
    return delta
