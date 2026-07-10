# Core Architecture

## Objective
Describe the current architecture of `MoneyPlanner Core` as a self-contained open-source product.

## Summary
1. Core owns the product domain and shared business behavior.
2. Core is designed to be useful on its own.
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
7. Financial Plan (`plan`): deterministic projection engine and `/api/plan/*`
8. Supporting product capabilities that belong to the Core domain baseline

## Architectural Rule
1. Shared product behavior belongs in Core.
2. Domain rules should live in backend domain layers, not in deployment-specific integrations.
3. Core documentation must remain self-contained and understandable without Core documentation.

## Internal Structure
1. Backend apps organize domain areas such as accounts, budget, net worth, accounting, memberships, and shared core services.
2. Frontend code is organized by product domains under `frontend/src/domains/*`, including domain-specific UI such as `accounting`.
3. Operational and functional documentation for the OSS product lives under `core/docs/`.

## Budget Execution Coverage Contract
1. `GET /api/budget/annual-income/monthly-summary/?year=YYYY` and `GET /api/budget/annual-expense/monthly-summary/?year=YYYY` are the canonical contracts to explain budget coverage vs real execution.
2. The payload distinguishes:
   - `executed_budgeted_total`: real execution matched to budgeted annual lines
   - `executed_unbudgeted_total`: real execution detected in ledger without annual budget line
   - `executed_total`: full real execution (`budgeted + unbudgeted`)
3. Monthly rows mirror the same split with `executed_budgeted`, `executed_unbudgeted`, and `executed_total`.
4. Responses include taxonomy breakdowns by category/subcategory (with monthly detail):
   - `income_execution_breakdown` for income summary
   - `expense_execution_breakdown` for expense summary
   so Core frontends can render unbudgeted execution visibility without duplicating backend rules.

## Net Worth Investment Contribution Intervals
1. Assets in category `investments` can be configured with multiple periodic contribution intervals through `contribution_intervals` in the asset serializer payload.
2. Each interval stores `start_date`, optional `end_date`, `amount`, `frequency` (`monthly` or `weekly`), and optional `currency`.
3. Legacy flat fields in `Asset` remain available for backward compatibility, while the schedule builder prioritizes interval rows when present.

## Net Worth Timeline Contract
1. `GET /api/net-worth/timeline/` returns monthly rows for the chart plus a `comparisons` object for summary UIs.
2. `comparisons` exposes four baseline points calculated by Core in the user's base currency:
   - `previous_month_close`
   - `same_day_previous_month`
   - `previous_year_close`
   - `same_day_previous_year`
3. Each point has `{date, total_assets, total_liabilities, net_worth}` or `null` when the reference date does not exist or predates the timeline range.
4. `prev_month_same_day` remains as a compatibility alias for `comparisons.same_day_previous_month`.

## Financial Plan Projection Contract
1. Core owns the `plan` app and exposes `/api/plan/*` for the SaaS frontend. The MVP has no Core frontend UI.
2. Each user has one `FinancialPlan`; `POST /api/plan/` is idempotent and updates the existing plan when present.
3. `AssumptionSet` is globally seeded with `prudent`, `expected` (default), and `favorable`; snapshots freeze the exact hypothesis values used.
4. `AssetClassificationService` infers asset function from net-worth taxonomy and applies optional `PlanAssetFunction` overrides. Associated liabilities through `Liability.financed_asset` are subtracted from the asset's functional net value to avoid double counting.
5. `ProjectionService` projects yearly in the user's base currency. Current positions are converted to `UserSettings.base_currency`; FX rates are not projected.
6. Target spending is entered in today's euros. Forward projection inflates target income and future pension/other income using the selected assumptions.
7. Planned contribution precedence for the projection is `InvestmentContributionInterval` plus active `AnnualExpenseEntry` rows with `cashflow_role in {savings, investment}`. The engine deliberately avoids using one recent month as the contribution baseline.
8. If the target date is before pension start, the required capital is split into a bridge period plus post-pension gap capital. The engine does not apply a single withdrawal-rate rule to the full lifetime need.
9. In Phase 1, financial cases such as car purchase, second home purchase, and sabbatical are represented as already-incorporated base data. Hypothetical non-contaminating scenarios are Phase 3 scope.

## Financial Plan Scenario Contract
1. `Scenario` and `ScenarioEvent` model hypothetical decisions without mutating real net worth, budget execution, or accounting.
2. Scenario comparison runs the projection engine with current accepted plan events plus the draft scenario deltas. It persists only non-official `ProjectionSnapshot` rows (`is_official=False`) linked to the scenario.
3. Accepted scenarios create a `PlanEvent` with the exact event payload in `planned_impact_json`. Active planned events are included in later official projections.
4. Scenario payments apply the agreed MVP rule: initial outflows reduce security capital first and then productive capital. New assets are classified with the same plan functions (`productive`, `security`, `short_term_goal`, `family_use`, `unknown`).
5. Monthly deltas apply from the event start date to the explicit end date. If no end date exists and the delta is tied to a new debt, it ends when that debt term ends; otherwise it remains active for projection purposes.
6. New scenario debt uses an amortizing monthly payment when term and interest are present; if no interest is present, it falls back to linear principal amortization.
7. Accepting a scenario does not create real `Asset`, `Liability`, `LedgerTransaction`, or check-in rows. It does create future budget entries from existing budget taxonomy defaults or from editable `metadata_json.budget_lines` supplied by the UI.
8. Temporary recurrent budget entries support `term_start_month`, `term_end_month`, and `term_end_year`, so scenario-generated rows can start and end in the intended months.

## Import Traceability And Accounting API
1. The old ad-hoc MoneyWiz CSV importer has been retired from the public Core API.
2. Imported accounting rows remain traceable through `LedgerTransaction.origin`, `import_source` and `import_fingerprint`; consolidated imported rows are no longer treated as disposable cleanup data.
3. Portable data import/export remains the supported whole-dataset migration path.
4. The accounting movement contract supports bidirectional investment flow with explicit direction (`inflow` / `outflow`).
5. Quick-entry investment payloads support optional manual realized metadata (`realized_cost_basis`, `realized_gain_loss`) without enforcing automatic PnL calculation in this phase.
6. The accounting timeline API exposes a daily consolidated balance series for active ledger accounts:
   - `GET /api/accounting/transactions/daily-balance-series/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&status=posted|draft`
   - optional `account_ids=1,2,3` scopes the series to validated active asset/liability accounts
7. Transaction lists expose the calculated `needs_review` classification signal, accept `review_state=needs_review|reviewed`, and return a filtered `needs_review_count` for operational review queues.

## Market Data Layer
1. External market datasets are synchronized by a dedicated worker service: `market_data_sync`.
2. The canonical sync command is `python manage.py sync_market_data --datasets fx inflation --mode reconcile|refresh`.
3. Core exposes a manual admin trigger endpoint for sync retries from UI: `POST /api/core/market-data/sync/` (defaults to `inflation` in `reconcile` mode).
4. Persisted datasets in Core are:
   - `FxRate` (daily FX and supported crypto crosses)
   - `InflationIndex` (monthly IPC national + CCAA)
5. Sync coverage and operational status are tracked in `MarketDataSyncState`.
6. Domain consumers (for example `net_worth`) read only persisted data from Core; they do not call external providers.
7. Core exposes an authenticated conversion endpoint `GET /api/core/fx/convert/?amount=&from=&to=&date=` (service `convert_currency_detailed`). It preserves crypto precision (up to 8 decimals, unlike `convert_currency` which quantizes to 2), resolves the rate for the requested date (direct/inverse/triangulation), and on a miss triggers a targeted on-demand sync via `market_data` before falling back to the nearest earlier quote. The response reports `{ converted, rate, rate_date, resolution: same|exact|synced|fallback }`.

## Monthly Close Data Model

`MonthlyClose` (app `budget`) is a lifecycle wrapper over the three monthly checkin models:
- `AnnualIncomeMonthlyCheckin` (budget)
- `AnnualExpenseMonthlyCheckin` (budget)
- `LiquidityMonthlyCheckin` (net_worth)

For liquidity rows covered by accounting ledger, monthly close uses ledger as default execution source. A user can create a manual liquidity checkin for the same month/asset to temporarily override ledger for reconciliation purposes; deleting that checkin restores ledger as source.

The liquidity monthly summary reports the monthly close perimeter: active cash assets plus interest-bearing investment assets (currently crowdlending, real-estate crowdfunding, and any investment asset with positive TAE) minus active credit-card liabilities. The existing `planned_total`, `executed_total`, and `deviation_total` fields are net perimeter totals so the monthly-close residual compares income/expense execution against the same position that includes card spending as short-term debt and passive income retained in scoped non-cash assets. The payload also exposes gross asset and liquid-liability totals (`gross_asset_*`, `liquid_liability_*`) and emits liability rows with `row_type=liability`. Asset rows include `annual_interest_tae` so clients can classify remunerated liquidity by actual expected interest instead of institution names. Liability rows use ledger/effective liability balance by default and can be manually adjusted through a month-end `LiabilityValuation` with `source=manual_checkpoint`. Expenses that move value into an asset already inside the close perimeter are exposed as `perimeter_internal_expense_total` and treated as internal movements for residual calculation.

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
