from django.core.exceptions import ValidationError

INCOME_TAXONOMY: dict[str, set[str]] = {
    "salary": {
        "employee_salary",
        "bonus_commission",
        "overtime",
        "severance",
        "other_salary",
    },
    "business": {
        "self_employed_services",
        "business_profit",
        "professional_fees",
        "royalties",
        "other_business",
    },
    "passive_income": {
        "real_estate_rent",
        "dividends",
        "interest_income",
        "staking_yield",
        "p2p_lending",
        "other_passive",
    },
    "capital_gains": {
        "sale_financial_assets",
        "sale_real_estate",
        "sale_business_asset",
        "sale_personal_asset",
        "fx_gain",
        "other_capital_gains",
    },
    "transfers_support": {
        "family_support",
        "gifts_received",
        "inheritance",
        "alimony_received",
        "insurance_payout",
        "other_transfers_support",
    },
    "public_benefits": {
        "unemployment_benefit",
        "retirement_pension",
        "disability_benefit",
        "scholarship",
        "subsidy_grant",
        "other_public_benefits",
    },
    "other_income": {
        "tax_refund",
        "one_off_adjustment",
        "misc",
        "other",
    },
}


def normalize_currency_code(value: str | None) -> str:
    return (value or "").upper().strip()


def validate_annual_income_taxonomy(*, category: str, subcategory: str) -> None:
    options = INCOME_TAXONOMY.get((category or "").strip())
    if not options:
        raise ValidationError("Categoria de ingreso anual no valida.")
    if (subcategory or "").strip() not in options:
        raise ValidationError("Subcategoria de ingreso anual no valida para la categoria dada.")
