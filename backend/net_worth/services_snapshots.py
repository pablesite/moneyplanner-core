from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import NetWorthSnapshot


def create_snapshot_for_user(*, user, validated_data: dict) -> NetWorthSnapshot:
    return NetWorthSnapshot.objects.create(user=user, **validated_data)


def _create_or_update_snapshot_from_current_impl(
    *,
    user,
    timezone_localdate_fn,
    get_base_currency_for_user_fn,
    get_active_positions_fn,
    calculate_totals_fn,
) -> tuple[NetWorthSnapshot, bool]:
    snapshot_date = timezone_localdate_fn()
    base_currency = get_base_currency_for_user_fn(user=user)
    assets_qs, liabilities_qs = get_active_positions_fn(user=user)
    totals = calculate_totals_fn(
        assets_qs=assets_qs,
        liabilities_qs=liabilities_qs,
        base_currency=base_currency,
        as_of_date=snapshot_date,
    )
    net_worth = totals.total_assets - totals.total_liabilities

    return NetWorthSnapshot.objects.update_or_create(
        user=user,
        snapshot_date=snapshot_date,
        defaults={
            "base_currency": base_currency,
            "total_assets": totals.total_assets,
            "total_liabilities": totals.total_liabilities,
            "net_worth": net_worth,
        },
    )


def validate_snapshot_payload(*, total_assets, total_liabilities, net_worth):
    if total_assets is None or total_liabilities is None:
        return net_worth

    computed = (total_assets or Decimal("0")) - (total_liabilities or Decimal("0"))
    if net_worth is None:
        return computed
    if net_worth != computed:
        raise ValidationError({"net_worth": "net_worth debe ser total_assets - total_liabilities"})
    return net_worth


@transaction.atomic
def import_snapshots_bulk_for_user(*, user, rows: list[dict]) -> dict[str, object]:
    created_count = 0
    updated_count = 0
    snapshots: list[NetWorthSnapshot] = []

    for row in rows:
        snapshot, created = NetWorthSnapshot.objects.update_or_create(
            user=user,
            snapshot_date=row["snapshot_date"],
            defaults={
                "base_currency": row["base_currency"],
                "total_assets": row["total_assets"],
                "total_liabilities": row["total_liabilities"],
                "net_worth": row["net_worth"],
            },
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
        snapshots.append(snapshot)

    return {
        "ok": True,
        "created": created_count,
        "updated": updated_count,
        "snapshots": snapshots,
    }


def create_or_update_snapshot_from_current(*, user) -> tuple[NetWorthSnapshot, bool]:
    # Local import keeps patching compatibility through `net_worth.services` during transition.
    from . import services as services_facade

    return _create_or_update_snapshot_from_current_impl(
        user=user,
        timezone_localdate_fn=services_facade.timezone.localdate,
        get_base_currency_for_user_fn=services_facade.get_base_currency_for_user,
        get_active_positions_fn=services_facade._get_active_positions,
        calculate_totals_fn=services_facade.calculate_totals,
    )
