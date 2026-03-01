from __future__ import annotations

from datetime import date

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

    if amortization_method and amortization_method != Asset.AmortizationMethod.NONE:
        if initial_purchase_value is None:
            raise DRFValidationError(
                {"initial_purchase_value": ("Requerido si se define amortizacion del activo.")}
            )
        if amortization_term_years is None:
            raise DRFValidationError(
                {"amortization_term_years": ("Requerido si se define amortizacion del activo.")}
            )


def create_asset_for_user(*, user, validated_data: dict) -> Asset:
    return Asset.objects.create(user=user, **validated_data)


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
