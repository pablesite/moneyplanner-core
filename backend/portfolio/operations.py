from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Any

from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounting.models import LedgerAccount, LedgerTransaction
from accounting.services_ledger import get_account_balance
from accounting.services_quick_entry import create_quick_transaction

from .models import (
    ContainerCashAccount,
    Portfolio,
    PortfolioCorporateAction,
    PortfolioPosition,
    PortfolioTrade,
    PositionValuation,
)

PREVIEW_SALT = "portfolio.operation.preview.v1"
OPERATION_TYPES = {
    "transfer",
    "buy",
    "sell",
    "dividend",
    "interest",
    "fee",
    "valuation",
    "split",
    "identifier_change",
    "position_transfer",
    "adjustment",
}


def _decimal(value: Any, field: str, *, required: bool = False) -> Decimal | None:
    if value in (None, ""):
        if required:
            raise ValidationError({field: "Este campo es obligatorio."})
        return None
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValidationError({field: "Usa un número válido."}) from exc
    return result


def _canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat()
        if isinstance(value, date)
        else str(value)
        if isinstance(value, Decimal)
        else value
        for key, value in sorted(payload.items())
        if key != "preview_token" and value not in (None, "")
    }


def operation_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(_canonical_payload(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _position(portfolio: Portfolio, raw_id: Any, field: str = "position_id") -> PortfolioPosition:
    try:
        return portfolio.positions.select_related(
            "instrument", "container", "ledger_account", "asset"
        ).get(id=int(raw_id))
    except (TypeError, ValueError, PortfolioPosition.DoesNotExist) as exc:
        raise ValidationError({field: "La posición no pertenece a la cartera."}) from exc


def _cash_link(portfolio: Portfolio, raw_id: Any, field: str) -> ContainerCashAccount:
    try:
        return ContainerCashAccount.objects.select_related("ledger_account", "container").get(
            id=int(raw_id), container__portfolio=portfolio
        )
    except (TypeError, ValueError, ContainerCashAccount.DoesNotExist) as exc:
        raise ValidationError({field: "La cuenta de efectivo no pertenece a la cartera."}) from exc


def _system_account(*, portfolio: Portfolio, account_type: str, currency: str, name: str):
    account, _ = LedgerAccount.objects.get_or_create(
        user=portfolio.user,
        account_type=account_type,
        currency=currency,
        origin=LedgerAccount.Origin.SYSTEM,
        name=name,
        defaults={"is_active": True},
    )
    return account


def _validate_payload(  # noqa: C901
    *, portfolio: Portfolio, payload: dict[str, Any]
) -> dict[str, Any]:
    operation_type = str(payload.get("operation_type") or "").strip()
    if operation_type not in OPERATION_TYPES:
        raise ValidationError({"operation_type": "Tipo de operación no válido."})
    booking_date = payload.get("booking_date") or timezone.localdate()
    if isinstance(booking_date, str):
        try:
            booking_date = date.fromisoformat(booking_date)
        except ValueError as exc:
            raise ValidationError({"booking_date": "Usa una fecha YYYY-MM-DD."}) from exc

    normalized = {**payload, "operation_type": operation_type, "booking_date": booking_date}
    if operation_type == "transfer":
        source = _cash_link(portfolio, payload.get("cash_account_id"), "cash_account_id")
        target = _cash_link(
            portfolio, payload.get("target_cash_account_id"), "target_cash_account_id"
        )
        if source.id == target.id:
            raise ValidationError({"target_cash_account_id": "Selecciona otra cuenta."})
        amount = _decimal(payload.get("amount"), "amount", required=True)
        if amount is None or amount <= 0:
            raise ValidationError({"amount": "Debe ser mayor que cero."})
        normalized.update(source_cash=source, target_cash=target, amount=amount)
        return normalized

    position = _position(portfolio, payload.get("position_id"))
    normalized["position"] = position
    if operation_type == "identifier_change":
        identifier = str(payload.get("new_identifier") or "").strip().upper()
        if not identifier:
            raise ValidationError({"new_identifier": "Indica el nuevo identificador."})
        normalized["new_identifier"] = identifier
        return normalized
    if operation_type == "valuation":
        value = _decimal(payload.get("amount"), "amount", required=True)
        if value is None or value < 0:
            raise ValidationError({"amount": "La valoración no puede ser negativa."})
        normalized.update(
            amount=value,
            currency=str(payload.get("currency") or position.instrument.quote_currency).upper(),
        )
        return normalized
    if operation_type in {"buy", "sell", "dividend", "interest", "fee"}:
        cash = _cash_link(portfolio, payload.get("cash_account_id"), "cash_account_id")
        if cash.container_id != position.container_id:
            raise ValidationError({"cash_account_id": "La cuenta debe pertenecer al contenedor."})
        amount = _decimal(payload.get("amount"), "amount", required=True)
        if amount is None or amount <= 0:
            raise ValidationError({"amount": "Debe ser mayor que cero."})
        units = _decimal(payload.get("units"), "units")
        price = _decimal(payload.get("unit_price"), "unit_price")
        fee = _decimal(payload.get("fee"), "fee") or Decimal("0")
        if units is not None and units <= 0:
            raise ValidationError({"units": "Debe ser mayor que cero."})
        if fee < 0:
            raise ValidationError({"fee": "No puede ser negativa."})
        if (
            operation_type == "buy"
            and get_account_balance(account=cash.ledger_account, status="posted") < amount + fee
        ):
            raise ValidationError({"amount": "El efectivo disponible no cubre compra y comisión."})
        if position.ledger_account_id is None and operation_type in {"buy", "sell"}:
            raise ValidationError({"position_id": "La posición no tiene cuenta contable enlazada."})
        normalized.update(cash=cash, amount=amount, units=units, unit_price=price, fee=fee)
        return normalized

    if position.ledger_account_id is None:
        raise ValidationError({"position_id": "La posición no tiene cuenta contable enlazada."})
    if operation_type == "position_transfer":
        target = _position(portfolio, payload.get("target_position_id"), "target_position_id")
        if target.id == position.id or target.ledger_account_id is None:
            raise ValidationError({"target_position_id": "Selecciona otra posición operativa."})
        normalized["target_position"] = target
    amount = _decimal(payload.get("amount"), "amount", required=True)
    if amount is None or amount == 0:
        raise ValidationError({"amount": "Debe ser distinto de cero."})
    normalized["amount"] = amount
    if operation_type == "split":
        denominator = _decimal(payload.get("ratio_denominator"), "ratio_denominator", required=True)
        if denominator is None or denominator <= 0 or amount <= 0:
            raise ValidationError({"ratio_denominator": "La proporción debe ser positiva."})
        normalized["ratio_denominator"] = denominator
    return normalized


def preview_operation(*, portfolio: Portfolio, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _validate_payload(portfolio=portfolio, payload=payload)
    canonical = _canonical_payload(payload)
    canonical.setdefault("booking_date", normalized["booking_date"].isoformat())
    preview = {
        "operation_type": normalized["operation_type"],
        "position": (
            {"id": normalized["position"].id, "name": normalized["position"].instrument.name}
            if normalized.get("position")
            else None
        ),
        "amount": str(normalized.get("amount", "")),
        "fee": str(normalized.get("fee", "0")),
        "booking_date": normalized["booking_date"].isoformat(),
    }
    cash = normalized.get("cash") or normalized.get("source_cash")
    if cash:
        balance = get_account_balance(account=cash.ledger_account, status="posted")
        preview["cash"] = {
            "id": cash.id,
            "name": cash.ledger_account.name,
            "currency": cash.currency,
            "available_before": str(balance),
        }
    return {"preview": preview, "preview_token": signing.dumps(canonical, salt=PREVIEW_SALT)}


def _assert_preview_token(payload: dict[str, Any]) -> None:
    token = str(payload.get("preview_token") or "")
    if not token:
        raise ValidationError({"preview_token": "Previsualiza antes de confirmar."})
    try:
        previewed = signing.loads(token, salt=PREVIEW_SALT, max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError({"preview_token": "La previsualización ha caducado."}) from exc
    canonical = _canonical_payload(payload)
    canonical.setdefault("booking_date", timezone.localdate().isoformat())
    if previewed != canonical:
        raise ValidationError({"preview_token": "Los datos cambiaron; vuelve a previsualizar."})


@transaction.atomic
def confirm_operation(
    *, portfolio: Portfolio, payload: dict[str, Any], require_preview: bool = True
) -> dict[str, Any]:
    if require_preview:
        _assert_preview_token(payload)
    data = _validate_payload(portfolio=portfolio, payload=payload)
    kind = data["operation_type"]
    origin = (
        LedgerTransaction.Origin.IMPORT
        if payload.get("source") == PortfolioTrade.Source.CSV
        else LedgerTransaction.Origin.MANUAL
    )
    note = str(payload.get("note") or "")
    fingerprint = operation_fingerprint(payload)
    if PortfolioTrade.objects.filter(portfolio=portfolio, fingerprint=fingerprint).exists():
        raise ValidationError({"detail": "Esta operación ya está registrada."})

    if kind == "valuation":
        valuation, created = PositionValuation.objects.update_or_create(
            position=data["position"],
            valuation_date=data["booking_date"],
            source=PositionValuation.Source.MANUAL,
            defaults={"value": data["amount"], "currency": data["currency"], "note": note},
        )
        return {"kind": kind, "valuation_id": valuation.id, "created": created}
    if kind == "identifier_change":
        instrument = data["position"].instrument
        previous = instrument.isin or instrument.ticker
        if len(data["new_identifier"]) == 12:
            instrument.isin = data["new_identifier"]
        else:
            instrument.ticker = data["new_identifier"]
        instrument.save(update_fields=["isin", "ticker", "updated_at"])
        action = PortfolioCorporateAction.objects.create(
            portfolio=portfolio,
            position=data["position"],
            action_type=kind,
            effective_date=data["booking_date"],
            payload={"previous_identifier": previous, "new_identifier": data["new_identifier"]},
            note=note,
        )
        return {"kind": kind, "corporate_action_id": action.id}
    if kind == "transfer":
        tx = create_quick_transaction(
            user=portfolio.user,
            movement_type="transfer",
            booking_date=data["booking_date"],
            value_date=data["booking_date"],
            description=str(payload.get("description") or "Transferencia de cartera"),
            amount=data["amount"],
            account=data["source_cash"].ledger_account,
            counterparty_account=data["target_cash"].ledger_account,
            status=LedgerTransaction.Status.POSTED,
            origin=origin,
            notes=note,
            destination_amount=_decimal(payload.get("destination_amount"), "destination_amount"),
        )
        return {"kind": kind, "ledger_transaction_id": tx.id}

    position = data["position"]
    if kind in {"buy", "sell", "dividend", "interest", "fee"}:
        cash_account = data["cash"].ledger_account
        fee_tx = None
        if kind in {"buy", "sell"}:
            direction = (
                LedgerTransaction.InvestmentDirection.INFLOW
                if kind == "buy"
                else LedgerTransaction.InvestmentDirection.OUTFLOW
            )
            tx = create_quick_transaction(
                user=portfolio.user,
                movement_type="investment",
                investment_direction=direction,
                booking_date=data["booking_date"],
                value_date=data["booking_date"],
                description=str(
                    payload.get("description") or ("Compra" if kind == "buy" else "Venta")
                ),
                amount=data["amount"],
                destination_amount=data["units"] or data["amount"],
                account=cash_account,
                counterparty_account=position.ledger_account,
                status=LedgerTransaction.Status.POSTED,
                origin=origin,
                notes=note,
                import_source="portfolio_csv" if origin == LedgerTransaction.Origin.IMPORT else "",
                import_fingerprint=fingerprint if origin == LedgerTransaction.Origin.IMPORT else "",
                realized_cost_basis=_decimal(
                    payload.get("realized_cost_basis"), "realized_cost_basis"
                ),
                realized_gain_loss=_decimal(
                    payload.get("realized_gain_loss"), "realized_gain_loss"
                ),
            )
        else:
            account_type = "income" if kind in {"dividend", "interest"} else "expense"
            counterpart = _system_account(
                portfolio=portfolio,
                account_type=account_type,
                currency=cash_account.currency,
                name="Ingresos de inversiones"
                if account_type == "income"
                else "Comisiones de inversión",
            )
            tx = create_quick_transaction(
                user=portfolio.user,
                movement_type="income" if account_type == "income" else "expense",
                booking_date=data["booking_date"],
                value_date=data["booking_date"],
                description=str(payload.get("description") or kind.title()),
                amount=data["amount"],
                account=cash_account,
                counterparty_account=counterpart,
                status=LedgerTransaction.Status.POSTED,
                origin=origin,
                notes=note,
                flow_family="income"
                if account_type == LedgerAccount.AccountType.INCOME
                else "expense",
                category_key="financial_investments",
                subcategory_key="investment_income"
                if account_type == LedgerAccount.AccountType.INCOME
                else "investment_fees",
            )
        if data["fee"] > 0 and kind in {"buy", "sell"}:
            fee_account = _system_account(
                portfolio=portfolio,
                account_type="expense",
                currency=cash_account.currency,
                name="Comisiones de inversión",
            )
            fee_tx = create_quick_transaction(
                user=portfolio.user,
                movement_type="expense",
                booking_date=data["booking_date"],
                value_date=data["booking_date"],
                description=f"Comisión · {position.instrument.name}",
                amount=data["fee"],
                account=cash_account,
                counterparty_account=fee_account,
                status=LedgerTransaction.Status.POSTED,
                origin=origin,
                flow_family="expense",
                category_key="financial_investments",
                subcategory_key="investment_fees",
            )
        trade = PortfolioTrade.objects.create(
            portfolio=portfolio,
            position=position,
            ledger_transaction=tx,
            fee_transaction=fee_tx,
            operation_type=kind,
            units=data["units"],
            unit_price=data["unit_price"],
            trade_currency=str(payload.get("currency") or data["cash"].currency).upper(),
            gross_amount=data["amount"],
            fee=data["fee"],
            external_id=str(payload.get("external_id") or ""),
            source=str(payload.get("source") or PortfolioTrade.Source.MANUAL),
            fingerprint=fingerprint,
            note=note,
        )
        return {"kind": kind, "trade_id": trade.id, "ledger_transaction_id": tx.id}

    if kind == "position_transfer":
        target = data["target_position"]
        tx = create_quick_transaction(
            user=portfolio.user,
            movement_type="transfer",
            booking_date=data["booking_date"],
            value_date=data["booking_date"],
            description=str(payload.get("description") or "Traspaso entre posiciones"),
            amount=abs(data["amount"]),
            account=position.ledger_account,
            counterparty_account=target.ledger_account,
            destination_amount=_decimal(payload.get("destination_amount"), "destination_amount"),
            status=LedgerTransaction.Status.POSTED,
            origin=origin,
            notes=note,
        )
    else:
        equity = _system_account(
            portfolio=portfolio,
            account_type="equity",
            currency=position.ledger_account.currency,
            name="Ajustes de cartera",
        )
        delta = data["amount"]
        if kind == "split":
            current = get_account_balance(account=position.ledger_account, status="posted")
            delta = current * (data["amount"] / data["ratio_denominator"] - Decimal("1"))
        tx = create_quick_transaction(
            user=portfolio.user,
            movement_type="adjustment",
            booking_date=data["booking_date"],
            value_date=data["booking_date"],
            description=str(payload.get("description") or "Ajuste de cartera"),
            amount=delta,
            account=position.ledger_account,
            counterparty_account=equity,
            status=LedgerTransaction.Status.POSTED,
            origin=origin,
            notes=note,
        )
    action = PortfolioCorporateAction.objects.create(
        portfolio=portfolio,
        position=position,
        ledger_transaction=tx,
        action_type=kind,
        effective_date=data["booking_date"],
        payload=_canonical_payload(payload),
        note=note,
    )
    return {"kind": kind, "corporate_action_id": action.id, "ledger_transaction_id": tx.id}


def operation_options(*, portfolio: Portfolio) -> dict[str, Any]:
    from .services import position_coverage

    positions = list(
        portfolio.positions.select_related("instrument", "container", "ledger_account").order_by(
            "instrument__name"
        )
    )
    cash_links = list(
        ContainerCashAccount.objects.filter(container__portfolio=portfolio).select_related(
            "container", "ledger_account"
        )
    )
    return {
        "positions": [
            {
                "id": row.id,
                "name": row.instrument.name,
                "container_id": row.container_id,
                "container_name": row.container.name,
                "tracking_style": row.tracking_style,
                "status": row.status,
                "operational": row.ledger_account_id is not None,
                "history_mode": row.history_mode,
                "history_start_date": (
                    row.history_start_date.isoformat() if row.history_start_date else None
                ),
                "setup_confirmed": row.setup_confirmed_at is not None,
                **position_coverage(row),
            }
            for row in positions
        ],
        "cash_accounts": [
            {
                "id": row.id,
                "container_id": row.container_id,
                "name": row.ledger_account.name,
                "currency": row.currency,
                "available": str(get_account_balance(account=row.ledger_account, status="posted")),
            }
            for row in cash_links
        ],
    }
