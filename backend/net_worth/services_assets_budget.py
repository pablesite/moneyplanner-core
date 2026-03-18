from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import cast

from django.db.models import Q
from django.utils import timezone

from .models import Asset
from .services_assets_core import (
    INVESTMENTS_SUBCATEGORY_TO_EXPENSE_SUBCATEGORY,
    SYSTEM_GENERATED_ASSET_EXPENSE_EVENT_PREFIX,
)
from .services_liabilities_core import _add_months_preserve_day


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


def _get_generated_asset_expense_profile(*, asset: Asset) -> tuple[str, str]:
    from budget.models import AnnualExpenseEntry

    if asset.category == Asset.Category.INVESTMENTS:
        return (
            cast(str, AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS),
            INVESTMENTS_SUBCATEGORY_TO_EXPENSE_SUBCATEGORY.get(
                asset.subcategory, "other_financial_investments"
            ),
        )

    return (cast(str, AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS), "property_purchase")


def _build_investment_contribution_schedule(
    *,
    asset: Asset,
    as_of_date: date | None = None,
    horizon_end_date: date | None = None,
) -> list[tuple[date, Decimal]]:
    if (
        asset.category != Asset.Category.INVESTMENTS
        or asset.investment_contribution_mode
        != Asset.InvestmentContributionMode.PERIODIC_CONTRIBUTION
        or asset.monthly_contribution_amount is None
        or asset.monthly_contribution_amount <= 0
    ):
        return []

    schedule_end = asset.expected_end_date
    bounded_end = horizon_end_date or as_of_date
    if schedule_end is None:
        schedule_end = bounded_end or timezone.localdate()
    elif bounded_end is not None:
        schedule_end = min(schedule_end, bounded_end)
    if schedule_end < asset.start_date:
        return []

    frequency = (
        asset.investment_contribution_frequency or Asset.InvestmentContributionFrequency.MONTHLY
    )
    schedule: list[tuple[date, Decimal]] = []
    due_date = asset.start_date
    installment = Decimal(asset.monthly_contribution_amount)
    while due_date <= schedule_end:
        schedule.append((due_date, installment))
        if frequency == Asset.InvestmentContributionFrequency.WEEKLY:
            due_date += timedelta(days=7)
        else:
            due_date = _add_months_preserve_day(due_date, 1)
    return schedule


def sync_generated_budget_commitments_for_asset(*, asset: Asset) -> None:
    from budget.models import AnnualExpenseEntry

    schedule = []
    if asset.is_active:
        horizon_year = timezone.localdate().year + 1
        schedule = _build_investment_contribution_schedule(
            asset=asset,
            horizon_end_date=date(horizon_year, 12, 31),
        )
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
    expense_category, expense_subcategory = _get_generated_asset_expense_profile(asset=asset)
    final_due_year = schedule[-1][0].year if asset.expected_end_date is not None else None
    for year, annual_total in totals_by_year.items():
        time_profile = (
            AnnualExpenseEntry.TimeProfile.TERM_RECURRENT
            if final_due_year is not None
            else AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT
        )
        contribution_currency = (
            str(asset.investment_contribution_currency or "").strip().upper()
            or str(asset.currency).strip().upper()
        )
        generated_defaults = {
            "name": f"Aportacion inversion: {asset.name}",
            "category": expense_category,
            "subcategory": expense_subcategory,
            "owner_name": owner_name,
            "expense_type": AnnualExpenseEntry.ExpenseType.RECURRENT,
            "time_profile": time_profile,
            "cashflow_role": AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            "event_group": event_group,
            "term_end_year": final_due_year,
            "amount_annual": annual_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            "currency": contribution_currency,
            "notes": "Generado automaticamente desde activo de inversion periodica (editable).",
            "is_active": True,
        }
        row = AnnualExpenseEntry.objects.filter(
            user=asset.user,
            source_asset=asset,
            is_system_generated=True,
            fiscal_year=year,
        ).first()
        created = False
        if row is None:
            # Backward-compat: recover legacy rows linked only by event_group.
            row = AnnualExpenseEntry.objects.filter(
                user=asset.user,
                source_asset__isnull=True,
                is_system_generated=True,
                fiscal_year=year,
                event_group=event_group,
            ).first()
            if row is not None:
                row.source_asset = asset
                row.save(update_fields=["source_asset"])
            else:
                row = AnnualExpenseEntry.objects.create(
                    user=asset.user,
                    source_asset=asset,
                    is_system_generated=True,
                    fiscal_year=year,
                    **generated_defaults,
                )
                created = True
        if created:
            continue

        system_owned_fields = [
            "owner_name",
            "term_end_year",
            "currency",
            "event_group",
            "is_active",
            "amount_annual",
        ]
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
        is_system_generated=True,
    ).filter(Q(source_asset=asset) | Q(event_group=event_group)).exclude(
        fiscal_year__in=list(totals_by_year.keys())
    ).delete()


def delete_generated_budget_commitments_for_asset(*, asset: Asset) -> None:
    from budget.models import AnnualExpenseEntry

    event_group = f"{SYSTEM_GENERATED_ASSET_EXPENSE_EVENT_PREFIX}{asset.id}"
    AnnualExpenseEntry.objects.filter(
        user=asset.user,
        is_system_generated=True,
    ).filter(Q(source_asset=asset) | Q(event_group=event_group)).delete()
