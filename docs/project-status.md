# Project Status — Core

Current feature status by area. Update this file whenever functionality status changes.

**Last review:** 2026-06-23 | **Core Version:** see `VERSION`

---

## Current and Next Tasks

> Task type convention:
> - **(Manual)** — requires direct user guidance; direction is defined interactively and should not be delegated without that guidance.
> - **(Agent)** — delegable; requires a master plan but not continuous user decisions.

### In progress

| Module | Type | Description | Spec |
|--------|------|-------------|------|
| _(none)_ | — | — | — |

### Next available task

Pick based on capacity: execute **(Agent)** tasks when delegation bandwidth exists; execute **(Manual)** tasks when guided collaboration time is available.

| Module | Type | Description | Spec |
|--------|------|-------------|------|
| _(none)_ | — | — | — |

### Pre-production roadmap snapshot (by area)

Consolidated view of what remains in Core before production launch. See `roadmap/product-roadmap.md` for module-level details.

| Area | Priority | Status | Description |
|------|----------|--------|-------------|
| Accounting — v1 | High | ✅ | Core contract supports the SaaS daily-operations workspace: calculated classification review queue and validated account-scoped daily balance series. Imported movement traceability remains preserved. |
| Budget — v1 | High | ✅ | Functional closeout applied and manually reviewed: canonical monthly summaries for execution/coverage, ledger precedence over manual check-ins, backend errors shown inside line modals, and header aligned with Net Worth. |
| Net Worth — asset/liability modals | Medium | ✅ | Full review of asset and liability create/edit modals completed. Module v1 functionally closed. |
| Monthly Close — dual mode | High | ✅ | Automatic implementation completed (backend + frontend) and operational manual review completed. v1 bugs fixed on 2026-05-20: reconciliation bridge column alignment (CSS subgrid) and per-account liquidity reference (previous month effective balance instead of `asset.amount`). |
| Crypto Tax Report | Medium | ⏸ | Full Spanish IRPF module: Pionex + Binance, global cross-exchange FIFO, boxes 029/332/337. Paused — reassess before resuming. |
| Financial coach — navigation | Medium | ✅ | Simplified v1: `/` -> `/patrimonio` landing, guide at `/guia`, phase 5 (financial independence) removed until an investment portfolio module exists. Contextual quick actions by phase already existed. |
| Remove Data Input module | High | ✅ | `/introduccion-datos` removed in Core. Portable data consolidated in `/account`; assets and liabilities in `/patrimonio`. |
| Unified design system | High (critical) | ✅ | 22 steps completed (see `docs/frontend/design-system.md`). Full foundation done: canonical views, full domain CSS tokenization, `ui-pro-*` layer removed, `--chart-*` palette, accounting hero aligned with Net Worth. Incremental view-by-view polish continues as needed. |
| Residual legacy cleanup | Medium | ✅ | Completed 2026-05-20. Removed: Data Input, `investment_purchase` alias, scalar contribution fields (migration 0042), external `net_worth.services` import, and `compat.*` in capabilities. Budget/check-in fallback is intentional design, not technical debt. See `roadmap/product-roadmap.md`. |
| Core backend refactor | Medium | ✅ | Structural refactor completed (phases 1-5). Contribution backlog remains documented in `roadmap/backend-maintainability-backlog.md`. |
| Core frontend refactor | Medium | ✅ | Structural roadmap completed; contribution backlog documented in `roadmap/frontend-maintainability-backlog.md`; see `roadmap/terminados/frontend-refactor-roadmap.md` and `core/docs/architecture/shared-package-candidates.md`. |
| Auth and security | High | ✅ | Logout with blacklist, cross-user isolation (31 tests), user signup in UI (`/registro`, JWT on signup, rate throttling). Frontend (12->0) and backend CVEs resolved. |
| DB backup/restore | Medium | ✅ | Admin-only endpoints `GET /api/core/db-backup/` and `POST /api/core/db-restore/` based on pg_dump/pg_restore. AccountView migrated to this flow; portable JSON removed. |

---

## Implemented and Stable Features

| Area | Status | Notes |
|------|--------|-------|
| Net Worth (assets, liabilities, liquidity) | ✅ | Complete baseline. Snapshots removed. Added investment-asset generated-expense review modal. Multiple periodic contribution intervals completed (phases 1-2 archived). Charts (timeline + donut) and KPIs validated. Asset and liability create/edit modals reviewed; module v1 functionally closed. |
| Budget (annual income/expense, monthly check-ins) | ✅ | Full category-based flow. Executed evolution bars, recurring/one-time filter, YTD bars, and canonical coverage all functional. Monthly summaries are the canonical execution/coverage contract; line modals show backend errors without losing form state; header aligned with Net Worth. Manual review completed on 2026-05-14. |
| Monthly Close | ✅ | Integrated with budget and accounting. Automatic dual mode, DRAFT/FINALIZED/LOCKED lifecycle, and manual review completed on 2026-05-14. Bug fixes on 2026-05-20: bridge alignment and per-account liquidity reference. |
| Data Input (annual entries) | ✅ | Module/route removed. Responsibilities moved to Budget (income/expense), Net Worth (assets/liabilities), and Account (portable data). |
| Financial Guide / Coach v1 | ✅ | Phases 1-4 scoring implemented. Phase 5 removed until portfolio module exists. Guide at `/guia`; `/` redirects to `/patrimonio`. |
| Family & Ownership (`FamilyMember`, `OwnershipLink`) | ✅ | Complete. |
| Accounting Movements (`LedgerAccount` / `LedgerTransaction` / `LedgerEntry`) | ✅ | Cursor-paginated transaction API includes server filters, `activity_kind`, calculated `needs_review`, review counts and safe daily series scoped by accounts. Bidirectional and multi-currency investment flows, manual realized metadata, invested-capital aggregates and import traceability remain supported. |
| Market data sync (FX, national + regional CPI) | ✅ | Phases 1-6 complete, `market_data_sync` worker live. Tables use server pagination (`page_size=50`) and frontend infinite scroll. |
| DB Backup/Restore (pg_dump) | ✅ | Admin-only backup/restore endpoints based on pg_dump/pg_restore. Portable JSON flow removed from UI and replaced with this flow. |
| Financial scoring phases 1-4 | ✅ | Debt, cash flow, emergency fund, net worth health. |
| Core auth (JWT) | ✅ | User signup from UI (`/registro`), logout with blacklist, token refresh, and rate throttling. |

## Active progress trackers

| Area | Status | Canonical roadmap |
|------|--------|-------------------|
| Accounting-budget separation | ✅ Phases 1-5 complete | `roadmap/terminados/accounting-category-budget-separation-roadmap.md` |
| Frontend refactor | ✅ Completed | Phases 0-6 closed; archived specs in `core/docs/tasks/frontend-refactor/*/terminados/`; `core/docs/architecture/shared-package-candidates.md` created. |

## Deliberately parked (future functionality)

| Module | Description | Specs |
|--------|-------------|-------|
| Crypto Tax Report | Full Spanish IRPF module: Pionex + Binance integration, global cross-exchange FIFO engine, and tax boxes 029/332/337. Parked before public OSS publication; reassess exploration status before resuming. | `core/docs/tasks/fiscal-report/` |

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented and working |
| 🔄 | In progress |
| ⚪ | Not started (future scope) |
| ⛔ | Explicitly out of scope (decision made) |
| ⏸ | Deliberately parked |
