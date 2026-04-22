from __future__ import annotations

from .common import csv_rows, parse_pionex_datetime, to_decimal, upsert_income_event_dedup
from ..models import IncomeEvent


def import_pionex_others(*, uploaded_file, credential=None) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0
    for row in csv_rows(uploaded_file):
        tag = (row.get("tag") or "").strip()
        if tag != "CommissionIn":
            skipped += 1
            continue
        timestamp = parse_pionex_datetime(row.get("date(UTC+0)") or "")
        amount = to_decimal(row.get("amount"))
        asset = (row.get("coin") or "").strip().upper()
        defaults = {
            "credential": credential,
            "source": IncomeEvent.Source.PIONEX_COMMISSION_CSV,
            "income_type": IncomeEvent.IncomeType.COMMISSION,
            "description": "Pionex CommissionIn",
            "raw": row,
        }
        _, was_created = upsert_income_event_dedup(
            lookup={
                "timestamp": timestamp,
                "asset": asset,
                "amount": amount,
                "source": IncomeEvent.Source.PIONEX_COMMISSION_CSV,
                "income_type": IncomeEvent.IncomeType.COMMISSION,
            },
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated, "skipped": skipped}
