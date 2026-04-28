from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from typing import cast

from django.db import transaction
from django.db.models import Q

from .models import Asset, Liability
from .services_liabilities_core import (
    FURNISHINGS_SUBCATEGORY_TO_EXPENSE_SUBCATEGORY,
    INVESTMENTS_SUBCATEGORY_TO_EXPENSE_SUBCATEGORY,
    _last_day_of_month,
    build_liability_installment_schedule_simple,
    estimate_liability_outstanding_amount_simple,
)


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


def _should_include_installment_in_cancellation_month(*, liability: Liability) -> bool:
    return bool(getattr(liability, "cancellation_include_payment_month", True))


def _is_due_before_cancellation(*, liability: Liability, due_date, cancellation_date) -> bool:
    due_month_key = (due_date.year, due_date.month)
    cancellation_month_key = (cancellation_date.year, cancellation_date.month)
    if _should_include_installment_in_cancellation_month(liability=liability):
        return due_month_key <= cancellation_month_key
    return due_month_key < cancellation_month_key


def _cancellation_principal_reference_date(*, liability: Liability, cancellation_date):
    if _should_include_installment_in_cancellation_month(liability=liability):
        return cancellation_date.replace(
            day=_last_day_of_month(cancellation_date.year, cancellation_date.month)
        )
    return cancellation_date.replace(day=1) - timedelta(days=1)


def _estimate_cancellation_remaining_principal(*, liability: Liability, cancellation_date):
    reference_date = _cancellation_principal_reference_date(
        liability=liability,
        cancellation_date=cancellation_date,
    )
    original_flag = liability.cancellation_forecast_enabled
    liability.cancellation_forecast_enabled = False
    try:
        return estimate_liability_outstanding_amount_simple(
            liability=liability,
            as_of_date=reference_date,
        )
    finally:
        liability.cancellation_forecast_enabled = original_flag


@transaction.atomic
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
            (due_date, amount)
            for due_date, amount in full_schedule
            if _is_due_before_cancellation(
                liability=liability,
                due_date=due_date,
                cancellation_date=cancellation_date,
            )
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
        remaining_principal = _estimate_cancellation_remaining_principal(
            liability=liability,
            cancellation_date=cancellation_date,
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
