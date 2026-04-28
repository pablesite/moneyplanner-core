from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import cast

from django.core.exceptions import ValidationError

from accounting.models import LedgerEntry, LedgerTransaction

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
        "purchase_refunds",
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
        "index_funds",
        "etf_indexed",
        "index_funds_etf",
        "crowdfunding_real_estate",
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
        "sports_equipment",
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
        "personal_loan_repayment",
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


def _resolve_ledger_budget_classification(
    row: LedgerEntry,
    *,
    mortgage_payment_transaction_ids: set[int] | None = None,
) -> tuple[str, str, str, bool]:
    if (
        mortgage_payment_transaction_ids
        and row.transaction_id in mortgage_payment_transaction_ids
        and row.flow_family == LedgerEntry.FlowFamily.EXPENSE
    ):
        return (
            cast(str, LedgerEntry.FlowFamily.EXPENSE),
            "real_estate_assets",
            "mortgage_principal",
            True,
        )
    if row.flow_family and row.category_key and row.subcategory_key:
        return row.flow_family, row.category_key, row.subcategory_key, True
    if row.annual_income_entry_id is not None and row.annual_income_entry is not None:
        return (
            cast(str, LedgerEntry.FlowFamily.INCOME),
            row.annual_income_entry.category,
            row.annual_income_entry.subcategory,
            False,
        )
    if row.annual_expense_entry_id is not None and row.annual_expense_entry is not None:
        return (
            cast(str, LedgerEntry.FlowFamily.EXPENSE),
            row.annual_expense_entry.category,
            row.annual_expense_entry.subcategory,
            False,
        )
    return "", "", "", False


def _build_ledger_monthly_execution_maps(
    *,
    user,
    fiscal_year: int,
    flow_family: str,
    legacy_fk_name: str,
    positive_side: str,
) -> tuple[dict[tuple[str, str, int], Decimal], dict[tuple[int, int], Decimal]]:
    queryset = (
        LedgerEntry.objects.filter(
            transaction__user=user,
            transaction__status=LedgerTransaction.Status.POSTED,
            transaction__booking_date__year=fiscal_year,
        )
        .select_related("transaction", "annual_income_entry", "annual_expense_entry", "liability")
        .only(
            "transaction_id",
            "side",
            "amount",
            "flow_family",
            "category_key",
            "subcategory_key",
            "annual_income_entry_id",
            "annual_expense_entry_id",
            "liability_id",
            "liability__category",
            "transaction__booking_date",
            "annual_income_entry__category",
            "annual_income_entry__subcategory",
            "annual_expense_entry__category",
            "annual_expense_entry__subcategory",
        )
    )
    rows = list(queryset)
    mortgage_payment_transaction_ids = {
        row.transaction_id
        for row in rows
        if row.liability_id is not None
        and row.liability is not None
        and row.liability.category == "mortgage"
        and row.flow_family == LedgerEntry.FlowFamily.EXPENSE
    }
    categorized_totals: dict[tuple[str, str, int], Decimal] = defaultdict(lambda: Decimal("0.00"))
    legacy_totals: dict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in rows:
        resolved_flow_family, category_key, subcategory_key, is_primary_classification = (
            _resolve_ledger_budget_classification(
                row,
                mortgage_payment_transaction_ids=mortgage_payment_transaction_ids,
            )
        )
        if resolved_flow_family != flow_family:
            continue
        signed_amount = Decimal(row.amount) if row.side == positive_side else -Decimal(row.amount)
        if is_primary_classification and category_key and subcategory_key:
            key = (category_key, subcategory_key, row.transaction.booking_date.month)
            categorized_totals[key] += signed_amount
            continue
        entry_id = getattr(row, f"{legacy_fk_name}_id")
        if entry_id is None:
            continue
        legacy_totals[(entry_id, row.transaction.booking_date.month)] += signed_amount
    return (
        {key: _round_money(value) for key, value in categorized_totals.items()},
        {key: _round_money(value) for key, value in legacy_totals.items()},
    )


def _resolve_coverage_mode(*, ledger_count: int, fallback_count: int) -> str:
    if ledger_count > 0 and fallback_count > 0:
        return "mixed"
    if ledger_count > 0:
        return "ledger"
    if fallback_count > 0:
        return "checkin"
    return "none"


def _build_expense_execution_breakdown(
    *,
    planned_by_slot_month: dict[tuple[str, str, int], Decimal],
    executed_budgeted_by_slot_month: dict[tuple[str, str, int], Decimal],
    executed_unbudgeted_by_slot_month: dict[tuple[str, str, int], Decimal],
) -> dict:
    category_bucket: dict[str, dict[str, object]] = {}

    def _ensure_category(category_key: str) -> dict[str, object]:
        category = category_bucket.get(category_key)
        if category is not None:
            return category
        category = {
            "category": category_key,
            "planned_total": Decimal("0.00"),
            "executed_budgeted_total": Decimal("0.00"),
            "executed_unbudgeted_total": Decimal("0.00"),
            "subcategories": {},
        }
        category_bucket[category_key] = category
        return category

    def _ensure_subcategory(category: dict[str, object], subcategory_key: str) -> dict[str, object]:
        subcategories = cast(dict[str, dict[str, object]], category["subcategories"])
        subcategory = subcategories.get(subcategory_key)
        if subcategory is not None:
            return subcategory
        subcategory = {
            "subcategory": subcategory_key,
            "planned_total": Decimal("0.00"),
            "executed_budgeted_total": Decimal("0.00"),
            "executed_unbudgeted_total": Decimal("0.00"),
            "months": {
                month: {
                    "planned": Decimal("0.00"),
                    "executed_budgeted": Decimal("0.00"),
                    "executed_unbudgeted": Decimal("0.00"),
                }
                for month in range(1, 13)
            },
        }
        subcategories[subcategory_key] = subcategory
        return subcategory

    all_keys = (
        set(planned_by_slot_month)
        | set(executed_budgeted_by_slot_month)
        | set(executed_unbudgeted_by_slot_month)
    )
    for category_key, subcategory_key, month in sorted(all_keys):
        planned = planned_by_slot_month.get((category_key, subcategory_key, month), Decimal("0.00"))
        executed_budgeted = executed_budgeted_by_slot_month.get(
            (category_key, subcategory_key, month), Decimal("0.00")
        )
        executed_unbudgeted = executed_unbudgeted_by_slot_month.get(
            (category_key, subcategory_key, month), Decimal("0.00")
        )
        if planned == 0 and executed_budgeted == 0 and executed_unbudgeted == 0:
            continue
        category = _ensure_category(category_key)
        subcategory = _ensure_subcategory(category, subcategory_key)

        category["planned_total"] = cast(Decimal, category["planned_total"]) + planned
        category["executed_budgeted_total"] = (
            cast(Decimal, category["executed_budgeted_total"]) + executed_budgeted
        )
        category["executed_unbudgeted_total"] = (
            cast(Decimal, category["executed_unbudgeted_total"]) + executed_unbudgeted
        )
        subcategory["planned_total"] = cast(Decimal, subcategory["planned_total"]) + planned
        subcategory["executed_budgeted_total"] = (
            cast(Decimal, subcategory["executed_budgeted_total"]) + executed_budgeted
        )
        subcategory["executed_unbudgeted_total"] = (
            cast(Decimal, subcategory["executed_unbudgeted_total"]) + executed_unbudgeted
        )
        month_bucket = cast(dict[int, dict[str, Decimal]], subcategory["months"]).setdefault(
            month,
            {
                "planned": Decimal("0.00"),
                "executed_budgeted": Decimal("0.00"),
                "executed_unbudgeted": Decimal("0.00"),
            },
        )
        month_bucket["planned"] += planned
        month_bucket["executed_budgeted"] += executed_budgeted
        month_bucket["executed_unbudgeted"] += executed_unbudgeted

    categories_payload = []
    executed_budgeted_total = Decimal("0.00")
    executed_unbudgeted_total = Decimal("0.00")
    executed_total = Decimal("0.00")

    for category in category_bucket.values():
        subcategories = cast(dict[str, dict[str, object]], category["subcategories"])
        category_subcategories = []
        for subcategory in subcategories.values():
            months_payload = []
            for month in range(1, 13):
                month_bucket = cast(dict[int, dict[str, Decimal]], subcategory["months"])[month]
                month_planned = _round_money(month_bucket["planned"])
                month_budgeted = _round_money(month_bucket["executed_budgeted"])
                month_unbudgeted = _round_money(month_bucket["executed_unbudgeted"])
                month_total = _round_money(month_budgeted + month_unbudgeted)
                months_payload.append(
                    {
                        "month": month,
                        "planned": str(month_planned),
                        "executed_budgeted": str(month_budgeted),
                        "executed_unbudgeted": str(month_unbudgeted),
                        "executed_total": str(month_total),
                    }
                )
            sub_planned = _round_money(cast(Decimal, subcategory["planned_total"]))
            sub_budgeted = _round_money(cast(Decimal, subcategory["executed_budgeted_total"]))
            sub_unbudgeted = _round_money(cast(Decimal, subcategory["executed_unbudgeted_total"]))
            sub_total = _round_money(sub_budgeted + sub_unbudgeted)
            category_subcategories.append(
                {
                    "subcategory": cast(str, subcategory["subcategory"]),
                    "planned_total": str(sub_planned),
                    "executed_budgeted_total": str(sub_budgeted),
                    "executed_unbudgeted_total": str(sub_unbudgeted),
                    "executed_total": str(sub_total),
                    "has_budgeted_line": sub_planned > 0,
                    "has_unbudgeted_execution": sub_unbudgeted > 0,
                    "months": months_payload,
                }
            )
        category_subcategories.sort(
            key=lambda item: (
                -Decimal(cast(str, item["executed_total"])),
                -Decimal(cast(str, item["planned_total"])),
                cast(str, item["subcategory"]),
            )
        )

        cat_planned = _round_money(cast(Decimal, category["planned_total"]))
        cat_budgeted = _round_money(cast(Decimal, category["executed_budgeted_total"]))
        cat_unbudgeted = _round_money(cast(Decimal, category["executed_unbudgeted_total"]))
        cat_total = _round_money(cat_budgeted + cat_unbudgeted)
        executed_budgeted_total += cat_budgeted
        executed_unbudgeted_total += cat_unbudgeted
        executed_total += cat_total
        categories_payload.append(
            {
                "category": cast(str, category["category"]),
                "planned_total": str(cat_planned),
                "executed_budgeted_total": str(cat_budgeted),
                "executed_unbudgeted_total": str(cat_unbudgeted),
                "executed_total": str(cat_total),
                "has_budgeted_lines": cat_planned > 0,
                "has_unbudgeted_execution": cat_unbudgeted > 0,
                "subcategories": category_subcategories,
            }
        )

    categories_payload.sort(
        key=lambda item: (
            -Decimal(cast(str, item["executed_total"])),
            -Decimal(cast(str, item["planned_total"])),
            cast(str, item["category"]),
        )
    )

    return {
        "categories": categories_payload,
        "executed_budgeted_total": str(_round_money(executed_budgeted_total)),
        "executed_unbudgeted_total": str(_round_money(executed_unbudgeted_total)),
        "executed_total": str(_round_money(executed_total)),
    }


def expense_entry_applies_to_fiscal_year(*, entry: AnnualExpenseEntry, fiscal_year: int) -> bool:
    if entry.fiscal_year != fiscal_year:
        return False
    if entry.time_profile != AnnualExpenseEntry.TimeProfile.TERM_RECURRENT:
        return True
    if entry.term_end_year is None:
        return True
    return entry.term_end_year >= fiscal_year


def planned_expense_monthly_distribution(
    *, entry: AnnualExpenseEntry, fiscal_year: int
) -> dict[int, Decimal]:
    amount = Decimal(entry.amount_annual or 0)
    if amount <= 0:
        return {}
    if not expense_entry_applies_to_fiscal_year(entry=entry, fiscal_year=fiscal_year):
        return {}
    if (
        entry.time_profile == AnnualExpenseEntry.TimeProfile.ONE_OFF
        or entry.expense_type == AnnualExpenseEntry.ExpenseType.ONE_OFF
    ):
        if not entry.target_month:
            return {}
        return {int(entry.target_month): _round_money(amount)}

    end_month = 12
    if (
        entry.time_profile == AnnualExpenseEntry.TimeProfile.TERM_RECURRENT
        and (entry.term_end_year is None or entry.term_end_year == fiscal_year)
    ):
        end_month = entry.term_end_month or 12
    base = _round_money(amount / Decimal(end_month))
    distribution = {month: base for month in range(1, end_month + 1)}
    total = sum(distribution.values(), Decimal("0.00"))
    delta = _round_money(amount - total)
    if delta:
        distribution[end_month] = _round_money(distribution[end_month] + delta)
    return distribution


def build_expense_monthly_plan_vs_executed_summary(*, user, fiscal_year: int) -> dict:
    entries = list(
        AnnualExpenseEntry.objects.filter(user=user, is_active=True, fiscal_year=fiscal_year)
        .only(
            "id",
            "fiscal_year",
            "expense_type",
            "time_profile",
            "target_month",
            "term_end_month",
            "term_end_year",
            "amount_annual",
        )
        .order_by("id")
    )
    entries_by_id = {entry.id: entry for entry in entries}
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
    categorized_ledger_by_key, legacy_ledger_by_key = _build_ledger_monthly_execution_maps(
        user=user,
        fiscal_year=fiscal_year,
        flow_family=cast(str, LedgerEntry.FlowFamily.EXPENSE),
        legacy_fk_name="annual_expense_entry",
        positive_side=cast(str, LedgerEntry.Side.DEBIT),
    )

    planned_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    executed_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    pending_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    confirmed_entries_by_month = {month: 0 for month in range(1, 13)}
    expected_entries_by_month = {month: 0 for month in range(1, 13)}
    ledger_entries_by_month = {month: 0 for month in range(1, 13)}
    fallback_entries_by_month = {month: 0 for month in range(1, 13)}
    planned_entry_amounts_by_key: dict[tuple[int, int], Decimal] = {}
    planned_slots: dict[tuple[str, str, int], dict[str, object]] = {}
    planned_by_slot_month: dict[tuple[str, str, int], Decimal] = defaultdict(
        lambda: Decimal("0.00")
    )
    executed_budgeted_by_slot_month: dict[tuple[str, str, int], Decimal] = defaultdict(
        lambda: Decimal("0.00")
    )

    for entry in entries:
        distribution = planned_expense_monthly_distribution(entry=entry, fiscal_year=fiscal_year)
        for month, planned_amount in distribution.items():
            planned_by_month[month] += planned_amount
            expected_entries_by_month[month] += 1
            planned_entry_amounts_by_key[(entry.id, month)] = planned_amount
            slot_key = (entry.category, entry.subcategory, month)
            slot = planned_slots.get(slot_key)
            if slot is None:
                slot = {"entry_ids": [], "month": month}
                planned_slots[slot_key] = slot
            cast(list[int], slot["entry_ids"]).append(entry.id)
            planned_by_slot_month[slot_key] += planned_amount

    for slot_key, slot in planned_slots.items():
        month = cast(int, slot["month"])
        entry_ids = cast(list[int], slot["entry_ids"])
        ledger_amount = categorized_ledger_by_key.get(slot_key)
        if ledger_amount is not None:
            ledger_entries_by_month[month] += len(entry_ids)
            confirmed_entries_by_month[month] += len(entry_ids)
            executed_by_month[month] += ledger_amount
            executed_budgeted_by_slot_month[slot_key] += ledger_amount
            continue
        for entry_id in entry_ids:
            legacy_ledger_amount = legacy_ledger_by_key.get((entry_id, month))
            if legacy_ledger_amount is not None:
                fallback_entries_by_month[month] += 1
                confirmed_entries_by_month[month] += 1
                executed_by_month[month] += legacy_ledger_amount
                entry = entries_by_id[entry_id]
                budget_key = (entry.category, entry.subcategory, month)
                executed_budgeted_by_slot_month[budget_key] += legacy_ledger_amount
                continue
            checkin = checkins_by_key.get((entry_id, month))
            if checkin is None:
                pending_by_month[month] += planned_entry_amounts_by_key[(entry_id, month)]
                continue
            fallback_entries_by_month[month] += 1
            confirmed_entries_by_month[month] += 1
            if checkin.status == AnnualExpenseMonthlyCheckin.Status.SKIPPED:
                continue
            executed_amount = Decimal(checkin.executed_amount or 0)
            resolved_executed = _round_money(executed_amount)
            executed_by_month[month] += resolved_executed
            entry = entries_by_id[entry_id]
            budget_key = (entry.category, entry.subcategory, month)
            executed_budgeted_by_slot_month[budget_key] += resolved_executed

    executed_unbudgeted_by_slot_month: dict[tuple[str, str, int], Decimal] = defaultdict(
        lambda: Decimal("0.00")
    )
    executed_unbudgeted_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    for slot_key, ledger_amount in categorized_ledger_by_key.items():
        if slot_key in planned_slots:
            continue
        executed_unbudgeted_by_slot_month[slot_key] += ledger_amount
        month = slot_key[2]
        executed_unbudgeted_by_month[month] += ledger_amount

    planned_total = sum(planned_by_month.values(), Decimal("0.00"))
    executed_budgeted_total = sum(executed_by_month.values(), Decimal("0.00"))
    executed_unbudgeted_total = sum(executed_unbudgeted_by_month.values(), Decimal("0.00"))
    executed_total = executed_budgeted_total + executed_unbudgeted_total
    pending_total = sum(pending_by_month.values(), Decimal("0.00"))
    unbudgeted_ledger_months = sum(
        1 for amount in executed_unbudgeted_by_month.values() if amount != Decimal("0.00")
    )
    unbudgeted_ledger_slots_total = sum(
        1 for amount in executed_unbudgeted_by_slot_month.values() if amount != Decimal("0.00")
    )

    months_payload = []
    months_with_checkins = 0
    months_with_ledger = 0
    months_with_fallback = 0
    months_with_coverage = 0
    expected_slots_total = 0
    confirmed_slots_total = 0
    ledger_slots_total = 0
    fallback_slots_total = 0
    for month in range(1, 13):
        expected = expected_entries_by_month[month]
        confirmed = confirmed_entries_by_month[month]
        ledger_count = ledger_entries_by_month[month]
        fallback_count = fallback_entries_by_month[month]
        expected_slots_total += expected
        confirmed_slots_total += confirmed
        ledger_slots_total += ledger_count
        fallback_slots_total += fallback_count
        if fallback_count > 0:
            months_with_checkins += 1
            months_with_fallback += 1
        if ledger_count > 0:
            months_with_ledger += 1
        month_unbudgeted = _round_money(executed_unbudgeted_by_month[month])
        month_budgeted = _round_money(executed_by_month[month])
        month_total = _round_money(month_budgeted + month_unbudgeted)
        if confirmed > 0 or month_unbudgeted > 0:
            months_with_coverage += 1
        completion_ratio = 1.0 if expected == 0 else (confirmed / expected)
        months_payload.append(
            {
                "month": month,
                "planned": str(_round_money(planned_by_month[month])),
                "executed": str(month_total),
                "executed_budgeted": str(month_budgeted),
                "executed_unbudgeted": str(month_unbudgeted),
                "executed_total": str(month_total),
                "pending": str(_round_money(pending_by_month[month])),
                "completion_ratio": round(completion_ratio, 4),
                "checkins_confirmed": confirmed,
                "checkins_expected": expected,
                "ledger_confirmed": ledger_count,
                "fallback_confirmed": fallback_count,
                "coverage_mode": _resolve_coverage_mode(
                    ledger_count=ledger_count,
                    fallback_count=fallback_count,
                ),
            }
        )

    total_completion_ratio = (
        1.0 if expected_slots_total == 0 else round(confirmed_slots_total / expected_slots_total, 4)
    )
    expense_execution_breakdown = _build_expense_execution_breakdown(
        planned_by_slot_month=planned_by_slot_month,
        executed_budgeted_by_slot_month=executed_budgeted_by_slot_month,
        executed_unbudgeted_by_slot_month=executed_unbudgeted_by_slot_month,
    )

    return {
        "fiscal_year": fiscal_year,
        "planned_total": str(_round_money(planned_total)),
        "executed_total": str(_round_money(executed_total)),
        "executed_budgeted_total": str(_round_money(executed_budgeted_total)),
        "executed_unbudgeted_total": str(_round_money(executed_unbudgeted_total)),
        "pending_total": str(_round_money(pending_total)),
        "variance_total": str(_round_money(executed_total - planned_total)),
        "months": months_payload,
        "completion_ratio": total_completion_ratio,
        "months_with_checkins": months_with_checkins,
        "months_with_ledger": months_with_ledger + unbudgeted_ledger_months,
        "months_with_fallback": months_with_fallback,
        "months_with_coverage": months_with_coverage,
        "has_ledger_data": ledger_slots_total > 0 or unbudgeted_ledger_slots_total > 0,
        "has_executed_data": confirmed_slots_total > 0 or unbudgeted_ledger_slots_total > 0,
        "coverage_mode": _resolve_coverage_mode(
            ledger_count=ledger_slots_total + unbudgeted_ledger_slots_total,
            fallback_count=fallback_slots_total,
        ),
        "expense_execution_breakdown": expense_execution_breakdown,
    }


def income_entry_applies_to_fiscal_year(*, entry: AnnualIncomeEntry, fiscal_year: int) -> bool:
    if entry.fiscal_year != fiscal_year:
        return False
    if entry.time_profile != AnnualIncomeEntry.TimeProfile.TERM_RECURRENT:
        return True
    if entry.term_end_year is None:
        return True
    return entry.term_end_year >= fiscal_year


def planned_income_monthly_distribution(
    *, entry: AnnualIncomeEntry, fiscal_year: int
) -> dict[int, Decimal]:
    amount = Decimal(entry.amount_annual or 0)
    if amount <= 0:
        return {}
    if not income_entry_applies_to_fiscal_year(entry=entry, fiscal_year=fiscal_year):
        return {}
    if entry.time_profile == AnnualIncomeEntry.TimeProfile.ONE_OFF:
        if not entry.target_month:
            return {}
        return {int(entry.target_month): _round_money(amount)}

    end_month = 12
    if (
        entry.time_profile == AnnualIncomeEntry.TimeProfile.TERM_RECURRENT
        and entry.term_end_year == fiscal_year
    ):
        end_month = entry.term_end_month or 12
    if entry.target_month and 1 <= int(entry.target_month) <= end_month:
        return {int(entry.target_month): _round_money(amount)}

    base = _round_money(amount / Decimal("12"))
    distribution = {month: base for month in range(1, end_month + 1)}
    total = sum(distribution.values(), Decimal("0.00"))
    delta = _round_money(amount - total)
    if delta:
        distribution[end_month] = _round_money(distribution[end_month] + delta)
    return distribution


def build_income_monthly_plan_vs_executed_summary(*, user, fiscal_year: int) -> dict:
    entries = list(
        AnnualIncomeEntry.objects.filter(user=user, is_active=True, fiscal_year=fiscal_year)
        .only(
            "id",
            "fiscal_year",
            "time_profile",
            "target_month",
            "term_end_month",
            "term_end_year",
            "amount_annual",
        )
        .order_by("id")
    )
    entries_by_id = {entry.id: entry for entry in entries}
    checkins = list(
        AnnualIncomeMonthlyCheckin.objects.filter(user=user, fiscal_year=fiscal_year).only(
            "annual_income_entry_id", "month", "status", "executed_amount"
        )
    )
    checkins_by_key = {
        (item.annual_income_entry_id, item.month): item
        for item in checkins
        if 1 <= item.month <= 12
    }
    categorized_ledger_by_key, legacy_ledger_by_key = _build_ledger_monthly_execution_maps(
        user=user,
        fiscal_year=fiscal_year,
        flow_family=cast(str, LedgerEntry.FlowFamily.INCOME),
        legacy_fk_name="annual_income_entry",
        positive_side=cast(str, LedgerEntry.Side.CREDIT),
    )

    planned_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    executed_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    pending_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    confirmed_entries_by_month = {month: 0 for month in range(1, 13)}
    expected_entries_by_month = {month: 0 for month in range(1, 13)}
    ledger_entries_by_month = {month: 0 for month in range(1, 13)}
    fallback_entries_by_month = {month: 0 for month in range(1, 13)}
    planned_entry_amounts_by_key: dict[tuple[int, int], Decimal] = {}
    planned_slots: dict[tuple[str, str, int], dict[str, object]] = {}
    planned_by_slot_month: dict[tuple[str, str, int], Decimal] = defaultdict(
        lambda: Decimal("0.00")
    )
    executed_budgeted_by_slot_month: dict[tuple[str, str, int], Decimal] = defaultdict(
        lambda: Decimal("0.00")
    )

    for entry in entries:
        distribution = planned_income_monthly_distribution(entry=entry, fiscal_year=fiscal_year)
        for month, planned_amount in distribution.items():
            planned_by_month[month] += planned_amount
            expected_entries_by_month[month] += 1
            planned_entry_amounts_by_key[(entry.id, month)] = planned_amount
            slot_key = (entry.category, entry.subcategory, month)
            slot = planned_slots.get(slot_key)
            if slot is None:
                slot = {"entry_ids": [], "month": month}
                planned_slots[slot_key] = slot
            cast(list[int], slot["entry_ids"]).append(entry.id)
            planned_by_slot_month[slot_key] += planned_amount

    for slot_key, slot in planned_slots.items():
        month = cast(int, slot["month"])
        entry_ids = cast(list[int], slot["entry_ids"])
        ledger_amount = categorized_ledger_by_key.get(slot_key)
        if ledger_amount is not None:
            ledger_entries_by_month[month] += len(entry_ids)
            confirmed_entries_by_month[month] += len(entry_ids)
            executed_by_month[month] += ledger_amount
            executed_budgeted_by_slot_month[slot_key] += ledger_amount
            continue
        for entry_id in entry_ids:
            legacy_ledger_amount = legacy_ledger_by_key.get((entry_id, month))
            if legacy_ledger_amount is not None:
                fallback_entries_by_month[month] += 1
                confirmed_entries_by_month[month] += 1
                executed_by_month[month] += legacy_ledger_amount
                entry = entries_by_id[entry_id]
                budget_key = (entry.category, entry.subcategory, month)
                executed_budgeted_by_slot_month[budget_key] += legacy_ledger_amount
                continue
            checkin = checkins_by_key.get((entry_id, month))
            if checkin is None:
                pending_by_month[month] += planned_entry_amounts_by_key[(entry_id, month)]
                continue
            fallback_entries_by_month[month] += 1
            confirmed_entries_by_month[month] += 1
            if checkin.status == AnnualIncomeMonthlyCheckin.Status.SKIPPED:
                continue
            executed_amount = Decimal(checkin.executed_amount or 0)
            resolved_executed = _round_money(executed_amount)
            executed_by_month[month] += resolved_executed
            entry = entries_by_id[entry_id]
            budget_key = (entry.category, entry.subcategory, month)
            executed_budgeted_by_slot_month[budget_key] += resolved_executed

    executed_unbudgeted_by_slot_month: dict[tuple[str, str, int], Decimal] = defaultdict(
        lambda: Decimal("0.00")
    )
    executed_unbudgeted_by_month = {month: Decimal("0.00") for month in range(1, 13)}
    for slot_key, ledger_amount in categorized_ledger_by_key.items():
        if slot_key in planned_slots:
            continue
        executed_unbudgeted_by_slot_month[slot_key] += ledger_amount
        month = slot_key[2]
        executed_unbudgeted_by_month[month] += ledger_amount

    planned_total = sum(planned_by_month.values(), Decimal("0.00"))
    executed_budgeted_total = sum(executed_by_month.values(), Decimal("0.00"))
    executed_unbudgeted_total = sum(executed_unbudgeted_by_month.values(), Decimal("0.00"))
    executed_total = executed_budgeted_total + executed_unbudgeted_total
    pending_total = sum(pending_by_month.values(), Decimal("0.00"))
    unbudgeted_ledger_months = sum(
        1 for amount in executed_unbudgeted_by_month.values() if amount != Decimal("0.00")
    )
    unbudgeted_ledger_slots_total = sum(
        1 for amount in executed_unbudgeted_by_slot_month.values() if amount != Decimal("0.00")
    )

    months_payload = []
    months_with_checkins = 0
    months_with_ledger = 0
    months_with_fallback = 0
    months_with_coverage = 0
    expected_slots_total = 0
    confirmed_slots_total = 0
    ledger_slots_total = 0
    fallback_slots_total = 0
    for month in range(1, 13):
        expected = expected_entries_by_month[month]
        confirmed = confirmed_entries_by_month[month]
        ledger_count = ledger_entries_by_month[month]
        fallback_count = fallback_entries_by_month[month]
        expected_slots_total += expected
        confirmed_slots_total += confirmed
        ledger_slots_total += ledger_count
        fallback_slots_total += fallback_count
        if fallback_count > 0:
            months_with_checkins += 1
            months_with_fallback += 1
        if ledger_count > 0:
            months_with_ledger += 1
        month_unbudgeted = _round_money(executed_unbudgeted_by_month[month])
        month_budgeted = _round_money(executed_by_month[month])
        month_total = _round_money(month_budgeted + month_unbudgeted)
        if confirmed > 0 or month_unbudgeted > 0:
            months_with_coverage += 1
        completion_ratio = 1.0 if expected == 0 else (confirmed / expected)
        months_payload.append(
            {
                "month": month,
                "planned": str(_round_money(planned_by_month[month])),
                "executed": str(month_total),
                "executed_budgeted": str(month_budgeted),
                "executed_unbudgeted": str(month_unbudgeted),
                "executed_total": str(month_total),
                "pending": str(_round_money(pending_by_month[month])),
                "completion_ratio": round(completion_ratio, 4),
                "checkins_confirmed": confirmed,
                "checkins_expected": expected,
                "ledger_confirmed": ledger_count,
                "fallback_confirmed": fallback_count,
                "coverage_mode": _resolve_coverage_mode(
                    ledger_count=ledger_count,
                    fallback_count=fallback_count,
                ),
            }
        )

    total_completion_ratio = (
        1.0 if expected_slots_total == 0 else round(confirmed_slots_total / expected_slots_total, 4)
    )
    income_execution_breakdown = _build_expense_execution_breakdown(
        planned_by_slot_month=planned_by_slot_month,
        executed_budgeted_by_slot_month=executed_budgeted_by_slot_month,
        executed_unbudgeted_by_slot_month=executed_unbudgeted_by_slot_month,
    )
    return {
        "fiscal_year": fiscal_year,
        "planned_total": str(_round_money(planned_total)),
        "executed_total": str(_round_money(executed_total)),
        "executed_budgeted_total": str(_round_money(executed_budgeted_total)),
        "executed_unbudgeted_total": str(_round_money(executed_unbudgeted_total)),
        "pending_total": str(_round_money(pending_total)),
        "variance_total": str(_round_money(executed_total - planned_total)),
        "months": months_payload,
        "completion_ratio": total_completion_ratio,
        "months_with_checkins": months_with_checkins,
        "months_with_ledger": months_with_ledger + unbudgeted_ledger_months,
        "months_with_fallback": months_with_fallback,
        "months_with_coverage": months_with_coverage,
        "has_ledger_data": ledger_slots_total > 0 or unbudgeted_ledger_slots_total > 0,
        "has_executed_data": confirmed_slots_total > 0 or unbudgeted_ledger_slots_total > 0,
        "coverage_mode": _resolve_coverage_mode(
            ledger_count=ledger_slots_total + unbudgeted_ledger_slots_total,
            fallback_count=fallback_slots_total,
        ),
        "income_execution_breakdown": income_execution_breakdown,
    }
