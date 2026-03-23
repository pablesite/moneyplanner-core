# Core Architecture

## Objective
Describe the current architecture of `MoneyPlanner Core` as a self-contained open-source product.

## Summary
1. Core owns the product domain and shared business behavior.
2. Core is designed to be useful on its own, without requiring the SaaS layer.
3. Core includes both backend and frontend for the main personal-finance product experience.

## Core Stack
1. `backend/`
   - Django + DRF
   - domain logic and product APIs
2. `frontend/`
   - Vue + Vite
   - Core product interface
3. PostgreSQL
4. Docker Compose for local development

## Product Scope
1. Net worth
2. Budget and monthly close
3. Accounting / daily movements
4. Account workspace (includes portable data transfer: export/import/replace)
5. Financial guide v1
6. Family and ownership
7. Supporting product capabilities that belong to the Core domain baseline

## Architectural Rule
1. Shared product behavior belongs in Core.
2. Domain rules should live in backend domain layers, not in deployment-specific integrations.
3. Core documentation must remain self-contained and understandable without SaaS documentation.

## Internal Structure
1. Backend apps organize domain areas such as accounts, budget, net worth, accounting, memberships, and shared core services.
2. Frontend code is organized by product domains under `frontend/src/domains/*`, including domain-specific UI such as `accounting`.
3. Operational and functional documentation for the OSS product lives under `core/docs/`.

## Public Import API
1. Core exposes MoneyWiz import endpoints in `accounting` for preview and commit:
   - `POST /api/accounting/transactions/import-moneywiz/preview/`
   - `POST /api/accounting/transactions/import-moneywiz/commit/`
2. The import flow is Core-owned and supports:
   - CSV parsing with optional `sep=` header
   - row fingerprint idempotency persisted on `LedgerTransaction`
   - safe fallback classification when MoneyWiz categories do not map exactly
   - automatic creation of missing operational ledger accounts
3. The accounting movement contract is evolving from purchase-only investment support to a bidirectional investment flow with explicit direction (`inflow` / `outflow`), while preserving legacy compatibility for existing `investment_purchase` writers during transition.
4. The frontend workspace for accounting consumes this API directly in Core and mirrors the same flow in SaaS.

## Market Data Layer
1. External market datasets are synchronized by a dedicated worker service: `market_data_sync`.
2. The canonical sync command is `python manage.py sync_market_data --datasets fx inflation --mode reconcile|refresh`.
3. Persisted datasets in Core are:
   - `FxRate` (daily FX and supported crypto crosses)
   - `InflationIndex` (monthly IPC national + CCAA)
4. Sync coverage and operational status are tracked in `MarketDataSyncState`.
5. Domain consumers (for example `net_worth`) read only persisted data from Core; they do not call external providers.

## Monthly Close Data Model

`MonthlyClose` (app `budget`) is a lifecycle wrapper over the three monthly checkin models:
- `AnnualIncomeMonthlyCheckin` (budget)
- `AnnualExpenseMonthlyCheckin` (budget)
- `LiquidityMonthlyCheckin` (net_worth)

For liquidity rows covered by accounting ledger, monthly close uses ledger as default execution source. A user can create a manual liquidity checkin for the same month/asset to temporarily override ledger for reconciliation purposes; deleting that checkin restores ledger as source.

Each `MonthlyClose` is unique per `(user, fiscal_year, month)`. Lifecycle: `draft → finalized → locked`, with reopening (`finalized → draft`). The three checkin models now support status `estimated` to distinguish algorithmically suggested distributions from manually entered data.

Key services in `budget/services_monthly_close.py`:
- `compute_monthly_close_state` — orchestrates the 3 summary builders, detects coverage, computes delta liquidity, generates suggestions
- `compute_smart_distribution` — proportional distribution of residual net cashflow across uncovered entries
- `apply_distribution_to_checkins` — persists suggestions as checkins with `status=estimated`
- `finalize_monthly_close / reopen_monthly_close / lock_monthly_close` — lifecycle transitions with `select_for_update`

Checkin writes (create + update) in `budget/views.py` and `net_worth/views.py` are blocked with `403` if a `MonthlyClose` with status `finalized` or `locked` exists for that period.

## Related Documents
1. `../../README.md`
2. `../../CONTRIBUTING.md`
3. `../../RELEASING.md`
4. `accounting-movements-architecture.md`
5. `../operations/dev-setup.md`
6. `../roadmap/community-roadmap.md`
7. `../roadmap/terminados/backend-refactor-roadmap.md`
