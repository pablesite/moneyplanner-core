from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from core.services import convert_currency

from .models import ASSET_SUBCATEGORY_MAP, Asset

ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE = {
    Asset.Subcategory.BANK_ACCOUNT,
    Asset.Subcategory.SHORT_TERM_DEPOSIT,
    Asset.Subcategory.CRYPTO_SPOT_EARN,
    Asset.Subcategory.OTHER,
}


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
    valuation_model=None,
    land_value_share_percent=None,
    land_annual_appreciation_percent=None,
    building_annual_depreciation_percent=None,
    deposit_term_months=None,
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

    if amortization_method and amortization_method != Asset.AmortizationMethod.NONE:
        if initial_purchase_value is None:
            raise DRFValidationError(
                {"initial_purchase_value": ("Requerido si se define amortizacion del activo.")}
            )
        if amortization_term_years is None:
            raise DRFValidationError(
                {"amortization_term_years": ("Requerido si se define amortizacion del activo.")}
            )

    is_auto_real_estate = valuation_model == Asset.ValuationModel.REAL_ESTATE_AUTO
    if is_auto_real_estate:
        if not (
            category == Asset.Category.REAL_ESTATE and subcategory == Asset.Subcategory.PRIMARY_HOME
        ):
            raise DRFValidationError(
                {
                    "valuation_model": (
                        "La valoracion automatica solo aplica a vivienda habitual."
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


def _whole_months_elapsed(*, start: date, end: date) -> int:
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def get_effective_asset_amount(*, asset: Asset, as_of_date: date | None = None) -> Decimal:
    ref_date = as_of_date or timezone.localdate()
    if (
        asset.valuation_model != Asset.ValuationModel.REAL_ESTATE_AUTO
        or asset.category != Asset.Category.REAL_ESTATE
        or asset.subcategory != Asset.Subcategory.PRIMARY_HOME
    ):
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
    return land_amount + building_amount


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
