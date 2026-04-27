from __future__ import annotations

from .common import csv_rows, deterministic_id, parse_binance_datetime, to_decimal
from ..models import BrokerCredential, BrokerTrade, DepositWithdrawal, ManualCostBasis


def _has_prior_known_acquisition(*, ownership, asset: str, timestamp) -> bool:
    return (
        BrokerTrade.objects.filter(
            credential__ownership=ownership,
            base_asset=asset,
            side=BrokerTrade.Side.BUY,
            timestamp__lte=timestamp,
        ).exists()
        or DepositWithdrawal.objects.filter(
            credential__ownership=ownership,
            asset=asset,
            direction=DepositWithdrawal.Direction.DEPOSIT,
            timestamp__lte=timestamp,
        ).exists()
        or ManualCostBasis.objects.filter(
            ownership=ownership,
            asset=asset,
            acquired_at__lte=timestamp,
        ).exists()
    )


def import_binance_simple_earn_flexible(
    *, uploaded_file, credential: BrokerCredential | None = None
) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0
    ownership = credential.ownership if credential is not None else None

    for row in csv_rows(uploaded_file):
        status = (row.get("Estado") or "").strip().upper()
        method = (row.get("Método") or "").strip().lower()
        destination = (row.get("Canjear en") or row.get("De") or "").strip().upper()
        if status != "SUCCESS" or "redemption" not in method or destination != "SPOT":
            skipped += 1
            continue

        timestamp_text = (row.get("Fecha de reembolso/canje") or "").strip()
        if not timestamp_text:
            skipped += 1
            continue
        timestamp = parse_binance_datetime(timestamp_text)
        asset = (row.get("Moneda") or row.get("Nombre del Producto") or "").strip().upper()
        amount = abs(to_decimal(row.get("Principal reembolsado"), places=10))
        if not asset or amount <= 0:
            skipped += 1
            continue

        if ownership is not None and _has_prior_known_acquisition(
            ownership=ownership,
            asset=asset,
            timestamp=timestamp,
        ):
            skipped += 1
            continue

        transaction_id = deterministic_id(
            timestamp_text,
            asset,
            amount,
            method,
            destination,
        )
        _, was_created = DepositWithdrawal.objects.update_or_create(
            source=DepositWithdrawal.Source.BINANCE_CSV,
            transaction_id=transaction_id,
            defaults={
                "credential": credential,
                "direction": DepositWithdrawal.Direction.DEPOSIT,
                "asset": asset,
                "amount": amount,
                "timestamp": timestamp,
                "cost_eur_per_unit": None,
                "notes": "Binance Simple Earn Flexible redemption",
                "raw": row,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return {"created": created, "updated": updated, "skipped": skipped}
