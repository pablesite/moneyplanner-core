from __future__ import annotations

import base64
from binascii import Error as BinasciiError

from django.db.models import Q, QuerySet
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from .models import LedgerTransaction


def _decode_cursor(cursor: str) -> tuple[str, int]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    except (UnicodeDecodeError, ValueError, BinasciiError) as exc:
        raise ValidationError({"cursor": "Query param 'cursor' invalido."}) from exc
    parts = decoded.split(":", 1)
    if len(parts) != 2:
        raise ValidationError({"cursor": "Query param 'cursor' invalido."})
    booking_date_iso, identifier_raw = parts
    if parse_date(booking_date_iso) is None:
        raise ValidationError({"cursor": "Query param 'cursor' invalido."})
    try:
        identifier = int(identifier_raw)
    except ValueError as exc:
        raise ValidationError({"cursor": "Query param 'cursor' invalido."}) from exc
    return booking_date_iso, identifier


def _encode_cursor(transaction: LedgerTransaction) -> str:
    raw = f"{transaction.booking_date.isoformat()}:{transaction.id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def paginate_transactions(
    queryset: QuerySet, page_size: int, cursor: str | None, include_total: bool = True
) -> tuple[list[LedgerTransaction], str | None, int | None]:
    total_count = queryset.count() if include_total else None
    paginated_queryset = queryset
    if cursor:
        booking_date_iso, identifier = _decode_cursor(cursor)
        paginated_queryset = paginated_queryset.filter(
            Q(booking_date__lt=booking_date_iso)
            | Q(booking_date=booking_date_iso, id__lt=identifier)
        )
    rows = list(paginated_queryset.order_by("-booking_date", "-id")[: page_size + 1])
    has_more = len(rows) > page_size
    results = rows[:page_size]
    next_cursor = _encode_cursor(results[-1]) if has_more and results else None
    return results, next_cursor, total_count
