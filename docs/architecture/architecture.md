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
10. For adults with `birth_date`, retirement is derived deterministically on their 67th birthday and drives both the end of labour income and the start of pension income. Persisted manual dates remain a compatibility fallback only when birth date is absent.

## Financial Plan Scenario Contract
1. `Scenario` and `ScenarioEvent` model hypothetical decisions without mutating real net worth, budget execution, or accounting.
2. Scenario comparison runs the projection engine with current accepted plan events plus the draft scenario deltas. It persists only non-official `ProjectionSnapshot` rows (`is_official=False`) linked to the scenario.
3. Accepted scenarios create a `PlanEvent` with the exact event payload in `planned_impact_json`. Active planned events are included in later official projections.
4. Scenario payments apply the agreed MVP rule: initial outflows reduce security capital first and then productive capital. New assets are classified with the same plan functions (`productive`, `security`, `short_term_goal`, `family_use`, `unknown`).
5. Monthly deltas apply from the event start date to the explicit end date. If no end date exists and the delta is tied to a new debt, it ends when that debt term ends; otherwise it remains active for projection purposes.
6. New scenario debt uses an amortizing monthly payment when term and interest are present; if no interest is present, it falls back to linear principal amortization.
7. Accepting a scenario does not create real `Asset`, `Liability`, `LedgerTransaction`, or check-in rows. It does create future budget entries from existing budget taxonomy defaults or from editable `metadata_json.budget_lines` supplied by the UI.
8. Temporary recurrent budget entries support `term_start_month`, `term_end_month`, and `term_end_year`, so scenario-generated rows can start and end in the intended months.
9. Scenario-generated annual budget rows use reserved lineage `plan_event:<PlanEvent.id>`. Budget serializers expose `is_plan_managed`, `plan_event_id`, and `plan_event_name`; general budget `PUT`/`PATCH`/`DELETE` operations reject managed rows with `403 plan_managed_entry`.
10. `GET /api/plan/events/{id}/budget-lines/` is the inverse trace from a user-owned plan event to its income and expense rows. `audit_plan_budget_lineage` reports invalid/orphan lineage and can explicitly repair the legacy scenario-ID format; it never deletes rows.
11. `PlanEvent.effective_end_date` is the first month in which a closed event no longer produces recurring effects. Closing preserves historical and one-off rows, splits/shortens the managed recurrent lineage at month precision, removes later rows, records the exact mutation in `actual_impact_json.closure`, and recalculates the official projection.
12. Event closure stops recurring income, expense, and contribution deltas. The virtual asset residual remains in the projection because disposal proceeds are not modeled in this phase; real asset disposal remains owned by Patrimonio.
13. `ScenarioEvent.metadata_json.one_off_items` may preserve several named one-off expenses within one decision. The serializer makes their sum the canonical `initial_outflow`; comparison applies that total once, while acceptance creates one traceable managed budget row per concept. Events without this metadata retain the legacy aggregate initial-outflow behavior.

## Occurred (Retrospective) Decisions

1. `POST /api/plan/events/occurred/` registers a decision the user already took. It creates a `PlanEvent` with `status=occurred` and `actual_date`, and creates **no** budget rows: the rows already exist.
2. Occurred events are excluded from the projection by construction — `plan_event_payloads` only reads `planned` events. This is required, not cosmetic: the effects of a past decision are already inside current net worth and the current fiscal year's budget, so re-applying its deltas would double-count them.
3. Registration **adopts** existing budget rows by rewriting their `event_group` to `plan_event:<id>`, which makes them `is_plan_managed` (so general budget writes reject them) and puts them under the event's closure lineage. Amounts, dates and taxonomy are never modified.
4. Rows whose `source_liability` or `source_asset` is set cannot be adopted. Liability/asset budget synchronization does `get_or_create` keyed on its own `event_group` (`liability_<id>`, `asset_<id>`), so rewriting it would make the next sync miss the row and create a duplicate. Their lineage is already the asset or liability.
5. Rows already owned by another plan event cannot be adopted twice.
6. `DELETE /api/plan/events/{id}/` releases an occurred event: every adopted row returns to the `previous_event_group` recorded in `actual_impact_json.registration`, and the event is deleted. Without this, a mistaken registration would leave real user rows frozen as plan-managed.
7. Real assets and liabilities are **linked**, never adopted: `PlanEvent.linked_assets` / `linked_liabilities` (M2M to `net_worth`). Net worth stays their owner and keeps generating their budget rows. Linking is what lets a decision state its full impact (outflow **and** debt taken on) without stealing that lineage. `GET /api/plan/events/{id}/budget-lines/` returns the linked entities and the annual expense they generate, alongside the adopted rows.

## Decision Lifecycle

The boundary: **the plan owns the future; net worth owns the present and the commitment already taken on.** A decision has two lives, and three ways to leave the first one.

1. **Forecast (`planned`).** Accepting a scenario creates a `PlanEvent` and the future budget rows the plan itself forecasts. Nothing exists in net worth yet: no asset, no liability, no real commitment. This is what feeds the projection deltas.
2. **Materialization** — `POST /api/plan/events/{id}/materialize/`. The decision actually happened, so the truth moves to net worth: the real `Asset` and `Liability` are created **prefilled from the `ScenarioEvent`** (principal, rate, term, start date), the liability starts generating its own real installments (lineage `liability_<id>`), and the event becomes `occurred` and stops feeding the projection. The plan's forecast **financing** rows are deleted — the liability is about to regenerate them and they would double up. Every other row (down payment already made, running costs, contributions) is **released back to the user** (`event_group=""`): they are real, they are his, and from now on he edits them in Presupuesto. The simulated `new_asset_type` is written as a `PlanAssetFunction` override so classification respects what was simulated.
3. **Cancellation** — `POST /api/plan/events/{id}/cancel/`. Changed your mind about something that has not happened. Only valid while `planned`: the forecast rows the plan created are deleted whole, the event is deleted, the source scenario returns to `draft` (so it can be compared and accepted again) and the projection returns to where it was. Nothing about the present changes. What already happened is undone in net worth, not here.
4. **Closure** (`/close/`) is a different thing and only applies to what already occurred: it retires the recurring effects of a real decision from a date onwards.

### Baseline absorption (double counting)

An accepted event contributes deltas to the projection, but the budget rows it created enter the **current fiscal year's** budget as soon as its year arrives — and the current fiscal year is exactly where `planned_contribution_amount` and `structural_income` read the projection's contribution and income baseline from. From that moment the event is already inside the baseline, and adding its deltas on top counts it twice (measured: a 6.000 €/yr contribution produced 6.000 €/yr of phantom savings, compounding).

`plan_event_payloads` therefore marks each payload `baseline_absorbed` when `start_year <= current fiscal year`, and `event_deltas_for_year` skips its **contribution and income** deltas. The **expense** delta keeps applying: it raises the target standard of living, which the user declares and the budget does not feed. Draft scenarios compared via `extra_events` are never absorbed — their rows do not exist yet, so their deltas must apply.

## Financial Plan Foundations And Recommendations
1. `Finding` and `Recommendation` live in the Core `plan` app. Findings are unique per `(plan, code, period)` and recommendations are unique per `(finding, code)`.
2. `FoundationService` ports the former frontend guide diagnostics into backend-owned metrics: cash flow, emergency fund, debt, net-worth health, planned contribution and data quality. Each scored block also publishes a product `status` band (`good` >= 70, `warning` >= 40, `critical` below) computed from the rounded score, so clients color the diagnosis without owning thresholds.
3. `FindingService` evaluates deterministic MVP findings from those foundations and the expected projection. Resolved findings are closed instead of duplicated.
4. `RecommendationService` generates deterministic template-based actions with full explanation payloads (`action_json`, `impact_json`, `alternatives_json`). The plan profile only shifts priority; it does not change accounting calculations.
5. Recommendation simulation creates a draft `Scenario` and nested `ScenarioEvent`; it does not mutate plan, budget, net worth or accounting until the scenario is explicitly accepted.
6. `MonthlyClosePlanService` is invoked after monthly-close finalization. It is a no-op when the user has no financial plan and logs failures without breaking the monthly-close lifecycle.
7. Monthly-close plan impact exposes at most two open findings and one open recommendation. Projected-year deltas are only communicated when the rounded year change is material (`abs(delta) >= 1`).
8. The plan engine has one active fiscal-year window: the current natural year, resolved by `plan_fiscal_year()`. Foundations, structural income, and budget-based contributions never aggregate rows from different fiscal years.
9. Structural income excludes one-off rows. One-off income is not converted into recurring labour income or capital automatically in the MVP; future capital effects require an explicit plan event.
10. Aggregated labour income stops after the latest configured `employment_income_end_date` among active plan adults. This is an explicit approximation until budget income has canonical per-member attribution; missing dates are reported as a data-quality factor.
11. Expense inputs use one exhaustive role-based classifier shared by foundations and projection: operating, temporary commitment, contribution, asset purchase, tax/other, or unclassifiable. Unknown values are surfaced through data quality instead of disappearing silently.

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
