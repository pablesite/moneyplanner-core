from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import TextIOWrapper
from typing import Any, Iterable


def to_decimal(value: Any, *, places: int = 10) -> Decimal:
    if value is None:
        return Decimal("0")
    raw = str(value).strip().replace(",", "")
    if raw == "":
        return Decimal("0")
    try:
        decimal_value = Decimal(raw)
        quant = Decimal("1").scaleb(-places)
        return decimal_value.quantize(quant, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return Decimal("0")


def parse_pionex_datetime(raw: str) -> datetime:
    dt = datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)


def parse_pionex_timestamp(raw: Any) -> datetime:
    if raw is None:
        raise ValueError("timestamp vacío")
    text = str(raw).strip()
    if text.isdigit():
        number = int(text)
        if number > 10_000_000_000:
            number = number / 1000
        return datetime.fromtimestamp(number, tz=timezone.utc)
    return parse_pionex_datetime(text)


def csv_rows(uploaded_file: Any) -> Iterable[dict[str, str]]:
    uploaded_file.seek(0)
    wrapper = TextIOWrapper(uploaded_file, encoding="utf-8-sig")
    try:
        yield from csv.DictReader(wrapper)
    finally:
        wrapper.detach()


def deterministic_id(*parts: Any) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode()).hexdigest()


def split_symbol(symbol: str) -> tuple[str, str]:
    text = symbol.strip().upper()
    if "_" in text:
        base, quote = text.split("_", 1)
        if quote.endswith("_PERP"):
            quote = quote.replace("_PERP", "")
        if quote.endswith("PERP"):
            quote = quote.replace("PERP", "")
        return base, quote or "USDT"
    for suffix in ("USDT", "USDC", "BTC", "ETH", "EUR"):
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)], suffix
    return text, "USDT"


def upsert_income_event_dedup(*, lookup: dict[str, Any], defaults: dict[str, Any]) -> tuple[Any, bool]:
    from ..models import IncomeEvent

    queryset = IncomeEvent.objects.filter(**lookup).order_by("id")
    existing = queryset.first()
    if existing is None:
        payload = {**lookup, **defaults}
        return IncomeEvent.objects.create(**payload), True
    # Defensive cleanup for previously duplicated records created in older runs.
    queryset.exclude(id=existing.id).delete()
    for key, value in defaults.items():
        setattr(existing, key, value)
    existing.save()
    return existing, False
