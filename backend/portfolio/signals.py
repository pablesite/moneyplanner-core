"""Keep portfolio valuations in step with the accounting revaluations they derive from.

Cartera reads `PositionValuation`, while net worth and movements read the ledger balance.
A revaluation booked in Movimientos therefore has to reach the portfolio, otherwise the
position stays frozen at its last known value until someone re-runs the bootstrap.
"""

from __future__ import annotations

from django.db import transaction as db_transaction
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from accounting.models import LedgerEntry, LedgerTransaction
from memberships.models import OwnershipLink


def _positions_for_transaction(transaction_id: int) -> list[int]:
    from .models import PortfolioPosition

    account_ids = list(
        LedgerEntry.objects.filter(transaction_id=transaction_id).values_list(
            "account_id", flat=True
        )
    )
    if not account_ids:
        return []
    return list(
        PortfolioPosition.objects.filter(ledger_account_id__in=account_ids).values_list(
            "id", flat=True
        )
    )


def _resync(position_ids: list[int]) -> None:
    from .models import PortfolioPosition
    from .valuations import sync_ledger_valuations

    positions = PortfolioPosition.objects.filter(id__in=position_ids).select_related(
        "portfolio", "asset", "instrument", "ledger_account"
    )
    for position in positions:
        sync_ledger_valuations(position=position)


def _schedule_resync(position_ids: list[int]) -> None:
    if position_ids:
        db_transaction.on_commit(lambda: _resync(position_ids))


def _sync_ownership(user_id: int, asset_id: int) -> None:
    from django.contrib.auth import get_user_model

    from .services import sync_position_ownership_for_asset

    user = get_user_model().objects.filter(id=user_id).first()
    if user is not None:
        sync_position_ownership_for_asset(user=user, asset_id=asset_id)


@receiver(post_save, sender=OwnershipLink, dispatch_uid="portfolio_ownership_link_saved")
@receiver(post_delete, sender=OwnershipLink, dispatch_uid="portfolio_ownership_link_deleted")
def ownership_link_changed(sender, instance: OwnershipLink, **kwargs) -> None:
    """Carry a titularidad assigned in Patrimonio into the position that holds the asset.

    Ownership periods were created only by the bootstrap, so anything assigned later never
    arrived and the position sat in the review banner for good. Deletions run through the
    same path on purpose: the period stays, since ownership history is not rewritten, but
    the migration issue is reopened.
    """
    if instance.target_type != OwnershipLink.TargetType.ASSET:
        return
    user_id, asset_id = instance.user_id, instance.target_id
    db_transaction.on_commit(lambda: _sync_ownership(user_id, asset_id))


@receiver(post_save, sender=LedgerTransaction, dispatch_uid="portfolio_revaluation_saved")
def revaluation_saved(sender, instance: LedgerTransaction, **kwargs) -> None:
    if instance.quick_entry_kind != LedgerTransaction.QuickEntryKind.REVALUATION:
        return
    # Entries are written (and on edits, replaced) after the transaction row, so the
    # affected positions can only be resolved once the surrounding block commits.
    db_transaction.on_commit(lambda: _resync(_positions_for_transaction(instance.pk)))


@receiver(pre_delete, sender=LedgerTransaction, dispatch_uid="portfolio_revaluation_deleted")
def revaluation_deleted(sender, instance: LedgerTransaction, **kwargs) -> None:
    if instance.quick_entry_kind != LedgerTransaction.QuickEntryKind.REVALUATION:
        return
    # Entries disappear with the transaction, and every later derived valuation shifts by
    # this delta, so the affected positions are captured before the cascade runs.
    _schedule_resync(_positions_for_transaction(instance.pk))
