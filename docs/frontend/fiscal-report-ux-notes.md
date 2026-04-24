# Fiscal Report UX Notes (Core)

## Scope
Phase 4 frontend for `Informe Fiscal Crypto` in Core:
- `/informe-fiscal` (credentials, sync, CSV import)
- `/informe-fiscal/informe` (annual fiscal report)

## UX Decisions
1. Split flow into two screens:
   - setup/ingestion first,
   - reporting second,
   to reduce cognitive load.
2. Keep a compact visual hierarchy based on shared shells:
   - `ui-page-shell`, `ui-section-card`, shared state blocks.
3. Show "copy-ready" tax summary with explicit casillas:
   - 029 (capital mobiliario),
   - 332 (ganancias/perdidas).
4. Keep warnings as informative, not blocking:
   - futures and bot warnings use soft warning styling.
5. Keep lot-level FIFO detail collapsible under each asset to preserve readability.
6. Never show raw `"missing"` placeholders for buy-side provenance; use typed gap reasons from backend (`pre_period_buy`, `missing_data`, `balance_transfer_in`) with human-readable labels.

## Data/State UX
1. Credential screen includes:
   - create/delete credential,
   - per-credential sync actions,
   - fiscal year selector for sync scope,
   - recent sync stats summary,
   - latest imported-data block (new/updated trades, incomes, bots),
   - CSV import history.
2. Report screen includes explicit states:
   - loading,
   - empty (report not generated),
   - error.
3. Bot table policy:
   - bot rows are informational and explicitly excluded from fiscal summary totals,
   - fiscal summary is computed from FIFO-traceable movement datasets.
4. Trade FIFO detail policy:
   - consume backend `schema_version` to adapt rendering contracts,
   - render `sales[].matched_lots[]` as the canonical traceability dataset,
   - render `gap_reason` badges and CTA path to `ManualCostBasis` inputs when coverage gaps exist.

## Mirror Decision (Core -> SaaS)
Phase 4 spec explicitly marks SaaS mirror as out of MVP scope.
No mirror was implemented in `frontend/` for this phase.

## Export Status (Phase 5E/5F)
1. Backend export endpoint is available in Core:
   - `GET /api/v1/broker/fiscal-report/export/?year=YYYY&format=csv|pdf`
2. Download button and final UX integration remain in Phase 5F frontend scope.
