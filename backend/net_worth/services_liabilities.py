from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import cast

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from .models import Asset, Liability

LIABILITY_CATEGORIES_REQUIRING_TAE = {
    Liability.Category.MORTGAGE,
    Liability.Category.PERSONAL_LOAN,
    Liability.Category.CREDIT_CARD,
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


def _build_expense_profile(
    *, category: str, subcategory: str, cashflow_role: str
) -> dict[str, str]:
    return {
        "category": category,
        "subcategory": subcategory,
        "cashflow_role": cashflow_role,
    }


def _get_unbacked_liability_expense_profile(*, temporary_commitment_role: str) -> dict[str, str]:
    from budget.models import AnnualExpenseEntry

    return _build_expense_profile(
        category=cast(str, AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES),
        subcategory="financial_commitments",
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
            temporary_commitment_role=temporary_commitment_role
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

    schedule = build_liability_installment_schedule_simple(liability=liability)
    if not schedule:
        return

    totals_by_year: dict[int, Decimal] = {}
    final_due_year = schedule[-1][0].year
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

        system_owned_fields = ["owner_name", "term_end_year", "currency", "event_group", "is_active"]
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

    AnnualExpenseEntry.objects.filter(
        user=liability.user,
        source_liability=liability,
        is_system_generated=True,
    ).exclude(fiscal_year__in=list(totals_by_year.keys())).delete()


def delete_generated_budget_commitments_for_liability(*, liability: Liability) -> None:
    from budget.models import AnnualExpenseEntry

    event_group = f"liability_{liability.id}"
    AnnualExpenseEntry.objects.filter(
        user=liability.user,
        is_system_generated=True,
    ).filter(Q(source_liability=liability) | Q(event_group=event_group)).delete()
