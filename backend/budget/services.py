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

EXPENSE_TAXONOMY: dict[str, set[str]] = {
    "savings_allocation": {
        "emergency_fund",
        "cash_reserve",
        "short_term_savings",
        "long_term_savings",
        "other_savings_allocation",
    },
    "financial_investments": {
        "index_funds_etf",
        "pension_plan",
        "stocks_dividends",
        "crypto",
        "crowdlending_p2p",
        "roboadvisor",
        "other_financial_investments",
    },
    "real_estate_assets": {
        "property_purchase",
        "mortgage_principal",
        "property_improvements",
        "real_estate_fees_taxes",
        "other_real_estate_assets",
    },
    "tangible_assets": {
        "vehicle_purchase",
        "home_furniture_appliances",
        "technology_devices",
        "jewelry_collectibles",
        "other_tangible_assets",
    },
    "consumption_expenses": {
        "housing_home",
        "living_expenses",
        "family_childcare",
        "transport_mobility",
        "health_wellbeing",
        "education_growth",
        "leisure_lifestyle",
        "gifts_donations",
        "financial_commitments",
        "other_consumption_expenses",
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


def validate_annual_expense_taxonomy(*, category: str, subcategory: str) -> None:
    options = EXPENSE_TAXONOMY.get((category or "").strip())
    if not options:
        raise ValidationError("Categoria de gasto anual no valida.")
    if (subcategory or "").strip() not in options:
        raise ValidationError("Subcategoria de gasto anual no valida para la categoria dada.")
