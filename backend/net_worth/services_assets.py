from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from decimal import ROUND_HALF_UP

from django.db.models import Q

from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from core.models import InflationIndex
from core.services import convert_currency

from .models import ASSET_SUBCATEGORY_MAP, Asset, AssetImprovement

ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE = {
    Asset.Subcategory.BANK_ACCOUNT,
    Asset.Subcategory.SHORT_TERM_DEPOSIT,
    Asset.Subcategory.CRYPTO_SPOT_EARN,
    Asset.Subcategory.OTHER,
}

FURNISHINGS_DEGRESSIVE_PROFILES: dict[str, tuple[tuple[Decimal, ...], Decimal, Decimal, int]] = {
    Asset.Subcategory.VEHICLES: (
        (
            Decimal("0.18"),
            Decimal("0.15"),
            Decimal("0.12"),
            Decimal("0.10"),
        ),
        Decimal("0.08"),
        Decimal("0.15"),
        20,
    ),
    Asset.Subcategory.SPORTS_EQUIPMENT: (
        (
            Decimal("0.12"),
            Decimal("0.10"),
            Decimal("0.08"),
        ),
        Decimal("0.06"),
        Decimal("0.20"),
        15,
    ),
}
RESIDENTIAL_REAL_ESTATE_SUBCATEGORIES = {
    Asset.Subcategory.PRIMARY_HOME,
    Asset.Subcategory.SECOND_HOME,
    Asset.Subcategory.RENTAL,
}
SYSTEM_GENERATED_ASSET_EXPENSE_EVENT_PREFIX = "asset_"


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
    amount=None,
    start_date: date | None = None,
    valuation_model=None,
    land_value_share_percent=None,
    land_annual_appreciation_percent=None,
    building_annual_depreciation_percent=None,
    deposit_term_months=None,
    investment_contribution_mode: str | None = None,
    expected_end_date: date | None = None,
    monthly_contribution_amount=None,
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
                    "Requerido para liquidez en cuenta bancaria, depositos a corto plazo, "
                    "spot/earn cripto y otros."
                )
            }
        )

    if (
        category == Asset.Category.CASH
        and subcategory == Asset.Subcategory.SHORT_TERM_DEPOSIT
        and deposit_term_months is None
    ):
        raise DRFValidationError(
            {"deposit_term_months": ("Requerido para depositos a corto plazo (1-12 meses).")}
        )

    if deposit_term_months is not None and (
        not isinstance(deposit_term_months, int)
        or deposit_term_months < 1
        or deposit_term_months > 12
    ):
        raise DRFValidationError(
            {"deposit_term_months": ("La duracion del deposito debe estar entre 1 y 12 meses.")}
        )

    purchase_value = initial_purchase_value if initial_purchase_value is not None else amount

    is_periodic_investment = (
        category == Asset.Category.INVESTMENTS
        and investment_contribution_mode
        == Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION
    )
    if is_periodic_investment:
        if expected_end_date is None:
            raise DRFValidationError(
                {"expected_end_date": ("Requerido para aportacion periodica en inversiones.")}
            )
        if start_date and expected_end_date < start_date:
            raise DRFValidationError(
                {"expected_end_date": ("Debe ser igual o posterior a start_date.")}
            )
        if monthly_contribution_amount is None or Decimal(str(monthly_contribution_amount)) <= 0:
            raise DRFValidationError(
                {
                    "monthly_contribution_amount": (
                        "La cuota mensual debe ser mayor que 0 en aportacion periodica."
                    )
                }
            )
        if purchase_value is None:
            raise DRFValidationError({"amount": ("Requerido para aportacion periodica en inversiones.")})

    if amortization_method == Asset.AmortizationMethod.STRAIGHT_LINE:
        if purchase_value is None:
            raise DRFValidationError(
                {"initial_purchase_value": ("Requerido si se define amortizacion del activo.")}
            )
        default_term_years = get_default_amortization_term_years(
            category=category,
            subcategory=subcategory,
            amortization_method=amortization_method,
        )
        if amortization_term_years is None and default_term_years is None:
            raise DRFValidationError(
                {"amortization_term_years": ("Requerido si se define amortizacion del activo.")}
            )

    is_auto_real_estate = valuation_model == Asset.ValuationModel.REAL_ESTATE_AUTO
    if is_auto_real_estate:
        if not (
            category == Asset.Category.REAL_ESTATE
            and subcategory in RESIDENTIAL_REAL_ESTATE_SUBCATEGORIES
        ):
            raise DRFValidationError(
                {
                    "valuation_model": (
                        "La valoracion automatica solo aplica a inmuebles residenciales."
                    )
                }
            )
        if initial_purchase_value is None:
            raise DRFValidationError(
                {"initial_purchase_value": ("Requerido para valoracion automatica de vivienda.")}
            )
        if land_value_share_percent is None:
            raise DRFValidationError(
                {"land_value_share_percent": ("Requerido para valoracion automatica de vivienda.")}
            )
        if land_annual_appreciation_percent is None:
            raise DRFValidationError(
                {
                    "land_annual_appreciation_percent": (
                        "Requerido para valoracion automatica de vivienda."
                    )
                }
            )
        if building_annual_depreciation_percent is None:
            raise DRFValidationError(
                {
                    "building_annual_depreciation_percent": (
                        "Requerido para valoracion automatica de vivienda."
                    )
                }
            )


def create_asset_for_user(*, user, validated_data: dict) -> Asset:
    return Asset.objects.create(user=user, **validated_data)


def validate_asset_improvement_payload(
    *,
    amortization_method: str | None,
    amortization_term_years,
    capitalize_interest: bool,
    annual_interest_tae,
    manual_current_value,
) -> None:
    if amortization_method == AssetImprovement.AmortizationMethod.STRAIGHT_LINE:
        if amortization_term_years is None:
            raise DRFValidationError(
                {"amortization_term_years": "Requerido si la reforma amortiza en lineal."}
            )
    else:
        if amortization_term_years is not None:
            raise DRFValidationError(
                {
                    "amortization_term_years": (
                        "Solo aplica cuando amortization_method=straight_line."
                    )
                }
            )

    if amortization_method == AssetImprovement.AmortizationMethod.MANUAL:
        if manual_current_value is None:
            raise DRFValidationError(
                {"manual_current_value": "Requerido si amortization_method=manual."}
            )
    elif manual_current_value is not None:
        raise DRFValidationError(
            {"manual_current_value": "Solo aplica cuando amortization_method=manual."}
        )

    if capitalize_interest and annual_interest_tae is None:
        raise DRFValidationError({"annual_interest_tae": "Requerido si capitalize_interest=true."})


def _whole_months_elapsed(*, start: date, end: date) -> int:
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _get_inflation_index_or_none(*, region: str, period_month: date) -> Decimal | None:
    row = (
        InflationIndex.objects.filter(region=region, period__lte=period_month)
        .order_by("-period")
        .first()
    )
    if row:
        return Decimal(row.index)
    first_row = InflationIndex.objects.filter(region=region).order_by("period").first()
    if first_row:
        return Decimal(first_row.index)
    return None


def _get_inflation_growth_factor_or_one(*, start: date, end: date) -> Decimal:
    if end <= start:
        return Decimal("1")
    start_index = _get_inflation_index_or_none(
        region=InflationIndex.Region.ES,
        period_month=_month_start(start),
    )
    end_index = _get_inflation_index_or_none(
        region=InflationIndex.Region.ES,
        period_month=_month_start(end),
    )
    if not start_index or not end_index or start_index == 0:
        return Decimal("1")
    return end_index / start_index


def get_default_amortization_term_years(
    *,
    category: str | None,
    subcategory: str | None,
    amortization_method: str | None,
) -> int | None:
    if (
        category != Asset.Category.FURNISHINGS
        or amortization_method != Asset.AmortizationMethod.STRAIGHT_LINE
    ):
        return None
    profile = FURNISHINGS_DEGRESSIVE_PROFILES.get(str(subcategory or "").strip())
    if not profile:
        return None
    return profile[3]


def _get_degressive_remaining_ratio(
    *,
    elapsed_months: int,
    annual_rates: tuple[Decimal, ...],
    tail_annual_rate: Decimal,
) -> Decimal:
    if elapsed_months <= 0:
        return Decimal("1")
    remaining = Decimal("1")
    months_left = elapsed_months
    year_index = 0
    while months_left > 0:
        chunk_months = min(12, months_left)
        annual_rate = (
            annual_rates[year_index] if year_index < len(annual_rates) else tail_annual_rate
        )
        chunk_factor = Decimal("1") - (annual_rate * (Decimal(str(chunk_months)) / Decimal("12")))
        if chunk_factor < 0:
            chunk_factor = Decimal("0")
        remaining *= chunk_factor
        months_left -= chunk_months
        year_index += 1
    if remaining < 0:
        return Decimal("0")
    return remaining


def get_effective_asset_amount(*, asset: Asset, as_of_date: date | None = None) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    if (
        asset.category == Asset.Category.INVESTMENTS
        and asset.investment_contribution_mode == Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION
        and asset.monthly_contribution_amount is not None
        and asset.monthly_contribution_amount > 0
    ):
        accrued_contributions = sum(
            installment
            for due_date, installment in _build_investment_contribution_schedule(asset=asset)
            if due_date <= ref_date
        )
        return Decimal(asset.amount) + Decimal(accrued_contributions)

    if (
        asset.valuation_model != Asset.ValuationModel.REAL_ESTATE_AUTO
        or asset.category != Asset.Category.REAL_ESTATE
        or asset.subcategory not in RESIDENTIAL_REAL_ESTATE_SUBCATEGORIES
    ):
        if asset.amortization_method == Asset.AmortizationMethod.STRAIGHT_LINE:
            term_years = asset.amortization_term_years or 0
            if term_years <= 0:
                default_term_years = get_default_amortization_term_years(
                    category=asset.category,
                    subcategory=asset.subcategory,
                    amortization_method=asset.amortization_method,
                )
                term_years = default_term_years or 0
            if term_years <= 0:
                return asset.amount
            purchase_value = (
                asset.amount
                if asset.category == Asset.Category.FURNISHINGS
                else asset.initial_purchase_value or asset.amount
            )
            months = _whole_months_elapsed(start=asset.start_date, end=ref_date)
            life_months = term_years * 12
            profile = FURNISHINGS_DEGRESSIVE_PROFILES.get(asset.subcategory)

            if profile is None:
                remaining_ratio = Decimal("1") - (Decimal(str(months)) / Decimal(str(life_months)))
                if remaining_ratio < 0:
                    remaining_ratio = Decimal("0")
                if remaining_ratio == 0:
                    return Decimal("0")
            else:
                months_for_depreciation = min(months, life_months)
                annual_rates, tail_annual_rate, residual_ratio, _default_term_years = profile
                remaining_ratio = _get_degressive_remaining_ratio(
                    elapsed_months=months_for_depreciation,
                    annual_rates=annual_rates,
                    tail_annual_rate=tail_annual_rate,
                )
                if remaining_ratio < residual_ratio:
                    remaining_ratio = residual_ratio

            effective_value = purchase_value * remaining_ratio
            if asset.category == Asset.Category.FURNISHINGS and asset.currency == "EUR":
                inflation_growth = _get_inflation_growth_factor_or_one(
                    start=asset.start_date,
                    end=ref_date,
                )
                effective_value *= inflation_growth
            return effective_value
        return asset.amount

    purchase_value = asset.initial_purchase_value or asset.amount
    land_share = asset.land_value_share_percent
    land_appreciation = asset.land_annual_appreciation_percent
    building_depreciation = asset.building_annual_depreciation_percent
    if (
        purchase_value is None
        or land_share is None
        or land_appreciation is None
        or building_depreciation is None
    ):
        return asset.amount

    months = _whole_months_elapsed(start=asset.start_date, end=ref_date)
    land_initial = purchase_value * (land_share / Decimal("100"))
    building_initial = purchase_value - land_initial

    land_monthly_rate = land_appreciation / Decimal("1200")
    building_monthly_depreciation = building_depreciation / Decimal("1200")

    land_growth_factor = Decimal("1") + land_monthly_rate
    building_decay_factor = Decimal("1") - building_monthly_depreciation
    if building_decay_factor < 0:
        building_decay_factor = Decimal("0")

    land_amount = land_initial * (land_growth_factor**months)
    building_amount = building_initial * (building_decay_factor**months)
    if building_amount < 0:
        building_amount = Decimal("0")

    improvements_total = Decimal("0")
    for improvement in asset.improvements.all():
        improvements_total += get_effective_asset_improvement_amount(
            improvement=improvement,
            as_of_date=ref_date,
        )
    return land_amount + building_amount + improvements_total


def get_effective_asset_improvement_amount(
    *, improvement: AssetImprovement, as_of_date: date | None = None
) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    if ref_date < improvement.reform_date:
        return Decimal("0")

    months = _whole_months_elapsed(start=improvement.reform_date, end=ref_date)
    amount = improvement.amount

    if improvement.capitalize_interest and improvement.annual_interest_tae is not None:
        monthly_rate = improvement.annual_interest_tae / Decimal("1200")
        amount = amount * ((Decimal("1") + monthly_rate) ** months)

    if improvement.amortization_method == AssetImprovement.AmortizationMethod.STRAIGHT_LINE:
        term_years = improvement.amortization_term_years or 0
        if term_years <= 0:
            return amount
        life_months = term_years * 12
        remaining_ratio = Decimal("1") - (Decimal(str(months)) / Decimal(str(life_months)))
        if remaining_ratio < 0:
            remaining_ratio = Decimal("0")
        return amount * remaining_ratio

    if improvement.amortization_method == AssetImprovement.AmortizationMethod.MANUAL:
        return improvement.manual_current_value or amount

    return amount


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


def _format_ownership_percent(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _get_generated_asset_owner_name(*, asset: Asset) -> str:
    from memberships.models import Ownership, OwnershipLink

    link = (
        OwnershipLink.objects.filter(
            user=asset.user,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id=asset.id,
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


def _build_investment_contribution_schedule(*, asset: Asset) -> list[tuple[date, Decimal]]:
    if (
        asset.category != Asset.Category.INVESTMENTS
        or asset.investment_contribution_mode != Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION
        or asset.expected_end_date is None
        or asset.monthly_contribution_amount is None
        or asset.monthly_contribution_amount <= 0
        or asset.expected_end_date < asset.start_date
    ):
        return []

    schedule: list[tuple[date, Decimal]] = []
    due_date = asset.start_date
    installment = Decimal(asset.monthly_contribution_amount)
    while due_date <= asset.expected_end_date:
        schedule.append((due_date, installment))
        due_date = _add_months_preserve_day(due_date, 1)
    return schedule


def sync_generated_budget_commitments_for_asset(*, asset: Asset) -> None:
    from budget.models import AnnualExpenseEntry

    schedule = _build_investment_contribution_schedule(asset=asset) if asset.is_active else []
    event_group = f"{SYSTEM_GENERATED_ASSET_EXPENSE_EVENT_PREFIX}{asset.id}"

    if not schedule:
        AnnualExpenseEntry.objects.filter(
            user=asset.user,
            is_system_generated=True,
        ).filter(Q(source_asset=asset) | Q(event_group=event_group)).delete()
        return

    totals_by_year: dict[int, Decimal] = {}
    for due_date, installment in schedule:
        totals_by_year.setdefault(due_date.year, Decimal("0"))
        totals_by_year[due_date.year] += installment

    owner_name = _get_generated_asset_owner_name(asset=asset)
    final_due_year = schedule[-1][0].year
    for year, annual_total in totals_by_year.items():
        generated_defaults = {
            "name": f"Aportacion inversion: {asset.name}",
            "category": AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS,
            "subcategory": "property_purchase",
            "owner_name": owner_name,
            "expense_type": AnnualExpenseEntry.ExpenseType.RECURRENT,
            "time_profile": AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            "cashflow_role": AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            "event_group": event_group,
            "term_end_year": final_due_year,
            "amount_annual": annual_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "currency": asset.currency,
            "notes": "Generado automaticamente desde activo de inversion periodica (editable).",
            "is_active": True,
        }
        row, created = AnnualExpenseEntry.objects.get_or_create(
            user=asset.user,
            source_asset=asset,
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
        user=asset.user,
        source_asset=asset,
        is_system_generated=True,
    ).exclude(fiscal_year__in=list(totals_by_year.keys())).delete()


def delete_generated_budget_commitments_for_asset(*, asset: Asset) -> None:
    from budget.models import AnnualExpenseEntry

    event_group = f"{SYSTEM_GENERATED_ASSET_EXPENSE_EVENT_PREFIX}{asset.id}"
    AnnualExpenseEntry.objects.filter(
        user=asset.user,
        is_system_generated=True,
    ).filter(Q(source_asset=asset) | Q(event_group=event_group)).delete()
