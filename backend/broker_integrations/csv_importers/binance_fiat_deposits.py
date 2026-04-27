from __future__ import annotations

from decimal import Decimal

from .common import csv_rows, deterministic_id, parse_binance_datetime, to_decimal
from ..models import BrokerCredential, DepositWithdrawal


def _parse_amount(value: str) -> Decimal:
    text = (value or "").strip()
    if not text:
        return to_decimal("0")
    return to_decimal(text.split(" ", 1)[0], places=10)


def import_binance_fiat_deposits(
    *, uploaded_file, credential: BrokerCredential | None = None
) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0

    for row in csv_rows(uploaded_file):
        status = (row.get("Estado") or "").strip().upper()
        if status != "SUCCESSFUL":
            skipped += 1
            continue

        timestamp_text = (row.get("Hora") or "").strip()
        if not timestamp_text:
            skipped += 1
            continue

        gross_amount = abs(_parse_amount(row.get("Monto de depósito") or ""))
        received_amount = abs(_parse_amount(row.get("Monto a recibir") or ""))
        fee_amount = abs(_parse_amount(row.get("Tarifa") or ""))
        if received_amount <= 0:
            skipped += 1
            continue

        transaction_id = (row.get("ID de transacción (TXID)") or "").strip()
        if not transaction_id:
            transaction_id = deterministic_id(
                timestamp_text,
                row.get("Método"),
                gross_amount,
                received_amount,
            )

        total_cost_eur = gross_amount
        if total_cost_eur <= 0 and fee_amount > 0:
            total_cost_eur = received_amount + fee_amount
        cost_eur_per_unit = total_cost_eur / received_amount if total_cost_eur > 0 else None

        _, was_created = DepositWithdrawal.objects.update_or_create(
            source=DepositWithdrawal.Source.BINANCE_CSV,
            transaction_id=transaction_id,
            defaults={
                "credential": credential,
                "direction": DepositWithdrawal.Direction.DEPOSIT,
                "asset": "EUR",
                "amount": received_amount,
                "timestamp": parse_binance_datetime(timestamp_text),
                "cost_eur_per_unit": cost_eur_per_unit,
                "notes": (row.get("Método") or "").strip(),
                "raw": row,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return {"created": created, "updated": updated, "skipped": skipped}
