# Phase 5F — Frontend drill-down y explicabilidad

## Context

Con el backend completo (fases 5A-5E), el frontend Core debe exponer la
trazabilidad y explicabilidad que ahora existen en la API. Hoy
`/informe-fiscal` solo muestra contadores y `/informe-fiscal/informe` muestra
listas agregadas sin matching venta→lotes ni categorías de gap.

## Area

`frontend`

## Stack

`core`

## Scope

### In scope

**Vista `/informe-fiscal` (sincronización)**
- Sección "Historial de syncs" alimentada por `GET /api/v1/broker/sync-runs/`.
- Drill-down por run: listados paginados de `BrokerTrade`, `IncomeEvent`,
  `BotNetResult` tocados, con filtros (símbolo, source, side).
- Sección "Conciliación de saldos" con `balance_reconciliation` por asset
  (ok / mismatch con delta).

**Vista `/informe-fiscal/informe`**
- Tabla FIFO: por cada venta, fila expandible con `matched_lots`
  (`buy_date`, `buy_exchange`, `quantity_consumed`, `unit_price_eur`,
  `cost_eur`, `fee_eur_allocated`, `gain_loss_eur`, `hold_days`).
- Chip/badge para `gap_reason` tipado con tooltip explicativo; eliminar todo
  renderizado del literal `"missing"`.
- Modal "Asignar coste de adquisición manual" que crea `ManualCostBasis` para
  un `pre_period_buy` y recalcula el informe.
- Sección bots: tabla expandible con fills (BrokerTrade del bot) + fila de
  conciliación `sum(fills_eur)` vs `realized_profit_eur`; diff resaltado si
  excede tolerancia.
- Botón "Exportar" con opciones CSV/PDF (llama al endpoint de Phase 5E).

### Out of scope

- Cambios backend.
- Mirror SaaS (fuera de alcance como en Phases 1-4).

## Plan

### 1. Diagnosis

- Aplicar skill `frontend-system` antes de empezar.
- Releer `core/frontend/src/domains/fiscal-report/` para entender el store,
  tipos TS y componentes actuales.
- Confirmar el nuevo contrato de `fiscal-report` y los endpoints nuevos
  tras Phase 5D/5E.

### 2. Change implementation

**`domains/fiscal-report/api.ts`**
- Añadir tipos `SyncRunSummary`, `SyncRunDetail`, `TradeListResponse`,
  `FifoSaleMatch`, `MatchedLot`, `BalanceReconciliationEntry`,
  `ManualCostBasisInput`.
- Nuevas funciones: `fetchSyncRuns`, `fetchSyncRun`, `fetchTrades`,
  `fetchIncomeEvents`, `fetchBotResults`, `fetchBotResult` (con fills),
  `fetchBalanceReconciliation`, `createManualCostBasis`,
  `deleteManualCostBasis`, `downloadFiscalReportExport`.

**`domains/fiscal-report/store.ts`**
- Estado: `syncRuns`, `activeSyncRun`, `balanceReconciliation`,
  `manualCostBases`.
- Acciones: cargar historial, abrir detalle, crear/eliminar manual cost basis,
  recargar informe tras cambios.

**Componentes nuevos en `domains/fiscal-report/components/`**
- `SyncRunHistoryTable.vue` — tabla paginada de runs.
- `SyncRunDetailPanel.vue` — drill-down con tabs (trades / income / bots).
- `BalanceReconciliationTable.vue` — asset | expected | actual | delta | status.
- `FifoSaleMatchRow.vue` — fila expandible venta + lotes consumidos.
- `GapReasonChip.vue` — chip con tooltip por `gap_reason`.
- `BotFillsPanel.vue` — tabla expandible con fills del bot + fila conciliación.
- `ManualCostBasisModal.vue` — formulario (asset, quantity, acquired_at, cost_eur,
  exchange_origin, notes) y confirmación.
- `FiscalExportButton.vue` — botón con dropdown CSV/PDF.

**Vistas**
- `FiscalLandingView.vue` — añadir sección "Historial de syncs" y
  "Conciliación de saldos"; mantener bloque de últimos imports como atajo a run
  más reciente.
- `FiscalReportView.vue` — integrar `FifoSaleMatchRow` dentro de
  `FiscalGananciasPerdidaTable`, sustituir render de `"missing"` por
  `GapReasonChip`, añadir `BotFillsPanel`, `FiscalExportButton`.

### 3. Validation

```bash
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run format:check
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
```

**Smoke test manual** (sync ya ejecutado con datos reales 2025):
1. Abrir `/informe-fiscal` → historial de syncs visible con al menos un run;
   conciliación de saldos renderizada.
2. Abrir detalle de un run → drill-down muestra trades/income/bots.
3. Abrir `/informe-fiscal/informe` → cada venta expande sus lotes consumidos;
   nunca aparece el string literal `"missing"`.
4. Crear `ManualCostBasis` para un asset con gap → el informe se regenera y el
   gap desaparece o se reduce.
5. Exportar a CSV → archivo descargado y abrible.
6. Exportar a PDF → archivo descargado y visualizable.

## Required Documentation Updates

- [ ] `core/docs/frontend/fiscal-report-ux-notes.md` — actualizar con el nuevo
      flujo drill-down y matching.
- [ ] `core/docs/frontend/domain-map.md` (si aplica) — registrar componentes
      nuevos.
- [ ] `core/docs/project-status.md` — marcar Phase 5F cerrada y completar el
      ciclo de mejora.

## Risks

1. **Volumen en drill-down**: paginación estricta; la UI no debe cargar más de
   50 filas por página. Confirmar con backend en Phase 5B que los endpoints
   están paginados.
2. **Performance en FIFO match view**: renderizar matches expandibles bajo
   demanda (colapsados por defecto).
3. **Tooltips accesibles**: seguir el patrón de frontend-system; no inventar
   componente nuevo.

## Completion Criteria

- [ ] Todas las vistas y componentes nuevos implementados.
- [ ] Ningún renderizado del literal `"missing"` en el frontend.
- [ ] Exportar CSV/PDF funciona end-to-end.
- [ ] `ManualCostBasis` gestionable vía modal.
- [ ] Lint, format, typecheck verdes.
- [ ] Documentation updates done.
- [ ] Spec movida a `terminados/`.
- [ ] Commit: `feat(fiscal-report-ui): add drill-down, FIFO matching and export to Pionex fiscal report`.
