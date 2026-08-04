from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import cast

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounting.services_ledger import get_account_balance
from accounting.services_quick_entry import create_quick_transaction

from .models import (
    MonthlyClose,
    SettlementAccount,
    SettlementSnapshot,
    SettlementTransferRecommendation,
)

ZERO = Decimal("0")
MONEY_STEP = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_STEP)


def _money_string(value: Decimal) -> str:
    return str(_money(value))


def _recommendation_queryset(*, user):
    return SettlementTransferRecommendation.objects.select_related(
        "snapshot",
        "snapshot__monthly_close",
        "from_account__asset",
        "to_account__asset",
        "ownership",
        "member",
    ).filter(snapshot__monthly_close__user=user)


def _locked_recommendation(*, user, close_id: int, recommendation_id: int):
    try:
        return (
            _recommendation_queryset(user=user)
            .select_for_update(of=("self",))
            .get(id=recommendation_id, snapshot__monthly_close_id=close_id)
        )
    except SettlementTransferRecommendation.DoesNotExist as exc:
        raise ValidationError({"recommendation_id": "La recomendación no existe."}) from exc


def _validate_execution_state(recommendation: SettlementTransferRecommendation) -> None:
    close = recommendation.snapshot.monthly_close
    if close.status == MonthlyClose.Status.LOCKED:
        raise ValidationError({"monthly_close": "Un cierre bloqueado no admite ejecuciones."})
    if close.status != MonthlyClose.Status.FINALIZED:
        raise ValidationError(
            {"monthly_close": "Finaliza el cierre antes de aplicar transferencias."}
        )
    if recommendation.snapshot.status != SettlementSnapshot.Status.READY:
        raise ValidationError({"settlement": "La liquidación finalizada no estaba lista."})
    if not recommendation.snapshot.is_frozen:
        raise ValidationError(
            {"settlement": "La recomendación ya no pertenece a un snapshot vigente."}
        )
    if recommendation.status == SettlementTransferRecommendation.Status.CANCELLED:
        raise ValidationError({"recommendation": "La recomendación está cancelada."})


def _ledger_account(*, account: SettlementAccount, user) -> LedgerAccount:
    ledger_id = account.asset.accounting_account_id
    ledger = LedgerAccount.objects.filter(id=ledger_id, user=user, is_active=True).first()
    if ledger is None:
        raise ValidationError({"account": f"{account.asset.name} no tiene una cuenta activa."})
    if ledger.account_type != LedgerAccount.AccountType.ASSET:
        raise ValidationError({"account": f"{account.asset.name} no es una cuenta de activo."})
    if ledger.currency.upper() != account.currency.upper():
        raise ValidationError({"account": f"La moneda de {account.asset.name} no coincide."})
    return ledger


def _remaining(recommendation: SettlementTransferRecommendation) -> Decimal:
    return _money(Decimal(recommendation.amount) - Decimal(recommendation.applied_amount))


def _set_execution_status(recommendation: SettlementTransferRecommendation) -> None:
    applied = _money(Decimal(recommendation.applied_amount))
    total = _money(Decimal(recommendation.amount))
    if applied >= total:
        recommendation.status = SettlementTransferRecommendation.Status.APPLIED
    elif applied > ZERO:
        recommendation.status = SettlementTransferRecommendation.Status.PARTIALLY_APPLIED
    elif recommendation.accepted_at is not None:
        recommendation.status = SettlementTransferRecommendation.Status.ACCEPTED
    else:
        recommendation.status = SettlementTransferRecommendation.Status.RECOMMENDED


def serialize_recommendation(recommendation: SettlementTransferRecommendation) -> dict:
    transactions = [
        {
            "id": row.id,
            "booking_date": row.booking_date.isoformat(),
            "origin": row.origin,
            "action": row.settlement_action,
            "amount": _money_string(Decimal(row.settlement_amount or ZERO)),
            "idempotency_key": row.settlement_idempotency_key,
        }
        for row in recommendation.ledger_transactions.order_by("booking_date", "id")
    ]
    account_reconciliation = None
    try:
        source = _ledger_account(
            account=recommendation.from_account,
            user=recommendation.snapshot.monthly_close.user,
        )
        destination = _ledger_account(
            account=recommendation.to_account,
            user=recommendation.snapshot.monthly_close.user,
        )
        account_reconciliation = {
            "source_balance": _money_string(
                get_account_balance(
                    account=source, status=cast(str, LedgerTransaction.Status.POSTED)
                )
            ),
            "destination_balance": _money_string(
                get_account_balance(
                    account=destination, status=cast(str, LedgerTransaction.Status.POSTED)
                )
            ),
            "target_reached": _remaining(recommendation) == ZERO,
        }
    except ValidationError:
        pass
    return {
        "id": recommendation.id,
        "from_account_id": recommendation.from_account_id,
        "to_account_id": recommendation.to_account_id,
        "member_id": recommendation.member_id,
        "ownership_id": recommendation.ownership_id,
        "reason": recommendation.reason,
        "status": recommendation.status,
        "amount": _money_string(Decimal(recommendation.amount)),
        "applied_amount": _money_string(Decimal(recommendation.applied_amount)),
        "remaining_amount": _money_string(_remaining(recommendation)),
        "currency": recommendation.currency,
        "accepted_at": (
            recommendation.accepted_at.isoformat() if recommendation.accepted_at else None
        ),
        "cancelled_at": (
            recommendation.cancelled_at.isoformat() if recommendation.cancelled_at else None
        ),
        "transactions": transactions,
        "account_reconciliation": account_reconciliation,
    }


@transaction.atomic
def accept_settlement_recommendation(*, user, close_id: int, recommendation_id: int) -> dict:
    recommendation = _locked_recommendation(
        user=user, close_id=close_id, recommendation_id=recommendation_id
    )
    _validate_execution_state(recommendation)
    if recommendation.accepted_at is None:
        recommendation.accepted_at = timezone.now()
    _set_execution_status(recommendation)
    recommendation.save(update_fields=["accepted_at", "status"])
    return serialize_recommendation(recommendation)


def _validate_amount(*, requested: Decimal, available: Decimal) -> Decimal:
    amount = _money(Decimal(requested))
    if amount <= ZERO:
        raise ValidationError({"amount": "El importe debe ser mayor que cero."})
    if amount > available:
        raise ValidationError({"amount": "El importe supera el remanente de la recomendación."})
    return amount


def _idempotency_key(
    *, recommendation: SettlementTransferRecommendation, value: str, partial: bool
) -> str:
    key = value.strip()
    if not key and partial:
        raise ValidationError(
            {"idempotency_key": "Las aplicaciones parciales requieren una clave."}
        )
    if not key:
        key = f"settlement:{recommendation.snapshot_id}:{recommendation.id}:full"
    if len(key) > 128:
        raise ValidationError({"idempotency_key": "La clave no puede superar 128 caracteres."})
    return key


@transaction.atomic
def apply_settlement_recommendation(
    *,
    user,
    close_id: int,
    recommendation_id: int,
    execution_date: date,
    amount: Decimal | None = None,
    idempotency_key: str = "",
) -> dict:
    recommendation = _locked_recommendation(
        user=user, close_id=close_id, recommendation_id=recommendation_id
    )
    _validate_execution_state(recommendation)
    provisional_key = idempotency_key.strip()
    if not provisional_key and amount is None:
        provisional_key = f"settlement:{recommendation.snapshot_id}:{recommendation.id}:full"
    if provisional_key:
        existing = LedgerTransaction.objects.filter(
            user=user, settlement_idempotency_key=provisional_key
        ).first()
        if existing is not None:
            if existing.settlement_recommendation_id != recommendation.id:
                raise ValidationError(
                    {"idempotency_key": "La clave ya pertenece a otra operación."}
                )
            return serialize_recommendation(recommendation)
    available = _remaining(recommendation)
    requested = available if amount is None else Decimal(amount)
    applied_amount = _validate_amount(requested=requested, available=available)
    key = _idempotency_key(
        recommendation=recommendation,
        value=idempotency_key,
        partial=applied_amount < available,
    )
    existing = LedgerTransaction.objects.filter(user=user, settlement_idempotency_key=key).first()
    if existing is not None:
        if existing.settlement_recommendation_id != recommendation.id:
            raise ValidationError({"idempotency_key": "La clave ya pertenece a otra operación."})
        recommendation.refresh_from_db()
        return serialize_recommendation(recommendation)

    source = _ledger_account(account=recommendation.from_account, user=user)
    destination = _ledger_account(account=recommendation.to_account, user=user)
    try:
        ledger_transaction = create_quick_transaction(
            user=user,
            movement_type=LedgerTransaction.QuickEntryKind.TRANSFER,
            booking_date=execution_date,
            value_date=execution_date,
            description=(
                f"Liquidación cierre {recommendation.snapshot.monthly_close.fiscal_year}-"
                f"{recommendation.snapshot.monthly_close.month:02d}: "
                f"{recommendation.from_account.asset.name} → {recommendation.to_account.asset.name}"
            ),
            amount=applied_amount,
            account=source,
            counterparty_account=destination,
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.SYSTEM,
            ownership=recommendation.ownership,
            notes=f"Settlement recommendation #{recommendation.id}",
        )
        ledger_transaction.settlement_recommendation = recommendation
        ledger_transaction.settlement_idempotency_key = key
        ledger_transaction.settlement_action = LedgerTransaction.SettlementAction.APPLICATION
        ledger_transaction.settlement_amount = applied_amount
        ledger_transaction.save(
            update_fields=[
                "settlement_recommendation",
                "settlement_idempotency_key",
                "settlement_action",
                "settlement_amount",
                "updated_at",
            ]
        )
    except IntegrityError:
        existing = LedgerTransaction.objects.filter(
            user=user, settlement_idempotency_key=key
        ).first()
        if existing is None or existing.settlement_recommendation_id != recommendation.id:
            raise
        recommendation.refresh_from_db()
        return serialize_recommendation(recommendation)

    recommendation.applied_amount = _money(Decimal(recommendation.applied_amount) + applied_amount)
    if recommendation.accepted_at is None:
        recommendation.accepted_at = timezone.now()
    _set_execution_status(recommendation)
    recommendation.save(update_fields=["applied_amount", "accepted_at", "status"])
    return serialize_recommendation(recommendation)


def _matching_transfer_amount(
    *, transaction_row: LedgerTransaction, source: LedgerAccount, destination: LedgerAccount
) -> Decimal | None:
    source_amount = ZERO
    destination_amount = ZERO
    for entry in transaction_row.entries.all():
        if entry.currency.upper() != source.currency.upper():
            continue
        if entry.account_id == source.id and entry.side == LedgerEntry.Side.CREDIT:
            source_amount += Decimal(entry.amount)
        if entry.account_id == destination.id and entry.side == LedgerEntry.Side.DEBIT:
            destination_amount += Decimal(entry.amount)
    if source_amount <= ZERO or _money(source_amount) != _money(destination_amount):
        return None
    return _money(source_amount)


def settlement_reconciliation_candidates(
    *, user, close_id: int, recommendation_id: int
) -> list[dict]:
    try:
        recommendation = _recommendation_queryset(user=user).get(
            id=recommendation_id, snapshot__monthly_close_id=close_id
        )
    except SettlementTransferRecommendation.DoesNotExist as exc:
        raise ValidationError({"recommendation_id": "La recomendación no existe."}) from exc
    _validate_execution_state(recommendation)
    source = _ledger_account(account=recommendation.from_account, user=user)
    destination = _ledger_account(account=recommendation.to_account, user=user)
    period_end = recommendation.snapshot.period_end
    target_end = date(
        recommendation.snapshot.target_year,
        recommendation.snapshot.target_month,
        monthrange(recommendation.snapshot.target_year, recommendation.snapshot.target_month)[1],
    )
    candidates = (
        LedgerTransaction.objects.filter(
            user=user,
            status=LedgerTransaction.Status.POSTED,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
            booking_date__gte=period_end - timedelta(days=7),
            booking_date__lte=target_end,
            settlement_recommendation__isnull=True,
            entries__account_id=source.id,
        )
        .filter(entries__account_id=destination.id)
        .prefetch_related("entries")
        .distinct()
        .order_by("booking_date", "id")
    )
    rows = []
    remaining = _remaining(recommendation)
    for transaction_row in candidates:
        matched_amount = _matching_transfer_amount(
            transaction_row=transaction_row, source=source, destination=destination
        )
        if matched_amount is None or matched_amount > remaining:
            continue
        if transaction_row.ownership_id != recommendation.ownership_id:
            continue
        rows.append(
            {
                "transaction_id": transaction_row.id,
                "booking_date": transaction_row.booking_date.isoformat(),
                "description": transaction_row.description,
                "origin": transaction_row.origin,
                "amount": _money_string(matched_amount),
                "currency": recommendation.currency,
            }
        )
    return rows


@transaction.atomic
def reconcile_settlement_recommendation(
    *, user, close_id: int, recommendation_id: int, transaction_id: int
) -> dict:
    recommendation = _locked_recommendation(
        user=user, close_id=close_id, recommendation_id=recommendation_id
    )
    _validate_execution_state(recommendation)
    candidates = settlement_reconciliation_candidates(
        user=user, close_id=close_id, recommendation_id=recommendation_id
    )
    candidate = next((row for row in candidates if row["transaction_id"] == transaction_id), None)
    if candidate is None:
        raise ValidationError({"transaction_id": "La transferencia no es compatible."})
    transaction_row = LedgerTransaction.objects.select_for_update().get(
        id=transaction_id, user=user
    )
    transaction_row.settlement_recommendation = recommendation
    transaction_row.settlement_idempotency_key = (
        f"settlement:{recommendation.snapshot_id}:{recommendation.id}:reconcile:{transaction_id}"
    )
    transaction_row.settlement_action = LedgerTransaction.SettlementAction.RECONCILIATION
    transaction_row.settlement_amount = Decimal(candidate["amount"])
    transaction_row.save(
        update_fields=[
            "settlement_recommendation",
            "settlement_idempotency_key",
            "settlement_action",
            "settlement_amount",
            "updated_at",
        ]
    )
    recommendation.applied_amount = _money(
        Decimal(recommendation.applied_amount) + Decimal(candidate["amount"])
    )
    if recommendation.accepted_at is None:
        recommendation.accepted_at = timezone.now()
    _set_execution_status(recommendation)
    recommendation.save(update_fields=["applied_amount", "accepted_at", "status"])
    return serialize_recommendation(recommendation)


@transaction.atomic
def cancel_settlement_recommendation(*, user, close_id: int, recommendation_id: int) -> dict:
    recommendation = _locked_recommendation(
        user=user, close_id=close_id, recommendation_id=recommendation_id
    )
    _validate_execution_state(recommendation)
    if Decimal(recommendation.applied_amount) > ZERO:
        raise ValidationError({"recommendation": "Revierte primero el importe ya aplicado."})
    recommendation.status = SettlementTransferRecommendation.Status.CANCELLED
    recommendation.cancelled_at = timezone.now()
    recommendation.save(update_fields=["status", "cancelled_at"])
    return serialize_recommendation(recommendation)


@transaction.atomic
def reverse_settlement_recommendation(
    *,
    user,
    close_id: int,
    recommendation_id: int,
    execution_date: date,
    amount: Decimal | None = None,
    idempotency_key: str = "",
) -> dict:
    recommendation = _locked_recommendation(
        user=user, close_id=close_id, recommendation_id=recommendation_id
    )
    _validate_execution_state(recommendation)
    provisional_key = idempotency_key.strip()
    if not provisional_key and amount is None:
        provisional_key = (
            f"settlement:{recommendation.snapshot_id}:{recommendation.id}:reverse:full"
        )
    if provisional_key:
        if len(provisional_key) > 128:
            raise ValidationError({"idempotency_key": "La clave no puede superar 128 caracteres."})
        existing = LedgerTransaction.objects.filter(
            user=user, settlement_idempotency_key=provisional_key
        ).first()
        if existing is not None:
            if existing.settlement_recommendation_id != recommendation.id:
                raise ValidationError(
                    {"idempotency_key": "La clave ya pertenece a otra operación."}
                )
            return serialize_recommendation(recommendation)
    available = _money(Decimal(recommendation.applied_amount))
    requested = available if amount is None else Decimal(amount)
    reversed_amount = _validate_amount(requested=requested, available=available)
    key = idempotency_key.strip() or provisional_key
    if len(key) > 128:
        raise ValidationError({"idempotency_key": "La clave no puede superar 128 caracteres."})
    existing = LedgerTransaction.objects.filter(user=user, settlement_idempotency_key=key).first()
    if existing is not None:
        if existing.settlement_recommendation_id != recommendation.id:
            raise ValidationError({"idempotency_key": "La clave ya pertenece a otra operación."})
        return serialize_recommendation(recommendation)
    source = _ledger_account(account=recommendation.to_account, user=user)
    destination = _ledger_account(account=recommendation.from_account, user=user)
    ledger_transaction = create_quick_transaction(
        user=user,
        movement_type=LedgerTransaction.QuickEntryKind.TRANSFER,
        booking_date=execution_date,
        value_date=execution_date,
        description=f"Reverso de liquidación #{recommendation.id}",
        amount=reversed_amount,
        account=source,
        counterparty_account=destination,
        status=LedgerTransaction.Status.POSTED,
        origin=LedgerTransaction.Origin.SYSTEM,
        ownership=recommendation.ownership,
        notes=f"Settlement reversal recommendation #{recommendation.id}",
    )
    ledger_transaction.settlement_recommendation = recommendation
    ledger_transaction.settlement_idempotency_key = key
    ledger_transaction.settlement_action = LedgerTransaction.SettlementAction.REVERSAL
    ledger_transaction.settlement_amount = reversed_amount
    ledger_transaction.save(
        update_fields=[
            "settlement_recommendation",
            "settlement_idempotency_key",
            "settlement_action",
            "settlement_amount",
            "updated_at",
        ]
    )
    recommendation.applied_amount = _money(Decimal(recommendation.applied_amount) - reversed_amount)
    _set_execution_status(recommendation)
    recommendation.save(update_fields=["applied_amount", "status"])
    return serialize_recommendation(recommendation)


@transaction.atomic
def apply_all_settlement_recommendations(
    *, user, close_id: int, execution_date: date
) -> list[dict]:
    try:
        close = MonthlyClose.objects.select_for_update().get(id=close_id, user=user)
    except MonthlyClose.DoesNotExist as exc:
        raise ValidationError({"monthly_close": "El cierre no existe."}) from exc
    if close.status == MonthlyClose.Status.LOCKED:
        raise ValidationError({"monthly_close": "Un cierre bloqueado no admite ejecuciones."})
    if close.status != MonthlyClose.Status.FINALIZED:
        raise ValidationError(
            {"monthly_close": "Finaliza el cierre antes de aplicar transferencias."}
        )
    recommendation_ids = list(
        _recommendation_queryset(user=user)
        .filter(snapshot__monthly_close_id=close_id)
        .exclude(status=SettlementTransferRecommendation.Status.CANCELLED)
        .order_by("sort_order", "id")
        .values_list("id", flat=True)
    )
    rows = []
    for recommendation_id in recommendation_ids:
        recommendation = _recommendation_queryset(user=user).get(id=recommendation_id)
        if _remaining(recommendation) <= ZERO:
            rows.append(serialize_recommendation(recommendation))
            continue
        rows.append(
            apply_settlement_recommendation(
                user=user,
                close_id=close_id,
                recommendation_id=recommendation_id,
                execution_date=execution_date,
            )
        )
    return rows
