from __future__ import annotations

from datetime import date

from net_worth.models import Asset, Liability

from .models import LedgerAccount, LedgerTransaction


def sync_position_start_dates_for_transaction(*, transaction: LedgerTransaction) -> None:
    booking_date = transaction.booking_date
    if booking_date is None:
        return
    account_ids = list(
        transaction.entries.values_list("account_id", flat=True).distinct()
    )
    if not account_ids:
        return
    _sync_asset_start_dates_for_accounts(account_ids=account_ids, booking_date=booking_date)
    _sync_liability_start_dates_for_accounts(account_ids=account_ids, booking_date=booking_date)


def _sync_asset_start_dates_for_accounts(*, account_ids: list[int], booking_date: date) -> None:
    linked_asset_ids = set(
        LedgerAccount.objects.filter(id__in=account_ids, asset_id__isnull=False).values_list(
            "asset_id", flat=True
        )
    )
    if not linked_asset_ids:
        return
    assets = Asset.objects.filter(
        id__in=linked_asset_ids,
        tracking_mode=Asset.TrackingMode.ACCOUNTING,
    )
    for asset in assets:
        if asset.start_date is None or booking_date < asset.start_date:
            asset.start_date = booking_date
            asset.save(update_fields=["start_date", "updated_at"])


def _sync_liability_start_dates_for_accounts(*, account_ids: list[int], booking_date: date) -> None:
    linked_liability_ids = set(
        LedgerAccount.objects.filter(id__in=account_ids, liability_id__isnull=False).values_list(
            "liability_id", flat=True
        )
    )
    if not linked_liability_ids:
        return
    liabilities = Liability.objects.filter(
        id__in=linked_liability_ids,
        tracking_mode=Liability.TrackingMode.ACCOUNTING,
    )
    for liability in liabilities:
        if liability.start_date is None or booking_date < liability.start_date:
            liability.start_date = booking_date
            liability.save(update_fields=["start_date", "updated_at"])
