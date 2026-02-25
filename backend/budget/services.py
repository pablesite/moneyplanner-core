from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .models import (
    AnnualExpenseEntry,
    AnnualExpenseMonthlyCheckin,
    AnnualIncomeEntry,
    AnnualIncomeMonthlyCheckin,
)

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


TWOPLACES = Decimal("0.01")


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def planned_expense_monthly_distribution(entry: AnnualExpenseEntry) -> dict[int, Decimal]:
    amount = Decimal(entry.amount_annual or 0)
    if amount <= 0:
        return {}
    if entry.time_profile == AnnualExpenseEntry.TimeProfile.ONE_OFF:
        if not entry.target_month:
            return {}
        return {int(entry.target_month): _round_money(amount)}

    base = _round_money(amount / Decimal("12"))
    distribution = {month: base for month in range(1, 13)}
    total = sum(distribution.values(), Decimal("0.00"))
    delta = _round_money(amount - total)
    if delta:
        distribution[12] = _round_money(distribution[12] + delta)
    return distribution


def build_expense_monthly_plan_vs_executed_summary(*, user, fiscal_year: int) -> dict:
    entries = list(
        AnnualExpenseEntry.objects.filter(user=user, fiscal_year=fiscal_year, is_active=True)
        .only(
            "id",
            "fiscal_year",
            "time_profile",
            "target_month",
            "amount_annual",
        )
        .order_by("id")
    )
    checkins = list(
        AnnualExpenseMonthlyCheckin.objects.filter(
            user=user,
            fiscal_year=fiscal_year,
        ).only("annual_expense_entry_id", "month", "status", "executed_amount")
    )
    checkins_by_key = {
        (item.annual_expense_entry_id, item.month): item
        for item in checkins
        if 1 <= item.month <= 12
    }

    planned_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    executed_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    pending_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    confirmed_entries_by_month = {month: 0 for month in range(1, 13)}
    expected_entries_by_month = {month: 0 for month in range(1, 13)}

    for entry in entries:
        distribution = planned_expense_monthly_distribution(entry)
        for month, planned_amount in distribution.items():
            planned_by_month[month] += planned_amount
            expected_entries_by_month[month] += 1
            checkin = checkins_by_key.get((entry.id, month))
            if checkin is None:
                pending_by_month[month] += planned_amount
                continue
            confirmed_entries_by_month[month] += 1
            if checkin.status == AnnualExpenseMonthlyCheckin.Status.SKIPPED:
                continue
            executed_amount = Decimal(checkin.executed_amount or 0)
            executed_by_month[month] += _round_money(executed_amount)

    planned_total = sum(planned_by_month.values(), Decimal("0.00"))
    executed_total = sum(executed_by_month.values(), Decimal("0.00"))
    pending_total = sum(pending_by_month.values(), Decimal("0.00"))

    months_payload = []
    months_with_checkins = 0
    expected_slots_total = 0
    confirmed_slots_total = 0
    for month in range(1, 13):
        expected = expected_entries_by_month[month]
        confirmed = confirmed_entries_by_month[month]
        expected_slots_total += expected
        confirmed_slots_total += confirmed
        if confirmed > 0:
            months_with_checkins += 1
        completion_ratio = 1.0 if expected == 0 else (confirmed / expected)
        months_payload.append(
            {
                "month": month,
                "planned": str(_round_money(planned_by_month[month])),
                "executed": str(_round_money(executed_by_month[month])),
                "pending": str(_round_money(pending_by_month[month])),
                "completion_ratio": round(completion_ratio, 4),
                "checkins_confirmed": confirmed,
                "checkins_expected": expected,
            }
        )

    total_completion_ratio = (
        1.0 if expected_slots_total == 0 else round(confirmed_slots_total / expected_slots_total, 4)
    )

    return {
        "fiscal_year": fiscal_year,
        "planned_total": str(_round_money(planned_total)),
        "executed_total": str(_round_money(executed_total)),
        "pending_total": str(_round_money(pending_total)),
        "variance_total": str(_round_money(executed_total - planned_total)),
        "months": months_payload,
        "completion_ratio": total_completion_ratio,
        "months_with_checkins": months_with_checkins,
        "has_executed_data": any(item["checkins_confirmed"] > 0 for item in months_payload),
    }


def planned_income_monthly_distribution(entry: AnnualIncomeEntry) -> dict[int, Decimal]:
    amount = Decimal(entry.amount_annual or 0)
    if amount <= 0:
        return {}
    # v1: one-off incomes don't have target_month yet in AnnualIncomeEntry.
    if entry.time_profile == AnnualIncomeEntry.TimeProfile.ONE_OFF:
        return {}

    base = _round_money(amount / Decimal("12"))
    distribution = {month: base for month in range(1, 13)}
    total = sum(distribution.values(), Decimal("0.00"))
    delta = _round_money(amount - total)
    if delta:
        distribution[12] = _round_money(distribution[12] + delta)
    return distribution


def build_income_monthly_plan_vs_executed_summary(*, user, fiscal_year: int) -> dict:
    entries = list(
        AnnualIncomeEntry.objects.filter(user=user, fiscal_year=fiscal_year, is_active=True)
        .only("id", "fiscal_year", "time_profile", "amount_annual")
        .order_by("id")
    )
    checkins = list(
        AnnualIncomeMonthlyCheckin.objects.filter(user=user, fiscal_year=fiscal_year).only(
            "annual_income_entry_id", "month", "status", "executed_amount"
        )
    )
    checkins_by_key = {
        (item.annual_income_entry_id, item.month): item for item in checkins if 1 <= item.month <= 12
    }

    planned_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    executed_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    pending_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    confirmed_entries_by_month = {month: 0 for month in range(1, 13)}
    expected_entries_by_month = {month: 0 for month in range(1, 13)}

    for entry in entries:
        distribution = planned_income_monthly_distribution(entry)
        for month, planned_amount in distribution.items():
            planned_by_month[month] += planned_amount
            expected_entries_by_month[month] += 1
            checkin = checkins_by_key.get((entry.id, month))
            if checkin is None:
                pending_by_month[month] += planned_amount
                continue
            confirmed_entries_by_month[month] += 1
            if checkin.status == AnnualIncomeMonthlyCheckin.Status.SKIPPED:
                continue
            executed_amount = Decimal(checkin.executed_amount or 0)
            executed_by_month[month] += _round_money(executed_amount)

    planned_total = sum(planned_by_month.values(), Decimal("0.00"))
    executed_total = sum(executed_by_month.values(), Decimal("0.00"))
    pending_total = sum(pending_by_month.values(), Decimal("0.00"))

    months_payload = []
    months_with_checkins = 0
    expected_slots_total = 0
    confirmed_slots_total = 0
    for month in range(1, 13):
        expected = expected_entries_by_month[month]
        confirmed = confirmed_entries_by_month[month]
        expected_slots_total += expected
        confirmed_slots_total += confirmed
        if confirmed > 0:
            months_with_checkins += 1
        completion_ratio = 1.0 if expected == 0 else (confirmed / expected)
        months_payload.append(
            {
                "month": month,
                "planned": str(_round_money(planned_by_month[month])),
                "executed": str(_round_money(executed_by_month[month])),
                "pending": str(_round_money(pending_by_month[month])),
                "completion_ratio": round(completion_ratio, 4),
                "checkins_confirmed": confirmed,
                "checkins_expected": expected,
            }
        )

    total_completion_ratio = (
        1.0 if expected_slots_total == 0 else round(confirmed_slots_total / expected_slots_total, 4)
    )
    return {
        "fiscal_year": fiscal_year,
        "planned_total": str(_round_money(planned_total)),
        "executed_total": str(_round_money(executed_total)),
        "pending_total": str(_round_money(pending_total)),
        "variance_total": str(_round_money(executed_total - planned_total)),
        "months": months_payload,
        "completion_ratio": total_completion_ratio,
        "months_with_checkins": months_with_checkins,
        "has_executed_data": any(item["checkins_confirmed"] > 0 for item in months_payload),
    }
