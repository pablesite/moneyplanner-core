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

## External SaaS Authentication Boundary

1. Core standalone JWTs keep their local blacklist and rotation behavior.
2. When `AUTH_ACCEPT_EXTERNAL_TOKENS=1`, a SaaS-issued JWT must pass signature, issuer and audience validation and then live session introspection against SaaS.
3. Introspection makes Core respect SaaS account deactivation, password revocation and `must_change_password` immediately.
4. The only non-introspected external token is a two-minute `core_bootstrap` token signed by SaaS and accepted exclusively by `POST /api/family-members/ensure-primary/`.

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

## Ownership Allocation Contract

1. `Ownership.allocation_basis` is backward compatible: existing and newly created ownerships use
   `explicit_split` unless a shared ownership explicitly enables `recurring_income_12m`.
2. Individual ownership is always 100% of its member. Dynamic allocation is valid only for shared
   ownership and never mutates its persisted `OwnershipSplit` rows.
3. Dynamic shares for a close month use the twelve complete natural months immediately before it.
   The source is posted ledger income with individual transaction ownership and an explicit
   `OwnershipIncomeRule`; `salary` is the default rule when dynamic allocation is first enabled.
4. Every eligible entry is converted to the user's base currency with FX effective on its booking
   date. Drafts, shared/unassigned transaction ownership and unmatched taxonomies do not contribute.
5. `OwnershipAllocationSnapshot` stores the source window, source hash, quality status and member
   shares. Draft snapshots can be recomputed; frozen snapshots are immutable inputs for finalized
   monthly closes.
6. Quality is `ready` with 12 observed months, `provisional` with 3-11 and `blocked` below 3, without
   positive income, with negative member income or with missing FX. Blocked results expose no
   effective percentages and never fall back silently to the old explicit split.

## Monthly-close Settlement Inputs

1. `SettlementProfile` is one-to-one with the user and defaults to disabled. Existing close flows do
   not require settlement configuration and retain their previous behavior.
2. A participating `SettlementAccount` references one user-owned asset and gives it one explicit
   role: operating, primary personal destination, allocation destination or physical cash. Operating
   and personal accounts are liquidity; allocation destinations may also be investment assets.
3. `AnnualIncomeEntry.ownership` and `AnnualExpenseEntry.ownership` are the structured canonical
   ownership when present. Nullable fields and legacy `owner_name` keep existing clients compatible.
4. Recurrent expenses route through nullable `settlement_account`. Asset-generated investment rows
   inherit both ownership and an allocation destination only from unambiguous structural links;
   liability-generated rows inherit ownership. Plan-managed rows remain writable only by Mi Plan.
5. Readiness is period-specific and reports missing operating/personal accounts, account ownership,
   budget ownership, expense routes, incompatible effective vectors, dynamic-allocation coverage,
   non-zero opening adjustments and unnormalized wallets.
6. Activation is explicit and idempotent. It captures one member/account opening baseline using the
   effective account ownership for the activation month. A wallet baseline uses accepted physical
   cash while preserving its modeled balance and historical movements for audit.
7. Opening adjustments are signed member/account entries that must sum exactly zero. They carry
   prior fictitious wallet compensations into the economic baseline without representing liquidity.

## Net Worth Investment Contribution Intervals
1. Assets in category `investments` can be configured with multiple periodic contribution intervals through `contribution_intervals` in the asset serializer payload.
2. Each interval stores `start_date`, optional `end_date`, `amount`, `frequency` (`monthly` or `weekly`), and optional `currency`.
3. Legacy flat fields in `Asset` remain available for backward compatibility, while the schedule builder prioritizes interval rows when present.

## Net Worth Timeline Contract
1. `GET /api/net-worth/timeline/` returns monthly rows for the chart plus a `comparisons` object for summary UIs. Each row includes `assets_by_category` in the user's base currency so consumers can render the real historical composition without rebuilding valuation logic.
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
7. Recurring and one-off `savings/investment` budget rows describe the intended use of cash but never create cash themselves. `planned_contribution_schedule` carries their effective amount and destination for every projection year: `savings` directs cash to Security and `investment` to Productive. Asset-generated mirrors are excluded because `InvestmentContributionInterval` is their source of truth; future plan-managed rows are excluded until their event reaches the baseline, avoiding duplicate event deltas.
7b. Active `one_off` budget entries **not** governed by a decision feed the projection as year-specific flows in their `fiscal_year` across the whole horizon (`services_inputs.one_off_flows`): income adds cash, `asset_purchase` moves productive→non-productive (cash becomes an asset), and `tax_fee/transfer/other` are pure outflows. A one-off income in `transfers_support` (for example a gift, inheritance, or family support) is money new to the user: it increases net worth once. Investing that money later is a separate `savings/investment` expense and only changes its destination. A one-off `savings/investment` row is handled only as a planned allocation under point 7. Excluded from the cash path: past years (already in current capital), `is_system_generated` expenses (owned by Patrimonio), `asset_sale` income (modeled via decisions) and entries whose `event_group` starts with `plan_event:`. For the current year only not-yet-occurred entries count (`target_month` after the current month, or no month), so already-spent/received amounts are not double-counted.
7c. **Cash-flow reconciliation and allocation**: in each accumulation year (`year < target_year`), including the remaining months of the current year, `free_surplus = income − operating_expenses − active_temporary_commitments − decision_debt_service` (`services_projection.free_operating_surplus`). Positive surplus first recovers any `financing_gap` and honors debt contributions. Budget/event allocations to Security and Productive are funded next; if their total exceeds the remaining cash, both are reduced proportionally. Only the unassigned remainder follows `security_contribution_rate` (25% by default) until Security reaches `annual_operating_expense × security_target_expense_years`, with the excess going to Productive. Trajectory rows expose free cash, planned/effective/unfunded contribution, funded destination amounts and automatic remainder. A negative surplus consumes Security first, then Productive, and any uncovered amount remains as a recoverable negative `financing_gap`. Temporary commitments expire by `term_end_year`; a user's existing debt service is already represented by its budget line, while new decision debt uses `decision_debt_service_for_year`, so neither is paid "for free" nor counted twice. Known gap: `FoundationService.committed_surplus` reads budget lines only, so a decision's new debt is not yet reflected in the cash-flow *diagnosis* (only in the projection).
7d. Budget recurrence is shared by the Budget API, monthly summaries and Plan inputs. A one-off applies only to its exact `fiscal_year`; manual/non-linked structural rows remain effective from their start year; term rows remain effective through `term_end_year`; asset/liability-generated yearly mirrors apply only to their explicit fiscal slice.
7e. **Projected balance composition**: every trajectory row exposes gross `liquidity_assets`, `investment_assets`, `real_estate_assets`, `furnishings_assets`, `other_assets` and their `total_assets`. Housing/renovation decisions move Real estate; vehicle decisions move Furnishings; security allocations move Liquidity and productive allocations move Investments. Real estate uses `non_productive_appreciation_rate`; furnishings and vehicles use the explicit `furnishings_depreciation_rate` (12% default). Displayed amounts are rounded by category before totaling, and `net_worth = total_assets − liabilities` exactly.
8. If the target date is before pension start, the required capital is split into a bridge period plus post-pension gap capital. The engine does not apply a single withdrawal-rate rule to the full lifetime need.
8b. `preservation_target_eur` is untouchable capital: it is added on top of the required capital (denominator and yearly gate), so preserved wealth never funds the target income. The legacy net-worth check (`preservation_ok`, total net worth ≥ target at the achieving year) remains as an additional gate but rarely binds. `/api/plan/capital-requirements/` deliberately excludes preservation: its amounts describe expense needs only.
9. In Phase 1, financial cases such as car purchase, second home purchase, and sabbatical are represented as already-incorporated base data. Hypothetical non-contaminating scenarios are Phase 3 scope.
10. For adults with `birth_date`, employment end and pension start dates are derived from the configurable ages sent by the client; age 67 is only the initial pension value. `target_date` independently cuts structural labour income for the projection.
11. `GET /api/plan/capital-requirements/?monthly_amounts=a,b,...` returns, for each monthly need in today's euros (1–8 values), the capital required at the target date computed with the same math as the projection's target capital (inflation, pension/other-income offsets, bridge period, withdrawal rate). Plan-event deltas are deliberately excluded: an arbitrary need already defines the expense to cover. This keeps consumer-side progress milestones on the same axis as the projection denominator. Optional `target_year` moves that horizon: the capital required depends on how much bridge is left until the pension, so a consumer showing a denominator built for another year (the overview projects the **sustainable retirement year**, not `plan.target_date`) must request the milestones for that same year — otherwise a smaller monthly need can require more capital than the whole target.
12. Plan member writes reuse an existing same-name adult owned by the user. When setup replaces a draft member with that shared identity, Core moves the plan membership without deleting the draft record, preserving ownership and historical references outside the plan.

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
12. Event closure stops recurring income, expense, and contribution deltas. Asset **disposal** is modeled: an event may carry `disposed_asset_value`/`disposed_asset_type` (removed from its bucket at the projected value in the sale year, symmetric to `new_asset_value`), `proceeds` (added to productive capital) and `disposed_liability_value` (the cancelled associated debt, discounted from both the projected liabilities and `associated_liabilities` so net worth reconciles without double counting). Real asset archival in Patrimonio still happens on occurrence, not on planning.
13. `ScenarioEvent.metadata_json.one_off_items` may preserve several named one-off expenses within one decision. The serializer makes their sum the canonical `initial_outflow`; comparison applies that total once, while acceptance creates one traceable managed budget row per concept. Events without this metadata retain the legacy aggregate initial-outflow behavior.

## Occurred (Retrospective) Decisions

1. `POST /api/plan/events/occurred/` registers a decision the user already took. It creates a `PlanEvent` with `status=occurred` and `actual_date`, and creates **no** budget rows: the rows already exist.
2. Occurred events are excluded from the projection by construction — `plan_event_payloads` only reads `planned` events. This is required, not cosmetic: the effects of a past decision are already inside current net worth and the current fiscal year's budget, so re-applying its deltas would double-count them.
3. Registration **adopts** existing budget rows by rewriting their `event_group` to `plan_event:<id>`, which makes them `is_plan_managed` (so general budget writes reject them) and puts them under the event's closure lineage. Amounts, dates and taxonomy are never modified.
4. Rows whose `source_liability` or `source_asset` is set cannot be adopted. Liability/asset budget synchronization does `get_or_create` keyed on its own `event_group` (`liability_<id>`, `asset_<id>`), so rewriting it would make the next sync miss the row and create a duplicate. Their lineage is already the asset or liability.
5. Rows already owned by another plan event cannot be adopted twice.
6. `DELETE /api/plan/events/{id}/` releases an occurred event: every adopted row returns to the `previous_event_group` recorded in `actual_impact_json.registration`, and the event is deleted. Without this, a mistaken registration would leave real user rows frozen as plan-managed.
7. Real assets and liabilities are **linked**, never adopted: `PlanEvent.linked_assets` / `linked_liabilities` (M2M to `net_worth`). Net worth stays their owner and keeps generating their budget rows. Linking is what lets a decision state its full impact (outflow **and** debt taken on) without stealing that lineage. `GET /api/plan/events/{id}/budget-lines/` returns the linked entities and the annual expense they generate, alongside the adopted rows.

## Planned (Grouping) Decisions

1. `POST /api/plan/events/planned-decision/` (`register_planned_decision`) groups **existing** `one_off` budget rows into a `planned` `PlanEvent` **with** projection impact — a purchase (`new_asset_value`/`new_debt_*`/`initial_outflow`) or a sale (`disposed_asset_value`/`proceeds`/`disposed_liability_value`) applied in `transaction_year` + `transaction_month`. It is the forward-looking sibling of the occurred flow: same `_adopt_budget_entries`/`_link_net_worth` (adopt rows via `event_group`, link real assets/liabilities), but the event is `planned` and contributes to the official projection.
2. Adopting the rows removes them from the `one_off_flows` cash path (point 7b), so the decision counts them exactly once. The `impact` payload is built into `planned_impact_json.events[0]` with the same keys as `scenario_event_payload`.
3. Use it to migrate a transaction already entered as budget one-offs (e.g. a planned home sale) into a decision that disposes the asset and cancels its mortgage in the sale year, instead of counting the sale proceeds as plain income.
4. The current-year row starts after the current net-worth snapshot: structural cash flow and temporary commitments use only the remaining budget months, and new debt service is prorated from `transaction_month`. Decision inflows and outflows in the same month are netted before touching capital buckets, so a linked home sale funds its replacement purchase without artificially draining Security. A positive net remainder, like positive standalone one-off cash, follows the configurable Security/Productive allocation after recovering any financing gap and remains capped by the Security target. If the resulting cash need cannot be funded, the remainder is exposed as negative `financing_gap`, included in projected liabilities and repaid by future free cash before new contributions.
5. An unregistered asset sale and every one-off expense sharing its `event_group` stay outside `one_off_flows` until the sale becomes a Decision. This keeps proceeds, disposal and transaction costs atomic.
6. `PATCH /api/plan/events/{id}/planned-decision/` edits the date, transaction month/year and projected impact while a decision is still `planned`. Grouped decisions preserve their adopted rows and links; one-event accepted scenarios update their source and regenerate only their managed future rows. Both paths recalculate the official projection transactionally.
7. `POST /api/plan/events/planned-decision/preview/` is an ephemeral comparison for the create/edit forms. It persists neither a `PlanEvent` nor budget rows or snapshots: for a creation it excludes the selected one-off rows before applying the candidate event, and for an edit it replaces the existing event only in the projection inputs. It returns the current/candidate trajectories and their sustainable-year delta.
7. Mortgage cancellation forecasts respect the liability's source of truth. For `tracking_mode=accounting`, the cancellation principal starts from the effective ledger balance today and applies only the remaining budgeted installments through the configured cancellation month; it never rebuilds the historical loan from a stale manual principal. Manual liabilities retain the amortization-schedule estimate.

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
2. `FoundationService` ports the former frontend guide diagnostics into backend-owned metrics: cash flow, emergency fund, debt, net-worth health, planned contribution and data quality. Each scored block also publishes a product `status` band (`good` >= 70, `warning` >= 40, `critical` below) and an A-E `grade` (`A` >= 85, `B` >= 70, `C` >= 55, `D` >= 40, `E` below), both computed from the rounded score, so clients color and grade the diagnosis without owning thresholds. Debt service (`annual_debt_service`, `debt_payment_to_income`) counts **only commitments generated by a liability** (`source_liability`), not every temporary commitment: instalments of a purchase or a treatment with an end date are not debt, and counting them took a real pilot from 18.5% to 48.9% effort. That ratio is now 20% of the debt score (floor 15%, zero at 40%), so cheap debt that still eats the salary no longer scores clean. The grade recovers the Guide v1 scale but is fitted to the current bands — A/B are `good`, C/D `warning`, E `critical` — so letter and colour can never contradict each other. `planned_contribution` is scored too (savings rate = planned contribution / structural income, floor 5%, target 20%), and the payload adds an `overall` block: the weighted average of the six foundations (cash flow .28, emergency fund .22, debt .18, planned contribution .14, net-worth health .10, data quality .08) with the same score/status/grade shape, so a client can headline "health: C" instead of counting amber blocks. Emergency-fund eligible liquidity counts **cash and deposits only** (liquid investments such as funds/ETFs/stocks/crypto are sellable but are not the cushion), and its score is *only* coverage against **its own target** (`EMERGENCY_TARGET_MONTHS`, 6 months, floor at half the target): committed-expense coverage is published as detail but not averaged in (the cash-flow foundation already grades the squeeze) and liquidity-over-assets moved out (it is diversification, graded by net-worth health). All foundation metrics read **effective** asset/liability amounts (`get_effective_asset_amount` / `get_effective_liability_amount`, the same source as the plan's classification and as Patrimonio), not the raw `amount` column, which was stale for positions kept by accounting or valuations. Quality factors about people (`pensions`, `employment_income_end_dates`) look at **the plan's adults**, not every adult in the family: the setup leaves unlinked provisional identities behind, and those kept flagging data that was already complete. The data-quality block reuses `DataQualityService` (the same factor set that grades the projection) instead of a separate shallow checklist.
3. `FindingService` evaluates deterministic MVP findings from those foundations and the expected projection. Resolved findings are closed instead of duplicated.
4. `RecommendationService` generates deterministic template-based actions with full explanation payloads (`action_json`, `impact_json`, `alternatives_json`). Refresh preserves accepted, dismissed and future-snoozed states. Negative committed cash flow produces `RESTORE_CASH_FLOW` before any contribution increase.
5. Recommendation preview calculates the current and simulated projections without creating a scenario, snapshot or budget row. Contribution recommendations are constrained by the available cash-flow margin, deferred until temporary commitments recover when needed, accept amount/date overrides in preview and simulation, and are omitted when the proposed event produces no projection change. Simulation creates a draft `Scenario` linked through `source_recommendation`; the recommendation becomes accepted only when that scenario is incorporated.
6. `MonthlyClosePlanService` is invoked after monthly-close finalization. It is a no-op when the user has no financial plan and logs failures without breaking the monthly-close lifecycle.
7. Monthly-close plan impact exposes at most two open findings and one open recommendation. Projected-year deltas are only communicated when the rounded year change is material (`abs(delta) >= 1`).
8. The plan engine has one active fiscal-year window: the current natural year, resolved by `plan_fiscal_year()`. Foundations, structural income, and budget-based contributions never aggregate rows from different fiscal years.
9. Structural income excludes one-off rows. One-off income is not converted into recurring labour income or capital automatically in the MVP; future capital effects require an explicit plan event.
10. Structural labour income stops at `FinancialPlan.target_date`, the date when work is expected to become optional. Pension starts independently on each adult's configurable `pension_start_date`; age 67 is only the initial default.
11. Expense inputs use one exhaustive role-based classifier shared by foundations and projection: operating, temporary commitment, contribution, asset purchase, tax/other, or unclassifiable. Unknown values are surfaced through data quality instead of disappearing silently.
12. Scenario contributions carry `monthly_contribution_destination=productive|security|debt`; only productive contributions compound as productive capital.

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
