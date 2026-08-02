from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import cast

from django.db import transaction
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


def build_investment_contribution_schedule(
    *,
    asset: Asset,
    as_of_date: date | None = None,
    horizon_end_date: date | None = None,
) -> list[tuple[date, Decimal]]:
    if asset.category != Asset.Category.INVESTMENTS:
        return []
    intervals = list(asset.contribution_intervals.all())
    if not intervals:
        return []
    schedule: list[tuple[date, Decimal]] = []
    for interval in intervals:
        schedule.extend(
            _build_interval_schedule(
                start_date=interval.start_date,
                end_date=interval.end_date,
                amount=Decimal(interval.amount),
                frequency=interval.frequency,
                as_of_date=as_of_date,
                horizon_end_date=horizon_end_date,
            )
        )
    return sorted(schedule, key=lambda row: row[0])


def _build_interval_schedule(
    *,
    start_date: date,
    end_date: date | None,
    amount: Decimal,
    frequency: str,
    as_of_date: date | None = None,
    horizon_end_date: date | None = None,
) -> list[tuple[date, Decimal]]:
    if amount <= 0:
        return []
    schedule_end = end_date
    bounded_end = horizon_end_date or as_of_date
    if schedule_end is None:
        schedule_end = bounded_end or timezone.localdate()
    elif bounded_end is not None:
        schedule_end = min(schedule_end, bounded_end)
    if schedule_end < start_date:
        return []

    schedule: list[tuple[date, Decimal]] = []
    due_date = start_date
    while due_date <= schedule_end:
        schedule.append((due_date, amount))
        if frequency == Asset.InvestmentContributionFrequency.WEEKLY:
            due_date += timedelta(days=7)
        else:
            due_date = _add_months_preserve_day(due_date, 1)
    return schedule


@transaction.atomic
def sync_generated_budget_commitments_for_asset(*, asset: Asset) -> None:
    from budget.models import AnnualExpenseEntry

    schedule = []
    if asset.is_active:
        horizon_year = timezone.localdate().year + 1
        schedule = build_investment_contribution_schedule(
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
    intervals = list(asset.contribution_intervals.all())
    has_open_interval = any(interval.end_date is None for interval in intervals)
    final_due_year = None if has_open_interval else schedule[-1][0].year
    interval_currencies = {
        str(interval.currency or "").strip().upper()
        for interval in intervals
        if str(interval.currency or "").strip()
    }
    contribution_currency = (
        interval_currencies.pop()
        if len(interval_currencies) == 1
        else str(asset.currency).strip().upper()
    )
    for year, annual_total in totals_by_year.items():
        time_profile = (
            AnnualExpenseEntry.TimeProfile.TERM_RECURRENT
            if final_due_year is not None
            else AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT
        )
        generated_defaults = {
            "name": f"Aportacion inversion: {asset.name}",
            "category": expense_category,
            "subcategory": expense_subcategory,
            "owner_name": owner_name,
            "expense_type": AnnualExpenseEntry.ExpenseType.RECURRENT,
            "time_profile": time_profile,
            # Las aportaciones periodicas son destino de ahorro/inversion, no un
            # compromiso que consume ingresos: van al rol INVESTMENT (coherente con
            # su categoria financial_investments). El motor las cuenta como
            # aportacion via los InvestmentContributionInterval, no aqui.
            "cashflow_role": AnnualExpenseEntry.CashflowRole.INVESTMENT,
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
            "cashflow_role",
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
