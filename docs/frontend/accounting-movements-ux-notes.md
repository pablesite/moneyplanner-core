# Accounting Movements UX

## Objective
Describe the target UX for daily movements in Core and how it should coexist with current budget, monthly close, and net-worth workflows.

## Experience rule
1. There is one movement flow, not multiple user-profile flows.
2. Complexity is revealed through progressive disclosure.
3. The product should stay usable for low-detail users while remaining operational for detailed users.
4. `tracking_mode` and context determine how much accounting detail is shown.

## Visible form modes
1. Basic mode
   - date
   - amount
   - source/destination account or main account
   - transaction type
   - category
   - note
2. Advanced mode
   - split entries
   - counterpart position
   - debt principal vs interest breakdown
   - tags, metadata, and accounting-specific adjustments

## Required flows
1. Income to liquidity
   - manual inflow into a liquidity account
   - category and note captured in the same fast form
2. Expense from liquidity
   - manual outflow from a liquidity account
   - category and note captured without forcing advanced mode
3. Transfer between accounts
   - explicit account-to-account flow
   - should not be represented as income plus expense
4. Investment flow
   - one visible investment type with direction selector: `Aporte` or `Desinversion`
   - `Aporte`: money leaves liquidity and lands in the investment counterpart
   - `Desinversion`: money leaves the investment counterpart and lands in liquidity
   - should remain understandable from both movement history and position detail
5. Debt payment with principal and interest
   - one user action
   - clearly separates liability reduction from financing cost

## Current quick-entry coverage (2026-03-15)
1. `income`, `expense`, `transfer`
2. `investment` with explicit `inflow` / `outflow` direction and liquidity-to-investment counterpart
3. optional manual realized metadata for investment (`realized_cost_basis`, `realized_gain_loss`) without mandatory calculation
4. `debt_payment` with explicit `principal` + `interest` breakdown
5. edit flow supports changing investment direction while preserving a balanced entry
6. `adjustment` for reconciliation: the UI asks for target final balance and computes delta automatically before posting

## Integration with current screens
1. `DataInputView`
   - remains focused on annual planning data and supporting inputs
   - should not absorb daily accounting movements
2. `BudgetDashboardView`
   - should consume ledger execution when movement coverage exists
   - should fall back to existing execution and check-in data when coverage is partial or absent
   - should label the source row-by-row so the user can distinguish `Ledger` from `Fallback legacy`
   - should disable legacy edit actions on rows already covered by ledger
3. `NetWorthView`
   - positions in `tracking_mode=accounting` should show `Actividad contable`
   - the user should not be forced to leave the current workspace to inspect position activity

## States and UX edge cases
1. Partial coverage
   - the UI should say when only part of the month or only part of the position flow is covered by ledger data
   - the monthly-close workspace should keep editable fallback rows only where ledger coverage is absent
2. Legacy position without ledger
   - the UI should keep current event/checkpoint behavior without implying missing data
3. `tracking_mode=accounting` without linked account
   - the UI should show this as an actionable setup gap, not as silent zero activity
4. Unbalanced or invalid transaction
   - the UI should block save and explain the validation issue in-place

## Visual criteria
1. Fast manual-entry form must be visible without overwhelming secondary controls.
2. The movement list should be chronological and filterable.
3. Position-level accounting activity should appear as contextual detail, not as a disconnected sub-product.
4. Desktop should preserve strong hierarchy; mobile should keep the fast-entry path obvious.

## Implementation expectation
1. `frontend/src/domains/accounting/*`
2. `frontend/src/views/BudgetDashboardView.vue`
3. `frontend/src/views/NetWorthView.vue`

## View composition after refactor phase 3e (2026-03-19)
1. `AccountingMovementsView.vue` now acts as a thin page orchestrator.
2. Page state/fetch logic is centralized in `domains/accounting/useAccountingMovementsPage.ts`.
3. Main sections are split into focused components:
   - `AccountingMovementsHero.vue`
   - `AccountingAccountCatalog.vue`
   - `AccountingMovementsAllTransactions.vue`
   - `AccountingBalances.vue`
4. Accounting view styles are moved to `domains/accounting/styles/movements.css`.
5. Core keeps MoneyWiz unmapped categories support through `AccountingMovementsMoneyWizModal`.
6. SaaS mirrors the same structure but keeps the existing behavior difference (no unmapped section UI).

## Server pagination UX (2026-03-23)
1. The "Todos los movimientos" tab loads only the first page (`50`) on initial render.
2. "Cargar mas" requests the next page using `next_cursor` and appends rows without resetting scroll context.
3. Search input on "Todos" is debounced (`300ms`) before calling the backend.
4. Filters `kind`, `date_from`, `date_to` (and account when set) are now server-side and reset pagination.
5. The "N de M movimientos" label uses server `total_count` instead of local array length.
6. "Cuentas" tab uses server pagination by `account_id`; per-row `impactValue` and `tone` are still computed client-side.
7. Create/edit/delete/import mutations refresh current movement pages to keep visible data in sync.

## Pending compact-list adoption (2026-05-15)
1. Backend supports compact transaction pages through `include_entries=false`.
2. Frontend list-only and infinite-scroll requests should use `include_entries=false&include_total=false` when they do not render nested entry detail.
3. Detail/edit flows must keep the default full payload so forms still receive per-entry account, category, amount, and linked-position data.
4. The expected benefit is lower payload size and faster list refreshes; the backend measurement on 200-row pages reduced response bodies from roughly 289-309 KB to 106-118 KB.
5. Pending implementation: update the Core accounting domain client/store/composables to choose compact mode for list rendering and full mode for detail/edit.

## Shared scenarios that must stay consistent
1. Manual income to a liquidity account
2. Manual expense from a liquidity account
3. Transfer between two liquidity accounts
4. Investment flow with aporte / desinversion
5. Debt payment split into principal and interest
6. Monthly close with full ledger coverage
7. Monthly close with partial ledger coverage and legacy fallback
8. Asset or liability in `manual`
9. Asset or liability in `accounting`
