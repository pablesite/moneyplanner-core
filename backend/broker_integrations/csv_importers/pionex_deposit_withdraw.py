from __future__ import annotations

from .common import csv_rows, deterministic_id, parse_pionex_datetime, to_decimal
from ..services.eur_converter import EurConverter
from ..models import BrokerCredential, DepositWithdrawal


_AUTO_COST_ASSETS = {"USDC", "USDT"}


def _infer_cost_eur_per_unit(*, asset: str, timestamp, direction: str):
    if direction != DepositWithdrawal.Direction.DEPOSIT or asset not in _AUTO_COST_ASSETS:
        return None
    try:
        return EurConverter().get_eur_rate(trade_date=timestamp.date(), asset=asset)
    except ValueError:
        return None


def import_pionex_deposit_withdraw(
    *, uploaded_file, credential: BrokerCredential | None = None
) -> dict[str, int]:
    """Import Pionex deposit-withdraw.csv.

    Expected columns (defensive — handles common Pionex export variations):
      date(UTC+0) | coin | amount | direction | order_id
    Rows where direction is neither deposit nor withdrawal are skipped.
    """
    created = 0
    updated = 0
    skipped = 0
    for row in csv_rows(uploaded_file):
        raw_direction = (
            (
                row.get("direction")
                or row.get("tx_type")
                or row.get("type")
                or row.get("tag")
                or row.get("side")
                or ""
            )
            .strip()
            .lower()
        )
        if raw_direction in ("deposit", "in", "充值"):
            direction = DepositWithdrawal.Direction.DEPOSIT
        elif raw_direction in ("withdrawal", "withdraw", "out", "提现"):
            direction = DepositWithdrawal.Direction.WITHDRAWAL
        else:
            skipped += 1
            continue

        timestamp = parse_pionex_datetime(row.get("date(UTC+0)") or row.get("date") or "")
        asset = (row.get("coin") or row.get("currency") or row.get("asset") or "").strip().upper()
        amount = to_decimal(row.get("amount"))
        transaction_id = (
            row.get("order_id")
            or row.get("txid")
            or row.get("tx_id")
            or row.get("transaction_id")
            or ""
        ).strip()
        if not transaction_id:
            transaction_id = deterministic_id(
                row.get("date(UTC+0)") or row.get("date"),
                asset,
                amount,
                raw_direction,
            )

        _, was_created = DepositWithdrawal.objects.update_or_create(
            source=DepositWithdrawal.Source.PIONEX_CSV,
            transaction_id=transaction_id,
            defaults={
                "credential": credential,
                "direction": direction,
                "asset": asset,
                "amount": amount,
                "timestamp": timestamp,
                "cost_eur_per_unit": _infer_cost_eur_per_unit(
                    asset=asset,
                    timestamp=timestamp,
                    direction=str(direction),
                ),
                "raw": row,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated, "skipped": skipped}
