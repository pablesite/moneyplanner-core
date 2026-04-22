from __future__ import annotations

from .common import csv_rows, parse_pionex_datetime, to_decimal, upsert_income_event_dedup
from ..models import IncomeEvent


def import_pionex_staking(*, uploaded_file, credential=None) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0
    for row in csv_rows(uploaded_file):
        tag = (row.get("tag") or "").strip()
        if tag not in {"issued_profit", "claimed_profit"}:
            skipped += 1
            continue
        income_type = (
            IncomeEvent.IncomeType.EARN_ISSUED
            if tag == "issued_profit"
            else IncomeEvent.IncomeType.EARN_CLAIMED
        )
        timestamp = parse_pionex_datetime(row.get("date(UTC+0)") or "")
        amount = to_decimal(row.get("Received Quantity"))
        asset = (row.get("Received Currency") or "").strip().upper()
        defaults = {
            "credential": credential,
            "source": IncomeEvent.Source.PIONEX_STAKING_CSV,
            "income_type": income_type,
            "description": f"Pionex staking {tag}",
            "raw": row,
        }
        _, was_created = upsert_income_event_dedup(
            lookup={
                "timestamp": timestamp,
                "asset": asset,
                "amount": amount,
                "source": IncomeEvent.Source.PIONEX_STAKING_CSV,
                "income_type": income_type,
            },
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated, "skipped": skipped}
