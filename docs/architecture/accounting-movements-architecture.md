# Accounting Movements Architecture

## Objective
Define the Core-owned architecture for daily movements and the new `accounting` domain.

## Related roadmap note
1. The specific implementation handoff for separating accounting account, category/subcategory, and annual budget line lives in `../roadmap/terminados/accounting-category-budget-separation-roadmap.md` (completed).
2. That roadmap refines the execution-vs-plan boundary without changing Core ownership: `accounting` owns execution and movement classification, while `budget` remains the annual planning layer.

## Recurring-income ownership source

1. Monthly ownership allocation reads executed income from `LedgerEntry`, not annual budget values.
2. An eligible row belongs to a `posted` `LedgerTransaction`, has `flow_family=income`, matches an
   explicit category/subcategory rule and has an individual transaction `ownership` for a member of
   the shared ownership being resolved.
3. The transaction ownership is the economic owner of the income. The ownership of the receiving
   cash account does not reclassify it, so an individual salary paid into a shared account remains
   individual income.
4. The resolver signs classified entries and transaction update timestamps into a source hash, uses
   booking-date FX, and freezes the resulting allocation separately from the ledger.

## Settlement participating accounts

1. Settlement account configuration references Net Worth assets; it does not create a second ledger
   account catalogue or alter `LedgerAccount` balances.
2. Operating and personal destinations represent liquidity. Allocation destinations may reference
   an investment asset whose ownership matches the planned obligation.
3. `Asset.Subcategory.WALLET` is physical cash only after activation. Its accepted physical balance
   overrides the settlement opening baseline, not the asset or past ledger; signed zero-sum opening
   adjustments preserve prior member compensation separately.
4. Account ownership continues to come from `OwnershipLink`. A budget route is ready only when its
   destination vector equals the expense ownership vector for the target month.
5. A posted external income/expense changes the economic position with the transaction ownership,
   regardless of the ownership of the physical account entry. The difference is exposed as a
   transaction-traced member compensation.
6. Transfers whose asset entries remain inside the configured perimeter never create household or
   member income/expense. They only change physical location and therefore the transfer routes still
   required at close. Transfers that cross the perimeter block an exact preview instead of being
   guessed from the liquidity delta.
7. The close payload exposes each member's opening, classified income, classified expense,
   compensation, next-period requirement, closing position and excess. Compensation is explanatory
   location evidence and is not added again to the economic closing equation.
8. Applied settlement routes are ordinary posted double-entry transfers with `origin=system`,
   `quick_entry_kind=transfer`, route ownership and an explicit recommendation FK. Their entries have
   no income/expense flow family, so household and member economic totals remain unchanged.
9. `settlement_idempotency_key` is unique per user when present. `settlement_action` distinguishes
   application, reconciliation and reversal, while `settlement_amount` preserves the amount applied
   by each linked movement. A reversal adds the opposite transfer and never deletes history.

## Problem to solve
Core already has useful but separate execution layers:
1. annual budget entries and monthly check-ins
2. net-worth events split by position type
3. liquidity monthly closing balances

This leaves a gap:
1. there is no shared book of daily movements
2. liquidity, investment, debt, and patrimonial purchases do not yet converge on one operational model
3. monthly close can reconcile results, but not derive them from a common transactional layer

## Principles
1. `accounting` belongs to Core, not to Core.
2. The domain starts with double-entry bookkeeping semantics.
3. Legacy net-worth event models can coexist while the new domain is rolled out.
4. `tracking_mode` remains the main complexity control for positions.
5. Rollout must happen in small phases without breaking `budget`, `net_worth`, or `monthly close`.
6. Positions in `tracking_mode=accounting` must end with an operational `LedgerAccount` link, including pre-existing rows in `net_worth`.

## Conceptual model v1
1. `LedgerTransaction`
   - user-owned transactional envelope
   - booking/value dates, description, status, origin, notes
   - optional movement-level ownership link for individual/shared attribution
   - can represent simple flows, transfers, debt payments, and patrimonial purchases
2. `LedgerEntry`
   - belongs to one `LedgerTransaction`
   - points to one `LedgerAccount`
   - stores side, amount, currency, and optional classification metadata
   - may keep optional links to `Asset` or `Liability`
   - does not link to concrete annual budget rows; budget execution is derived by month + functional taxonomy
3. `LedgerAccount`
   - user-owned operational account
   - can be backed by an `Asset`, a `Liability`, or a system/virtual account
   - will be the balance source for positions tracked through accounting

## Relationships with current domains
1. `Asset`
   - cash and investment assets in `tracking_mode=accounting` should map to a `LedgerAccount`
   - purchases of other assets can be represented as liquidity outflow plus patrimonial counterpart entry
2. `Liability`
   - liabilities in `tracking_mode=accounting` should map to a `LedgerAccount`
   - debt payment flows should separate principal from interest/fees
3. `AnnualIncomeEntry`
   - remains planning data in v1
   - receives executed figures from ledger rows with matching `flow_family/category_key/subcategory_key` and month
4. `AnnualExpenseEntry`
   - remains planning data in v1
   - receives executed figures from ledger rows with matching `flow_family/category_key/subcategory_key` and month

## Portfolio boundary

1. `portfolio` references `LedgerAccount` and `LedgerTransaction`; it never duplicates accounts, entries, balances or monetary movements.
2. A `PortfolioPosition` may retain the unique asset-type `LedgerAccount` already linked through `LedgerAccount.asset`. If no compatible account exists, or several candidates exist, bootstrap leaves the link empty and emits a migration issue instead of creating or choosing one.
3. `Asset` remains the patrimonial identity and current net-worth boundary. Portfolio adds container, instrument, tracking style and dated ownership semantics around that same asset.
4. Performance coverage reads posted transactions with `quick_entry_kind=investment` plus legacy `InvestmentAssetEvent` and `AssetValuation`. It interprets a legacy bank-to-asset transfer as a funded purchase without rewriting the transaction, and never treats revaluation rows as external flows.
5. `PortfolioTrade` stores execution metadata linked to `LedgerTransaction`; the ledger remains the sole monetary source of truth. A purchase moves posted cash from the position's own container to its linked asset account, and an optional fee is a separate expense transaction.
6. Direct operation confirmation requires a signed preview of the unchanged payload. CSV imports stage and validate rows first, use the same atomic operation service, preserve import origin/fingerprint, reject duplicate external identifiers and never edit pre-existing ledger rows.
7. `PortfolioCorporateAction` retains split, identifier-change, position-transfer and audited-adjustment evidence. Archive/reopen changes position and asset availability only; all ledger, trade and action history remains intact.
8. A **manual** valuation states what the position is worth, so it also posts a `quick_entry_kind=revaluation` transaction for the delta between the declared value and the position account balance at that date, against the system `Revalorizaciones` account. This keeps Cartera, Patrimonio and Movimientos on the same number; without it the three diverge, because net worth anchors investment assets on the ledger balance. The delta is idempotent: re-confirming the same value posts nothing. Valuation stays analytic (no entry) when the position has no linked ledger account or the valuation currency differs from the account currency, and `operations/preview/` reports that as `ledger_effect.syncs_accounting=false` with a reason.
9. **Automatic** prices (`InstrumentPrice`, units × close) never post entries. They are analytic valuation only; posting them would add a revaluation per position per trading day.
10. The reverse direction is live: saving or deleting a posted `revaluation` transaction resyncs the derived `PositionValuation` of every position linked to its accounts, on commit. Cartera no longer waits for a bootstrap to notice a revaluation booked in Movimientos. `sync_ledger_valuations` re-imports the position and prunes derived rows that no longer match a posted revaluation on the same date, so amount, date and kind changes converge; manual valuations are never touched and keep precedence on a tie.
11. `PositionValuation.legacy_ledger_transaction` cascades. A derived valuation is a projection of the ledger and must not block deleting its own source; before this it raised `ProtectedError` and made every derived revaluation undeletable from Movimientos.
12. A **value-based** position with no valuation of any kind falls back to its posted ledger balance as carrying value, with provenance `ledger_balance` (`ledger:balance` on the performance path) and `observed_on` set to the last date the balance moved, so freshness stays honest. Contributions and income are flows, not valuations, so a position funded only through accounting used to report no value at all and drop out of the portfolio total. Units-based positions are excluded: their account holds units, not money. Both read paths implement this — `valuations.resolve_position_valuation` and `performance.resolve_preloaded_value` — and must stay in agreement.
13. Signals only cover changes made through the ORM. Data that reaches the database underneath it (a restore, a bulk load) fires nothing, so `POST /api/portfolio/positions/resync-valuations/` is the explicit way out of that drift; `/cartera` exposes it as "Actualizar desde contabilidad".

## Behavioral rules
1. `tracking_mode=manual`
   - current manual valuations, events, and check-ins remain valid
   - balances are not derived from the ledger by default
2. `tracking_mode=accounting`
   - the linked account becomes the operational source for balance and execution flows
   - the position should expose accounting activity in addition to legacy views where relevant
   - if the position has no valid linked account, Core should try auto-linking or auto-creating a compatible `LedgerAccount`
   - the integration result should be explicit via one state: `linked`, `auto_created`, or `needs_review`
3. Liquidity balances
   - liquidity accounts tracked through accounting derive their closing balance from ledger entries
   - liquidity monthly check-ins stay as fallback and reconciliation support during transition
4. Investments
   - contributions, withdrawals, fees, and income should move toward transaction-driven activity
   - investment flows should be modeled as one bidirectional operation with explicit direction (`inflow` / `outflow`), not as unrelated income plus transfer shortcuts
   - quick-entry uses `movement_type=investment` plus explicit `investment_direction`
   - for cross-currency investment quick-entry, Core accepts `amount` as origin amount and `destination_amount` as destination amount (broker executed units/value); same-currency investment keeps `destination_amount` optional and defaults it to `amount`
   - realized metadata (`realized_cost_basis`, `realized_gain_loss`) is optional and manual in this phase; Core stores it but does not auto-calculate lots or fiscal impact
   - investment aggregates per asset account expose `investment_inflow_total`, `investment_outflow_total`, and `investment_net_contributed`
   - legacy investment events remain available until explicit replacement
5. Debt and patrimonial purchases
   - debt payment transactions should model principal and cost separately
   - purchases of real estate, furnishings, vehicles, or similar positions should be representable from liquidity to asset counterpart entries
6. Legacy status during transition
   - `LiquidityAssetEvent`, `InvestmentAssetEvent`, and `LiabilityEvent` remain active
   - they are compatibility layers, not the long-term primary execution model

## Net-worth integration contract (vNext target)
1. Functional contract
   - any `Asset` or `Liability` in `tracking_mode=accounting` must have an operational `LedgerAccount` (`asset` type for assets, `liability` type for liabilities)
   - if missing at runtime or on update, Core should auto-link first and auto-create second
2. Idempotency and safety rules
   - never duplicate accounts for the same position
   - preserve ownership (`user`) boundaries
   - preserve currency compatibility between position and account
   - preserve account-type compatibility (`asset` with `Asset`, `liability` with `Liability`)
3. Existing data policy
   - for pre-existing `net_worth` positions, attempt auto-linking via direct references
   - if no safe link exists, create a compatible account and persist the relation
   - if ownership/currency/type checks fail, do not force-link; mark the row as `needs_review`
4. Integration states
   - `linked`: position already had a valid compatible account
   - `auto_created`: position had no account and Core created + linked one
   - `needs_review`: Core could not safely link/create without violating compatibility rules

## Integration with current views
1. Net worth
   - positions in `tracking_mode=accounting` should expose accounting activity in the same contextual workspace
   - the net-worth view remains summary-first and position drilldown stays in place
2. Budget
   - annual budget remains the planning layer
   - executed monthly figures consume posted ledger aggregates by taxonomy and month
   - monthly summaries can mix ledger-backed execution and manual check-ins in the same month
3. Monthly close
   - monthly close uses ledger-derived liquidity and execution where `tracking_mode=accounting` or taxonomy coverage exists
   - manual check-ins remain fallback when coverage is partial or absent
   - historical closes must respect `as_of_date` instead of reading current live balances
   - precedence is explicit: use ledger first when the account link is valid and covered; fallback only when ledger coverage is unsafe or absent
   - settlement attributes realized income and expense from each posted transaction's ownership; annual budget rows remain aggregate forecasts and are not ownership-readiness inputs

## Transactions list API contract
1. `GET /api/accounting/transactions/` uses server-side cursor pagination with ordering `-booking_date, -id`.
2. Response envelope is:
   - `results`: serialized `LedgerTransaction[]`
   - `next_cursor`: opaque cursor (`null` when there are no more rows)
   - `total_count`: total rows for the active filter set (independent from current page), or `null` when `include_total=false`
3. Supported query params:
   - existing compatibility filters: `year`, `month`, `status`
   - pagination: `cursor`, `page_size` (default `50`, max `200`), `include_total` (default `true`), `include_entries` (default `true`)
   - server-side filters: `query`, `kind`, `account_id`, `date_from`, `date_to`
4. `LedgerTransaction` list payload includes `activity_kind` (read-only) resolved server-side from prefetched entries.
   - when `include_entries=false`, list rows omit the nested `entries` payload but keep transaction-level fields and `activity_kind`
   - consumers should use `include_entries=false&include_total=false` for infinite-scroll/list-only views that do not render entry-level detail
   - consumers should keep the default full payload for detail, edit, and any view that needs per-entry account/category data
5. Supported `kind` values: `income`, `expense`, `transfer`, `adjustment`, `investment`, `debt_payment`, `revaluation`.
6. Quick-entry supports `movement_type=adjustment` for reconciliation deltas:
   - only for operational accounts (`asset`/`liability`)
   - optional `counterparty_account_id`; if omitted, backend auto-creates/reuses a system equity account (`Ajustes de conciliacion`) in the same currency
   - `amount` can be positive or negative and is applied as a delta on the selected account
7. Operational review contract:
   - every serialized transaction exposes calculated `needs_review`; it is never persisted
   - income, expense, debt-payment and non-reinvestment investment rows need review when they have no complete functional classification (`flow_family`, `category_key`, `subcategory_key`)
   - transfers, adjustments, opening balances, revaluations and reinvestments never need functional review
   - the list accepts `review_state=needs_review|reviewed` and returns `needs_review_count` under the other active filters
8. Daily balance selection:
   - `daily-balance-series` accepts optional comma-separated `account_ids`
   - selected accounts must belong to the user, be active and use `asset` or `liability` account type
   - the returned `filters.account_ids` records the effective selection

## Rollout phases
1. Base module
   - create the `accounting` backend app and frontend domain
   - define core ledger entities and initial API surface
2. Liquidity plus simple income/expense
   - support daily inflows and outflows against liquidity accounts
   - support basic categorization for monthly execution
3. Internal transfers
   - support account-to-account transfers between liquidity accounts
   - keep transfer semantics explicit and balanced
4. Investment and debt flows
   - support bidirectional investment flows (`inflow` / `outflow`) between liquidity and investment accounts
   - support debt payments with principal and interest separation
5. Budget-derived aggregates
   - expose historical monthly aggregates and suggestion-ready series for planning

## Explicit assumptions
1. Firefly is only a conceptual reference for transaction and account modeling.
2. There is no Firefly import/export integration in v1.
3. There is no bulk automatic migration of legacy data in v1; integration is position-level with safe auto-link/auto-create rules.
4. The architecture document is the canonical functional source for this initiative.
