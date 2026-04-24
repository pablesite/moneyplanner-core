# Phase 5E — Export CSV/PDF anexo AEAT

## Context

Con el matching venta→lotes ya expuesto por la API (Phase 5D), el usuario
necesita un dossier exportable que pueda entregar al asesor o conservar como
anexo de la declaración. CSV es el formato mínimo (columnas AEAT por lote
consumido); PDF es el "entregable visual" con el informe anual formateado.

## Area

`backend`

## Stack

`core`

## Scope

### In scope

- Nuevo endpoint `GET /api/v1/broker/fiscal-report/export/?year=YYYY&format=csv|pdf`.
- CSV: una fila por `MatchedLot`, con columnas compatibles AEAT.
- PDF: informe anual completo (resumen, detalle por asset, matches, capital
  mobiliario, conciliación bots, avisos).
- Botón de descarga en frontend (Phase 5F) — scope backend se limita al endpoint
  y los generadores.

### Out of scope

- Cambios en frontend (Phase 5F).
- Export de otros formatos (XLSX, etc.).

## Plan

### 1. Diagnosis

- Comprobar si Core ya depende de `reportlab` o `weasyprint`. Si no, preferir
  `reportlab` por menor peso y ausencia de dependencias de sistema.
- Revisar el JSON actual de `fiscal-report` post-5D para localizar los campos
  que alimentan el CSV/PDF.

### 2. Change implementation

**`services/fiscal_report_export.py`** (nuevo):
```python
def export_csv(report: dict) -> bytes:
    """Genera CSV con columnas AEAT por MatchedLot."""
    ...

def export_pdf(report: dict) -> bytes:
    """Genera PDF formateado del informe."""
    ...
```

Columnas CSV propuestas (una fila por lote consumido):

| Columna | Contenido |
|--------|-----------|
| denominacion | `base_asset` (BTC, ETH, ...) |
| fecha_adquisicion | `matched_lot.buy_date` (o "N/A" si manual/gap) |
| exchange_adquisicion | `matched_lot.buy_exchange` |
| fecha_transmision | `sell_date` |
| exchange_transmision | `sell_exchange` |
| cantidad | `matched_lot.quantity_consumed` |
| valor_adquisicion_eur | `matched_lot.cost_eur` |
| valor_transmision_eur | cuota proporcional de `proceeds_eur` |
| comision_eur | `matched_lot.fee_eur_allocated` |
| ganancia_perdida_eur | `matched_lot.gain_loss_eur` |
| dias_tenencia | `matched_lot.hold_days` |
| origen_coste | `trade` \| `manual_cost_basis` \| `gap:<reason>` |

Incluir una fila extra por `gap_quantity>0` con `origen_coste="gap:<reason>"`.

PDF (template simple con `reportlab.platypus`):
- Cabecera: ejercicio, credencial (alias, broker), fecha generación.
- Resumen: totales por casilla 029 y 332.
- Por asset: tabla con los `FifoSaleMatch` y sus `MatchedLot`.
- Anexo bots: tabla con `bot_label`, ganancia neta, fila conciliación
  (realized_profit Pionex vs suma fills).
- Anexo capital mobiliario: tabla por `(fuente, asset)`.
- Avisos al final.

**`views.py` + `urls.py`**
```python
class FiscalReportExportView(APIView):
    def get(self, request):
        year = int(request.query_params["year"])
        fmt = request.query_params.get("format", "csv")
        ownership = ...  # helper existente
        report = generate_fiscal_report(ownership, year)
        if fmt == "csv":
            return HttpResponse(export_csv(report),
                                content_type="text/csv",
                                headers={"Content-Disposition": f'attachment; filename="fiscal-{year}.csv"'})
        if fmt == "pdf":
            return HttpResponse(export_pdf(report),
                                content_type="application/pdf",
                                headers={"Content-Disposition": f'attachment; filename="fiscal-{year}.pdf"'})
        return Response({"detail": "unsupported format"}, status=400)
```

### 3. Validation

```bash
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
docker compose -f core/docker-compose.yml exec backend python manage.py test broker_integrations
```

**Unit tests**:
- Export CSV con un informe mock (1 asset, 2 ventas, 3 lotes) → comparar con
  fixture.
- Export PDF → smoke test (no crashea, devuelve bytes que empiezan por
  `b"%PDF-"`).

**Smoke test manual**:
1. `curl -OJ '.../fiscal-report/export/?year=2025&format=csv'` → abrir en hoja
   de cálculo y validar columnas.
2. `curl -OJ '.../fiscal-report/export/?year=2025&format=pdf'` → abrir en
   visor PDF, validar legibilidad.

## Required Documentation Updates

- [x] `core/docs/architecture/api-registry.md` — endpoint de export.
- [x] `core/docs/frontend/fiscal-report-ux-notes.md` — mencionar que el botón
      de export llegará en Phase 5F.
- [x] `core/docs/project-status.md` — marcar Phase 5E cerrada.

## Risks

1. **Dependencia de PDF**: si `reportlab` pesa demasiado, valorar exportar sólo
   CSV en un primer cierre y dejar PDF para después. Documentar claramente en
   caso de cortar scope.
2. **Validez AEAT de las columnas**: las columnas propuestas son una
   aproximación razonable. El usuario debe validar con asesor. Dejar aviso en
   el PDF: "Borrador de apoyo; no sustituye validación fiscal".

## Completion Criteria

- [x] Endpoint `/fiscal-report/export/` responde en CSV y PDF.
- [x] CSV abrible en hoja de cálculo con las columnas listadas.
- [x] PDF legible.
- [x] Tests unitarios pasan.
- [x] Documentation updates done.
- [x] Spec movida a `terminados/`.
- [x] Commit: `feat(broker-integrations): export fiscal report as CSV and PDF`.

## Cierre real (2026-04-24)

- Implementación backend cerrada en commit:
  - `c4283f8 feat(broker-integrations): export fiscal report as CSV and PDF`
- Validación ejecutada en Docker (Core backend):
  - `ruff check .`
  - `ruff format --check .`
  - `mypy .`
  - `python manage.py test broker_integrations --keepdb --noinput`
