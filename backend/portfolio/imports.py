from __future__ import annotations

import csv
import hashlib
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Portfolio, PortfolioImportBatch, PortfolioImportRow, PortfolioTrade
from .operations import confirm_operation, operation_fingerprint, preview_operation

REQUIRED_FIELDS = ("operation_type", "booking_date", "position_id", "amount")
OPTIONAL_FIELDS = (
    "cash_account_id",
    "units",
    "unit_price",
    "fee",
    "currency",
    "external_id",
    "description",
    "note",
)


def upload_csv(*, portfolio: Portfolio, uploaded_file) -> tuple[PortfolioImportBatch, bool]:
    raw = uploaded_file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise ValidationError({"file": "El CSV no puede superar 5 MB."})
    fingerprint = hashlib.sha256(raw).hexdigest()
    existing = PortfolioImportBatch.objects.filter(
        portfolio=portfolio, file_fingerprint=fingerprint
    ).first()
    if existing:
        return existing, True
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError({"file": "El CSV debe estar codificado en UTF-8."}) from exc
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [str(value).strip() for value in (reader.fieldnames or []) if value]
    if not headers:
        raise ValidationError({"file": "El CSV no contiene cabeceras."})
    rows = list(reader)
    if not rows:
        raise ValidationError({"file": "El CSV no contiene filas."})
    if len(rows) > 5000:
        raise ValidationError({"file": "El CSV no puede superar 5.000 filas."})
    with transaction.atomic():
        batch = PortfolioImportBatch.objects.create(
            portfolio=portfolio,
            filename=str(getattr(uploaded_file, "name", "cartera.csv"))[:240],
            file_fingerprint=fingerprint,
            headers=headers,
            row_count=len(rows),
        )
        PortfolioImportRow.objects.bulk_create(
            [
                PortfolioImportRow(
                    batch=batch,
                    row_number=index,
                    raw_data={str(key): value for key, value in row.items() if key is not None},
                )
                for index, row in enumerate(rows, start=2)
            ]
        )
    return batch, False


def _mapped_value(raw: dict[str, Any], mapping: dict[str, str], field: str) -> str:
    header = str(mapping.get(field) or "")
    return str(raw.get(header) or "").strip() if header else ""


def _normalize_row(
    *, portfolio: Portfolio, row: PortfolioImportRow, mapping: dict[str, str]
) -> tuple[dict[str, Any], dict[str, str]]:
    normalized = {
        field: _mapped_value(row.raw_data, mapping, field)
        for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS)
    }
    errors: dict[str, str] = {}
    aliases = {
        "compra": "buy",
        "venta": "sell",
        "dividendo": "dividend",
        "interes": "interest",
        "interés": "interest",
        "comision": "fee",
        "comisión": "fee",
        "valoracion": "valuation",
        "valoración": "valuation",
    }
    operation = normalized["operation_type"].lower()
    normalized["operation_type"] = aliases.get(operation, operation)
    try:
        date.fromisoformat(normalized["booking_date"])
    except ValueError:
        errors["booking_date"] = "Usa YYYY-MM-DD."
    for field in ("position_id", "cash_account_id"):
        if normalized[field]:
            try:
                normalized[field] = int(normalized[field])
            except ValueError:
                errors[field] = "Debe ser un identificador numérico."
    for field in ("amount", "units", "unit_price", "fee"):
        if not normalized[field]:
            continue
        try:
            normalized[field] = str(Decimal(normalized[field].replace(",", ".")))
        except InvalidOperation:
            errors[field] = "Usa un número válido."
    normalized = {key: value for key, value in normalized.items() if value not in (None, "")}
    normalized["source"] = PortfolioTrade.Source.CSV
    if not errors:
        try:
            preview_operation(portfolio=portfolio, payload=normalized)
        except ValidationError as exc:
            detail = exc.detail
            if isinstance(detail, dict):
                errors.update({str(key): str(value) for key, value in detail.items()})
            else:
                errors["row"] = str(detail)
    return normalized, errors


@transaction.atomic
def preview_import(
    *, portfolio: Portfolio, batch: PortfolioImportBatch, mapping: dict[str, str]
) -> PortfolioImportBatch:
    if batch.portfolio_id != portfolio.id:
        raise ValidationError({"detail": "La importación no pertenece a la cartera."})
    missing = [field for field in REQUIRED_FIELDS if not mapping.get(field)]
    if missing:
        raise ValidationError({"mapping": f"Faltan campos obligatorios: {', '.join(missing)}."})
    unknown_headers = [value for value in mapping.values() if value and value not in batch.headers]
    if unknown_headers:
        raise ValidationError({"mapping": "El mapeo contiene cabeceras inexistentes."})
    batch.mapping = mapping
    for row in batch.rows.select_for_update():
        if row.status == PortfolioImportRow.Status.CONFIRMED:
            continue
        normalized, errors = _normalize_row(portfolio=portfolio, row=row, mapping=mapping)
        fingerprint = operation_fingerprint(normalized) if not errors else ""
        duplicate = False
        external_id = str(normalized.get("external_id") or "")
        if external_id:
            duplicate = PortfolioTrade.objects.filter(
                portfolio=portfolio,
                source=PortfolioTrade.Source.CSV,
                external_id=external_id,
            ).exists()
        row.normalized_data = normalized
        row.errors = errors
        row.fingerprint = fingerprint
        row.status = (
            PortfolioImportRow.Status.ERROR
            if errors
            else PortfolioImportRow.Status.DUPLICATE
            if duplicate
            else PortfolioImportRow.Status.VALID
        )
        row.save(update_fields=["normalized_data", "errors", "fingerprint", "status"])
    batch.status = PortfolioImportBatch.Status.PREVIEWED
    batch.save(update_fields=["mapping", "status", "updated_at"])
    return batch


@transaction.atomic
def confirm_import(
    *, portfolio: Portfolio, batch: PortfolioImportBatch, row_ids: list[int] | None = None
) -> PortfolioImportBatch:
    batch = PortfolioImportBatch.objects.select_for_update().get(id=batch.id, portfolio=portfolio)
    if batch.status not in {
        PortfolioImportBatch.Status.PREVIEWED,
        PortfolioImportBatch.Status.PARTIAL,
    }:
        raise ValidationError({"detail": "Previsualiza el CSV antes de confirmarlo."})
    rows = batch.rows.select_for_update().filter(status=PortfolioImportRow.Status.VALID)
    if row_ids is not None:
        rows = rows.filter(id__in=row_ids)
    confirmed = 0
    for row in rows:
        result = confirm_operation(
            portfolio=portfolio, payload=row.normalized_data, require_preview=False
        )
        trade_id = result.get("trade_id")
        if trade_id:
            row.trade_id = trade_id
        row.status = PortfolioImportRow.Status.CONFIRMED
        row.save(update_fields=["trade", "status"])
        confirmed += 1
    batch.confirmed_count = batch.rows.filter(status=PortfolioImportRow.Status.CONFIRMED).count()
    remaining = batch.rows.exclude(
        status__in=[PortfolioImportRow.Status.CONFIRMED, PortfolioImportRow.Status.DUPLICATE]
    ).exists()
    batch.status = (
        PortfolioImportBatch.Status.PARTIAL if remaining else PortfolioImportBatch.Status.CONFIRMED
    )
    batch.save(update_fields=["confirmed_count", "status", "updated_at"])
    if confirmed == 0 and batch.confirmed_count == 0:
        raise ValidationError({"detail": "No hay filas válidas seleccionadas."})
    return batch


def serialize_batch(batch: PortfolioImportBatch, *, include_rows: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": batch.id,
        "filename": batch.filename,
        "status": batch.status,
        "headers": batch.headers,
        "mapping": batch.mapping,
        "row_count": batch.row_count,
        "confirmed_count": batch.confirmed_count,
    }
    if include_rows:
        payload["rows"] = [
            {
                "id": row.id,
                "row_number": row.row_number,
                "raw_data": row.raw_data,
                "normalized_data": row.normalized_data,
                "status": row.status,
                "errors": row.errors,
            }
            for row in batch.rows.all()
        ]
    return payload
