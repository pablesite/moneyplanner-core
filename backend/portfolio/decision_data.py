"""Perímetro monetario y evidencia necesaria antes de repartir dinero."""

from datetime import date
from decimal import Decimal
from typing import Any

from accounting.models import LedgerAccount
from accounting.services_ledger import get_account_balance
from memberships.models import Ownership, OwnershipLink

from .composition import class_compositions
from .models import PortfolioPosition
from .performance import (
    PerformanceContext,
    _balance_at,
    _position_value_base,
    _to_base,
    _value_status,
)

ZERO = Decimal("0")
CENT = Decimal("0.01")


def issue(
    code: str,
    message: str,
    action: str,
    *,
    position_id: int | None = None,
    observed_on: date | None = None,
    severity: str = "blocker",
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "action": action,
        "severity": severity,
        "position_id": position_id,
        "observed_on": observed_on.isoformat() if observed_on else None,
    }


def cash_snapshot(
    *, context: PerformanceContext, on_date: date, ownership: Ownership | None = None
) -> dict[str, Any]:
    links = {
        row.target_id: row.ownership_id
        for row in OwnershipLink.objects.filter(
            user=context.portfolio.user,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id__in=[
                row.ledger_account.asset_id
                for row in context.cash_accounts
                if row.ledger_account.asset_id
            ],
        )
    }
    rows = []
    issues = []
    total = ZERO
    position_accounts = {
        p.ledger_account_id
        for p in context.positions
        if p.status != PortfolioPosition.Status.ARCHIVED and p.ledger_account_id
    }
    for cash in context.cash_accounts:
        owner = links.get(cash.ledger_account.asset_id)
        balance = _balance_at(context, cash.ledger_account_id, on_date)
        if ownership and owner != ownership.id:
            if owner is None and balance:
                issues.append(
                    issue(
                        "cash_ownership",
                        f"{cash.ledger_account.name}: efectivo sin titularidad.",
                        "Asigna la titularidad de la cuenta en Patrimonio.",
                    )
                )
            continue
        if cash.ledger_account_id in position_accounts:
            issues.append(
                issue(
                    "duplicate_cash",
                    f"{cash.ledger_account.name}: cuenta vinculada también a una posición.",
                    "Corrige los enlaces en la configuración de cartera.",
                )
            )
            continue
        converted = (
            _to_base(context=context, amount=balance, currency=cash.currency, target=on_date)
            if balance
            else ZERO
        )
        if converted is None:
            issues.append(
                issue(
                    "cash_fx",
                    f"{cash.ledger_account.name}: falta cambio a moneda base.",
                    "Actualiza los tipos de cambio en Datos de mercado.",
                )
            )
        else:
            total += converted
            if converted < ZERO:
                issues.append(
                    issue(
                        "negative_cash",
                        f"{cash.ledger_account.name}: saldo negativo.",
                        "Revisa los movimientos de la cuenta.",
                    )
                )
        rows.append(
            {
                "cash_account_id": cash.id,
                "ledger_account_id": cash.ledger_account_id,
                "container_id": cash.container_id,
                "name": cash.ledger_account.name,
                "currency": cash.currency,
                "balance": str(balance),
                "value": str(converted) if converted is not None else None,
            }
        )
    return {
        "total": str(total.quantize(CENT)),
        "on_date": on_date.isoformat(),
        "accounts": rows,
        "issues": issues,
    }


def decision_quality(
    *,
    context: PerformanceContext,
    positions: list[PortfolioPosition],
    on_date: date,
    cash: dict[str, Any],
) -> dict[str, Any]:
    issues = list(cash["issues"])
    compositions = class_compositions(positions=positions, on_date=on_date)
    for position in context.positions:
        if position.status == PortfolioPosition.Status.ARCHIVED:
            continue
        if not any(
            p.start_date <= on_date and (p.end_date is None or p.end_date >= on_date)
            for p in context.ownership_periods.get(position.id, [])
        ):
            issues.append(
                issue(
                    "position_ownership",
                    f"{position.asset.name}: sin titularidad vigente.",
                    "Revisa la titularidad en la ficha de la posición.",
                    position_id=position.id,
                )
            )
    for position in positions:
        value, native = _position_value_base(
            context=context, position=position, target=on_date, member_id=None
        )
        observed = native.observed_on if native else None
        state = _value_status(position=position, native=native, target=on_date)
        if value is None:
            issues.append(
                issue(
                    "valuation_missing" if native is None else "valuation_fx",
                    f"{position.asset.name}: falta valoración o cambio a moneda base.",
                    "Registra una valoración y revisa los tipos de cambio en Datos de mercado.",
                    position_id=position.id,
                    observed_on=observed,
                )
            )
            continue
        if value == ZERO:
            continue
        if state in ("stale", "at_cost"):
            issues.append(
                issue(
                    "valuation_" + state,
                    f"{position.asset.name}: valoración caducada."
                    if state == "stale"
                    else f"{position.asset.name}: valor a coste, sin precio de mercado.",
                    "Actualiza la valoración en la ficha de la posición.",
                    position_id=position.id,
                    observed_on=observed,
                    severity="warning" if state == "at_cost" else "blocker",
                )
            )
        composition = compositions[position.id]
        if composition.covered_percent < Decimal("100"):
            issues.append(
                issue(
                    "class_coverage",
                    f"{position.asset.name}: clasificación incompleta.",
                    "Completa las clases o los subyacentes en la ficha de la posición.",
                    position_id=position.id,
                    observed_on=composition.observed_on,
                )
            )
        if composition.observed_on and (on_date - composition.observed_on).days > 90:
            issues.append(
                issue(
                    "holdings_stale",
                    f"{position.asset.name}: subyacentes de hace más de 90 días.",
                    "Actualiza la composición del fondo en su ficha.",
                    position_id=position.id,
                    observed_on=composition.observed_on,
                )
            )
    return {
        "status": "blocked"
        if any(row["severity"] == "blocker" for row in issues)
        else "review"
        if issues
        else "ready",
        "on_date": on_date.isoformat(),
        "issues": issues,
    }


def funding_source(
    *,
    context: PerformanceContext,
    cash: dict[str, Any],
    source_account_id: int | None,
    amount: Decimal,
    on_date: date,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    funding: dict[str, Any] = {
        "kind": "unspecified",
        "source_account_id": source_account_id,
        "name": None,
        "available": None,
        "on_date": on_date.isoformat(),
    }
    if source_account_id is None:
        return funding, []
    source = LedgerAccount.objects.filter(
        pk=source_account_id,
        user=context.portfolio.user,
        account_type=LedgerAccount.AccountType.ASSET,
        is_active=True,
    ).first()
    if source is None:
        return funding, [
            issue(
                "invalid_source",
                "La cuenta de origen no está disponible.",
                "Selecciona otra cuenta de origen.",
            )
        ]
    internal = any(row["ledger_account_id"] == source.id for row in cash["accounts"])
    funding.update(kind="internal" if internal else "external", name=source.name)
    issues = []
    if not internal and any(row.ledger_account_id == source.id for row in context.cash_accounts):
        issues.append(
            issue(
                "source_ownership",
                "El origen pertenece a otro ámbito o no tiene titularidad.",
                "Selecciona una cuenta de este ámbito o corrige su titularidad.",
            )
        )
    if any(p.ledger_account_id == source.id for p in context.positions):
        issues.append(
            issue(
                "source_position",
                "Una posición de inversión no es una cuenta de efectivo.",
                "Selecciona una cuenta de liquidez.",
            )
        )
    balance = get_account_balance(account=source, as_of_date=on_date, status="posted")
    funding["available"] = str(balance)
    funding["currency"] = source.currency
    if source.currency != context.portfolio.base_currency:
        issues.append(
            issue(
                "source_currency",
                "El reparto requiere un origen en moneda base.",
                "Selecciona una cuenta en la moneda de la cartera; realiza el cambio por separado.",
            )
        )
    elif balance < amount:
        issues.append(
            issue(
                "source_balance",
                "El importe supera el saldo disponible del origen.",
                "Reduce el importe o selecciona otra cuenta.",
            )
        )
    return funding, issues
