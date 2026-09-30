"""Link income already booked in accounting to the position that produced it.

A dividend often lands in a current account the portfolio does not hold, so accounting
knows the money arrived but not which holding paid it. Linking reuses `PortfolioTrade` as
the footprint of that movement: nothing new is booked, the ledger stays the monetary
source of truth, and the performance engine reads the link as income of the position.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any, cast

from django.db import transaction as db_transaction
from rest_framework.exceptions import ValidationError

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction

from .models import ContainerCashAccount, PortfolioPosition, PortfolioTrade

LINKABLE_OPERATION_TYPES = {
    cast(str, PortfolioTrade.OperationType.DIVIDEND),
    cast(str, PortfolioTrade.OperationType.INTEREST),
}
# Categorias de ingreso donde vive lo que rinde una inversion. El resto de ingresos
# (nomina, devoluciones) solo aparece si se pide expresamente.
SUGGESTED_CATEGORY_KEYS = ("passive_income", "financial_investments")
CANDIDATE_LIMIT = 200


def _portfolio_account_ids(position: PortfolioPosition) -> set[int]:
    """Accounts whose movements the ledger flows already attribute to the portfolio."""
    user = position.portfolio.user
    ids = set(
        PortfolioPosition.objects.filter(
            portfolio__user=user, ledger_account__isnull=False
        ).values_list("ledger_account_id", flat=True)
    )
    ids.update(
        ContainerCashAccount.objects.filter(container__portfolio__user=user).values_list(
            "ledger_account_id", flat=True
        )
    )
    return {int(account_id) for account_id in ids if account_id is not None}


def _serialize(transaction: LedgerTransaction, trade: PortfolioTrade | None = None) -> dict:
    entries = list(transaction.entries.all())
    income = next(
        (
            entry
            for entry in entries
            if entry.account.account_type == LedgerAccount.AccountType.INCOME
        ),
        None,
    )
    received = next(
        (
            entry
            for entry in entries
            if entry.account.account_type == LedgerAccount.AccountType.ASSET
            and entry.side == LedgerEntry.Side.DEBIT
        ),
        None,
    )
    return {
        "transaction_id": transaction.id,
        "booking_date": transaction.booking_date.isoformat(),
        "description": transaction.description,
        "amount": str(income.amount if income else Decimal("0")),
        "currency": income.currency if income else "",
        "account_name": received.account.name if received else "",
        "category_key": income.category_key if income else "",
        "subcategory_key": income.subcategory_key if income else "",
        "trade_id": trade.id if trade else None,
        "operation_type": trade.operation_type if trade else None,
    }


def income_links(*, position: PortfolioPosition, include_all: bool = False) -> dict[str, Any]:
    """Income already linked to the position, and income that could be."""
    linked = (
        PortfolioTrade.objects.filter(
            position=position,
            operation_type__in=LINKABLE_OPERATION_TYPES,
        )
        .select_related("ledger_transaction")
        .prefetch_related("ledger_transaction__entries__account")
        .order_by("-ledger_transaction__booking_date", "-id")
    )
    candidates = (
        LedgerTransaction.objects.filter(
            user=position.portfolio.user,
            status=cast(str, LedgerTransaction.Status.POSTED),
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INCOME,
            portfolio_trade__isnull=True,
            booking_date__gte=position.opened_on,
        )
        .exclude(entries__account_id__in=_portfolio_account_ids(position))
        .prefetch_related("entries__account")
        .order_by("-booking_date", "-id")
    )
    if not include_all:
        candidates = candidates.filter(entries__category_key__in=SUGGESTED_CATEGORY_KEYS)
    candidates = candidates.distinct()
    return {
        "linked": [_serialize(trade.ledger_transaction, trade) for trade in linked],
        "candidates": [_serialize(row) for row in candidates[:CANDIDATE_LIMIT]],
    }


def _fingerprint(transaction_id: int) -> str:
    return hashlib.sha256(f"income-link:{transaction_id}".encode()).hexdigest()


def link_income(
    *, position: PortfolioPosition, transaction_ids: list[Any], operation_type: str
) -> list[PortfolioTrade]:
    if operation_type not in LINKABLE_OPERATION_TYPES:
        raise ValidationError({"operation_type": "Usa dividend o interest."})
    try:
        ids = sorted({int(raw) for raw in transaction_ids})
    except (TypeError, ValueError) as exc:
        raise ValidationError({"transaction_ids": "Identificadores no válidos."}) from exc
    if not ids:
        raise ValidationError({"transaction_ids": "Selecciona al menos un ingreso."})
    portfolio_accounts = _portfolio_account_ids(position)
    transactions = list(
        LedgerTransaction.objects.filter(
            id__in=ids,
            user=position.portfolio.user,
            status=cast(str, LedgerTransaction.Status.POSTED),
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INCOME,
        ).prefetch_related("entries__account")
    )
    if len(transactions) != len(ids):
        raise ValidationError({"transaction_ids": "Algún movimiento no es un ingreso tuyo."})
    created: list[PortfolioTrade] = []
    with db_transaction.atomic():
        for transaction in transactions:
            entries = list(transaction.entries.all())
            if any(entry.account_id in portfolio_accounts for entry in entries):
                raise ValidationError(
                    {"transaction_ids": f"«{transaction.description}» ya cuenta en la cartera."}
                )
            if PortfolioTrade.objects.filter(ledger_transaction=transaction).exists():
                raise ValidationError(
                    {"transaction_ids": f"«{transaction.description}» ya está vinculado."}
                )
            income = next(
                (
                    entry
                    for entry in entries
                    if entry.account.account_type == LedgerAccount.AccountType.INCOME
                ),
                None,
            )
            if income is None:
                raise ValidationError(
                    {"transaction_ids": f"«{transaction.description}» no tiene cuenta de ingreso."}
                )
            created.append(
                PortfolioTrade.objects.create(
                    portfolio=position.portfolio,
                    position=position,
                    ledger_transaction=transaction,
                    operation_type=operation_type,
                    trade_currency=income.currency,
                    gross_amount=income.amount,
                    source=PortfolioTrade.Source.MANUAL,
                    fingerprint=_fingerprint(transaction.id),
                    note="Ingreso contable vinculado a la posición.",
                )
            )
    return created


def unlink_income(*, position: PortfolioPosition, transaction_id: Any) -> None:
    """Drop the link only; the ledger movement it pointed at stays untouched."""
    deleted, _ = PortfolioTrade.objects.filter(
        position=position,
        operation_type__in=LINKABLE_OPERATION_TYPES,
        ledger_transaction_id=transaction_id,
    ).delete()
    if not deleted:
        raise ValidationError({"transaction_id": "Ese ingreso no está vinculado."})
