"""Keep the portfolio in step with what gets booked in Movimientos.

Cartera reads `PositionValuation`, while net worth and movements read the ledger balance.
A revaluation booked in Movimientos therefore has to reach the portfolio, otherwise the
position stays frozen at its last known value until someone re-runs the bootstrap.

Investment movements need the same bridge for a different reason: registering money is
now Contabilidad's job, so an aporte or a retirada booked there has to leave the same
operation record the portfolio's own form used to leave, or a position followed by units
loses the trail of how many units each operation moved.
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


def _record_trade_from_investment(transaction_id: int) -> None:
    """Leave a `PortfolioTrade` for an investment movement booked in Movimientos.

    The ledger is the monetary source of truth, so value, flows and returns already work
    without this. What would be lost is the operation detail —units and unit price— that
    only exists at the moment of booking, plus the audit row that ties the movement to a
    position. The pairing is deliberately strict: one leg has to be a position's account
    and the other the cash of that position's own container, which is the same rule the
    portfolio form enforced when it funded a purchase.
    """
    from accounting.models import LedgerTransaction

    from .models import ContainerCashAccount, PortfolioPosition, PortfolioTrade

    transaction_row = LedgerTransaction.objects.filter(pk=transaction_id).first()
    if transaction_row is None or hasattr(transaction_row, "portfolio_trade"):
        return
    entries = list(LedgerEntry.objects.filter(transaction_id=transaction_id))
    account_ids = {entry.account_id for entry in entries}
    position = (
        PortfolioPosition.objects.filter(ledger_account_id__in=account_ids)
        .select_related("portfolio", "container", "ledger_account")
        .first()
    )
    if position is None:
        return
    cash = (
        ContainerCashAccount.objects.filter(
            container_id=position.container_id,
            ledger_account_id__in=account_ids - {position.ledger_account_id},
        )
        .select_related("ledger_account")
        .first()
    )
    if cash is None:
        return

    outflow = transaction_row.investment_direction == LedgerTransaction.InvestmentDirection.OUTFLOW
    gross = next(
        (abs(entry.amount) for entry in entries if entry.account_id == position.ledger_account_id),
        None,
    )
    if gross is None:
        return
    PortfolioTrade.objects.create(
        portfolio=position.portfolio,
        position=position,
        ledger_transaction=transaction_row,
        operation_type=(
            PortfolioTrade.OperationType.SELL if outflow else PortfolioTrade.OperationType.BUY
        ),
        units=transaction_row.investment_units,
        unit_price=transaction_row.investment_unit_price,
        trade_currency=position.ledger_account.currency,
        gross_amount=gross,
        source=PortfolioTrade.Source.MANUAL,
        fingerprint=f"accounting:{transaction_row.pk}",
        note=transaction_row.description[:240],
    )


@receiver(post_save, sender=LedgerTransaction, dispatch_uid="portfolio_investment_saved")
def investment_saved(sender, instance: LedgerTransaction, created: bool, **kwargs) -> None:
    if not created or instance.quick_entry_kind != LedgerTransaction.QuickEntryKind.INVESTMENT:
        return
    # Entries land after the transaction row, so the legs can only be paired once the
    # surrounding block commits.
    transaction_id = instance.pk
    db_transaction.on_commit(lambda: _record_trade_from_investment(transaction_id))


@receiver(post_save, sender="net_worth.Asset")
def investment_asset_saved(sender, instance, **kwargs) -> None:
    """Un activo de inversion creado en Patrimonio tiene que llegar a la cartera.

    Hasta ahora solo aparecia si alguien reejecutaba el arranque, y no habia nada en la
    interfaz que lo hiciera: el boton de actualizar resincroniza valoraciones de las
    posiciones que ya existen, no descubre activos nuevos. El resultado era un activo con
    sus movimientos ya contabilizados que no salia en la cartera de ninguna manera.

    Cae en el contenedor neutro y queda pendiente de configurar, porque en que broker
    esta no se puede adivinar.
    """
    from net_worth.models import Asset

    if instance.category != Asset.Category.INVESTMENTS:
        return

    def run() -> None:
        from .models import Portfolio
        from .services import ensure_position_for_asset, fallback_container

        portfolio = Portfolio.objects.filter(user_id=instance.user_id).first()
        if portfolio is None:
            # Sin cartera todavia no hay nada que sincronizar: el arranque la creara y
            # recogera este activo con todos los demas.
            return
        ensure_position_for_asset(
            portfolio=portfolio,
            container=fallback_container(portfolio=portfolio),
            asset=instance,
        )

    db_transaction.on_commit(run)
