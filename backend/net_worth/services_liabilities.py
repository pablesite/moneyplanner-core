from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import cast

from django.db import transaction
from django.db.models import Q
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
        if not account.is_active:
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
    expected_end_date,
    payment_frequency: str | None = None,
    term_months=None,
    cancellation_forecast_enabled: bool | None = None,
    cancellation_date=None,
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

    if start_date and expected_end_date and expected_end_date < start_date:
        raise DRFValidationError({"expected_end_date": "Debe ser igual o posterior a start_date."})

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
    elif cancellation_date is not None:
        raise DRFValidationError(
            {"cancellation_date": "Solo se permite si cancellation_forecast_enabled=true."}
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
    *, start_date: date, payment_frequency: str | None = None
) -> date:
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
    *, liability: Liability, as_of_date: date | None = None
) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    if liability.tracking_mode == Liability.TrackingMode.ACCOUNTING:
        integration_state = ensure_liability_accounting_account(liability=liability)
        if integration_state == AccountingIntegrationState.NEEDS_REVIEW:
            return liability.amount

        from accounting.models import LedgerTransaction
        from accounting.services_ledger import get_account_balance, has_account_entries

        accounting_account = _get_accounting_liability_account(
            user_id=liability.user_id,
            account_id=liability.accounting_account_id,
        )
        if (
            accounting_account is not None
            and accounting_account.currency == liability.currency
            and has_account_entries(
                account=accounting_account,
                as_of_date=ref_date,
                status=cast(str, LedgerTransaction.Status.POSTED),
            )
        ):
            return get_account_balance(
                account=accounting_account,
                as_of_date=ref_date,
                status=cast(str, LedgerTransaction.Status.POSTED),
            )

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
        )
    if liability.category == Liability.Category.CREDIT_CARD:
        return Decimal(liability.amount) + get_liability_events_delta(
            liability=liability,
            as_of_date=ref_date,
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
) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    delta = Decimal("0")
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


def _build_expense_profile(
    *, category: str, subcategory: str, cashflow_role: str
) -> dict[str, str]:
    return {
        "category": category,
        "subcategory": subcategory,
        "cashflow_role": cashflow_role,
    }


def _get_unbacked_liability_expense_profile(
    *, liability: Liability, temporary_commitment_role: str
) -> dict[str, str]:
    from budget.models import AnnualExpenseEntry

    return _build_expense_profile(
        category=cast(str, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES),
        subcategory=str(liability.expense_subcategory_override or "").strip()
        or "financial_commitments",
        cashflow_role=temporary_commitment_role,
    )


def _get_furnishings_expense_profile(
    *, subcategory: str, temporary_commitment_role: str
) -> dict[str, str]:
    from budget.models import AnnualExpenseEntry

    return _build_expense_profile(
        category=cast(str, AnnualExpenseEntry.Category.TANGIBLE_ASSETS),
        subcategory=FURNISHINGS_SUBCATEGORY_TO_EXPENSE_SUBCATEGORY.get(
            subcategory, "other_tangible_assets"
        ),
        cashflow_role=temporary_commitment_role,
    )


def _get_investments_expense_profile(
    *, subcategory: str, temporary_commitment_role: str
) -> dict[str, str]:
    from budget.models import AnnualExpenseEntry

    return _build_expense_profile(
        category=cast(str, AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS),
        subcategory=INVESTMENTS_SUBCATEGORY_TO_EXPENSE_SUBCATEGORY.get(
            subcategory, "other_financial_investments"
        ),
        cashflow_role=temporary_commitment_role,
    )


def get_generated_liability_expense_profile(*, liability: Liability) -> dict[str, str]:
    from budget.models import AnnualExpenseEntry

    temporary_commitment_role = cast(str, AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT)
    if liability.category == Liability.Category.MORTGAGE:
        return _build_expense_profile(
            category=cast(str, AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS),
            subcategory="mortgage_principal",
            cashflow_role=temporary_commitment_role,
        )

    financed_asset = getattr(liability, "financed_asset", None)
    if financed_asset is None:
        return _get_unbacked_liability_expense_profile(
            liability=liability, temporary_commitment_role=temporary_commitment_role
        )

    if financed_asset.category == Asset.Category.REAL_ESTATE:
        return _build_expense_profile(
            category=cast(str, AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS),
            subcategory="property_purchase",
            cashflow_role=temporary_commitment_role,
        )

    if financed_asset.category == Asset.Category.VEHICLE:
        return _build_expense_profile(
            category=cast(str, AnnualExpenseEntry.Category.TANGIBLE_ASSETS),
            subcategory="vehicle_purchase",
            cashflow_role=temporary_commitment_role,
        )

    if financed_asset.category == Asset.Category.FURNISHINGS:
        return _get_furnishings_expense_profile(
            subcategory=financed_asset.subcategory,
            temporary_commitment_role=temporary_commitment_role,
        )

    if financed_asset.category == Asset.Category.INVESTMENTS:
        return _get_investments_expense_profile(
            subcategory=financed_asset.subcategory,
            temporary_commitment_role=temporary_commitment_role,
        )

    if financed_asset.category == Asset.Category.CASH:
        return _build_expense_profile(
            category=cast(str, AnnualExpenseEntry.Category.SAVINGS_ALLOCATION),
            subcategory="cash_reserve",
            cashflow_role=temporary_commitment_role,
        )

    return _build_expense_profile(
        category=cast(str, AnnualExpenseEntry.Category.TANGIBLE_ASSETS),
        subcategory="other_tangible_assets",
        cashflow_role=temporary_commitment_role,
    )


def _format_ownership_percent(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _get_generated_liability_owner_name(*, liability: Liability) -> str:
    from memberships.models import Ownership, OwnershipLink

    link = (
        OwnershipLink.objects.filter(
            user=liability.user,
            target_type=OwnershipLink.TargetType.LIABILITY,
            target_id=liability.id,
        )
        .select_related("ownership", "ownership__member")
        .first()
    )
    if link is None:
        return ""

    ownership = link.ownership
    if ownership.kind == Ownership.Kind.INDIVIDUAL:
        member_name = getattr(ownership.member, "name", "") or ""
        return str(member_name).strip()

    if ownership.kind == Ownership.Kind.SHARED:
        splits = ownership.splits.select_related("member").order_by("id")
        parts: list[str] = []
        for split in splits:
            member_name = getattr(split.member, "name", "") or ""
            name = str(member_name).strip()
            if not name:
                continue
            percent = _format_ownership_percent(Decimal(split.percent))
            parts.append(f"{name} {percent}%")
        if parts:
            return f"Compartido ({' / '.join(parts)})"
        return "Compartido"

    return ""


def sync_generated_budget_commitments_for_liability(*, liability: Liability) -> None:
    from budget.models import AnnualExpenseEntry

    if not liability.is_active:
        return

    full_schedule = build_liability_installment_schedule_simple(liability=liability)
    schedule = full_schedule
    cancellation_date = None
    if liability.cancellation_forecast_enabled and liability.cancellation_date is not None:
        cancellation_date = liability.cancellation_date
        schedule = [
            (due_date, amount) for due_date, amount in full_schedule if due_date < cancellation_date
        ]
    if not full_schedule:
        return

    keep_ids: set[int] = set()
    totals_by_year: dict[int, Decimal] = {}
    final_due_year = None
    final_due_month = None
    if schedule:
        final_due_year = schedule[-1][0].year
        final_due_month = schedule[-1][0].month
        for due_date, installment in schedule:
            totals_by_year.setdefault(due_date.year, Decimal("0"))
            totals_by_year[due_date.year] += installment

    expense_profile = get_generated_liability_expense_profile(liability=liability)
    owner_name = _get_generated_liability_owner_name(liability=liability)

    for year, annual_total in totals_by_year.items():
        generated_defaults = {
            "name": f"Compromiso pasivo: {liability.name}",
            "category": expense_profile["category"],
            "subcategory": expense_profile["subcategory"],
            "owner_name": owner_name,
            "expense_type": AnnualExpenseEntry.ExpenseType.RECURRENT,
            "time_profile": AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            "cashflow_role": expense_profile["cashflow_role"],
            "event_group": f"liability_{liability.id}",
            "term_end_year": final_due_year,
            "term_end_month": final_due_month,
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
            event_group=f"liability_{liability.id}",
            defaults=generated_defaults,
        )
        keep_ids.add(row.id)
        if created:
            continue

        customization_marker_fields = (
            "name",
            "category",
            "subcategory",
            "expense_type",
            "time_profile",
            "cashflow_role",
            "notes",
        )
        is_customized = any(
            getattr(row, field_name) != generated_defaults[field_name]
            for field_name in customization_marker_fields
        )

        system_owned_fields = [
            "owner_name",
            "term_end_year",
            "term_end_month",
            "currency",
            "event_group",
            "is_active",
        ]
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

    if cancellation_date is not None and cancellation_date >= liability.start_date:
        remaining_principal = estimate_liability_outstanding_amount_simple(
            liability=liability, as_of_date=cancellation_date - timedelta(days=1)
        )
        if remaining_principal is not None and remaining_principal > 0:
            principal_defaults = {
                "name": f"Cancelacion anticipada principal: {liability.name}",
                "category": expense_profile["category"],
                "subcategory": expense_profile["subcategory"],
                "owner_name": owner_name,
                "expense_type": AnnualExpenseEntry.ExpenseType.ONE_OFF,
                "time_profile": AnnualExpenseEntry.TimeProfile.ONE_OFF,
                "cashflow_role": expense_profile["cashflow_role"],
                "event_group": f"liability_{liability.id}_cancellation_principal",
                "target_month": cancellation_date.month,
                "term_end_year": None,
                "term_end_month": None,
                "amount_annual": remaining_principal.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                "currency": liability.currency,
                "notes": "Generado automaticamente: cancelacion anticipada (principal).",
                "is_active": True,
            }
            principal_row, principal_created = AnnualExpenseEntry.objects.get_or_create(
                user=liability.user,
                source_liability=liability,
                is_system_generated=True,
                fiscal_year=cancellation_date.year,
                event_group=f"liability_{liability.id}_cancellation_principal",
                defaults=principal_defaults,
            )
            keep_ids.add(principal_row.id)
            if not principal_created:
                principal_row.owner_name = principal_defaults["owner_name"]
                principal_row.target_month = principal_defaults["target_month"]
                principal_row.term_end_year = None
                principal_row.term_end_month = None
                principal_row.currency = principal_defaults["currency"]
                principal_row.is_active = True
                principal_row.amount_annual = principal_defaults["amount_annual"]
                principal_row.save(
                    update_fields=[
                        "owner_name",
                        "target_month",
                        "term_end_year",
                        "term_end_month",
                        "currency",
                        "is_active",
                        "amount_annual",
                    ]
                )

            cancellation_fee_amount = liability.cancellation_fee_amount
            if cancellation_fee_amount in (
                None,
                "",
            ) and liability.early_repayment_fee_percent not in (
                None,
                "",
            ):
                fee_percent = Decimal(liability.early_repayment_fee_percent)
                cancellation_fee_amount = (
                    remaining_principal * fee_percent / Decimal("100")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if cancellation_fee_amount not in (None, "") and Decimal(cancellation_fee_amount) > 0:
                fee_defaults = {
                    "name": f"Cancelacion anticipada comision: {liability.name}",
                    "category": cast(str, AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS),
                    "subcategory": "real_estate_fees_taxes",
                    "owner_name": owner_name,
                    "expense_type": AnnualExpenseEntry.ExpenseType.ONE_OFF,
                    "time_profile": AnnualExpenseEntry.TimeProfile.ONE_OFF,
                    "cashflow_role": cast(str, AnnualExpenseEntry.CashflowRole.TAX_FEE),
                    "event_group": f"liability_{liability.id}_cancellation_fee",
                    "target_month": cancellation_date.month,
                    "term_end_year": None,
                    "term_end_month": None,
                    "amount_annual": Decimal(cancellation_fee_amount).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    "currency": liability.currency,
                    "notes": "Generado automaticamente: cancelacion anticipada (comision).",
                    "is_active": True,
                }
                fee_row, fee_created = AnnualExpenseEntry.objects.get_or_create(
                    user=liability.user,
                    source_liability=liability,
                    is_system_generated=True,
                    fiscal_year=cancellation_date.year,
                    event_group=f"liability_{liability.id}_cancellation_fee",
                    defaults=fee_defaults,
                )
                keep_ids.add(fee_row.id)
                if not fee_created:
                    fee_row.owner_name = fee_defaults["owner_name"]
                    fee_row.target_month = fee_defaults["target_month"]
                    fee_row.term_end_year = None
                    fee_row.term_end_month = None
                    fee_row.currency = fee_defaults["currency"]
                    fee_row.is_active = True
                    fee_row.amount_annual = fee_defaults["amount_annual"]
                    fee_row.save(
                        update_fields=[
                            "owner_name",
                            "target_month",
                            "term_end_year",
                            "term_end_month",
                            "currency",
                            "is_active",
                            "amount_annual",
                        ]
                    )

    stale_qs = AnnualExpenseEntry.objects.filter(
        user=liability.user,
        source_liability=liability,
        is_system_generated=True,
    )
    if keep_ids:
        stale_qs = stale_qs.exclude(id__in=keep_ids)
    stale_qs.delete()


def delete_generated_budget_commitments_for_liability(*, liability: Liability) -> None:
    from budget.models import AnnualExpenseEntry

    event_group = f"liability_{liability.id}"
    AnnualExpenseEntry.objects.filter(
        user=liability.user,
        is_system_generated=True,
    ).filter(Q(source_liability=liability) | Q(event_group=event_group)).delete()
