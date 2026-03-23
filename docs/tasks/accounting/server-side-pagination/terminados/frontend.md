# Title
Core + SaaS frontend — server-side pagination for transactions

## Context
Depends on: `server-side-pagination/backend.md`.

The frontend currently loads all transactions in a single API call, stores the full array in Pinia, and does filtering + slice-based pagination client-side. With the backend now providing cursor pagination and server-side filters, the frontend must switch to fetching pages on demand.

## Area
`frontend`

## Stack
`both` (Core + SaaS mirror)

## Scope

### In scope
1. Update API layer to use the new paginated endpoint and response envelope.
2. Update `LedgerTransaction` type with `activity_kind` field.
3. Refactor composable: replace client-side filtering/slicing with server-driven pagination for both "Todos" and "Cuentas" tabs.
4. Debounced text search (300ms) to avoid per-keystroke API calls.
5. Keep "Cuentas" tab `impactValue` calculation client-side (trivial once entries are present).
6. Remove store dependency on a full `transactions[]` array — transactions are now request-scoped.
7. Update Vue components to use new data sources and show `total_count`.
8. Mirror all changes Core → SaaS (excluding `revaluation` kind in SaaS).

### Out of scope
1. Backend changes (separate spec).
2. Monthly summary, account balances, or other non-transaction endpoints.
3. Activation modal, quick entry modal, edit transaction modal — no changes needed.

## Plan

### 1. Diagnosis
1. Review `core/frontend/src/domains/accounting/api.ts` — current `getTransactions` signature.
2. Review `core/frontend/src/domains/accounting/store.ts` — how `transactions` is stored and used.
3. Review `core/frontend/src/domains/accounting/composables.ts` — filtering chain: `filteredTransactions` → `todosRawTransactions` → `todosVisibleTransactions`, and `cuentasRawTransactions` → `cuentasVisibleTransactions`.
4. Identify all consumers of `store.transactions` and the computed properties that derive from it.

### 2. Implementation

#### 2.1 Models (`models.ts`, both stacks)
Add paginated response type:
```typescript
export type PaginatedTransactionsResponse = {
  results: LedgerTransaction[];
  next_cursor: string | null;
  total_count: number;
};
```
Add `activity_kind: string` to `LedgerTransaction`.

#### 2.2 API layer (`api.ts`, both stacks)
Update `getTransactions` to accept new params and return paginated response:
```typescript
getTransactions(params?: {
  year?: number; month?: number; status?: string;
  cursor?: string; page_size?: number;
  date_from?: string; date_to?: string;
  account_id?: number; query?: string; kind?: string;
})
```

#### 2.3 Store (`store.ts`, both stacks)
- Remove `transactions: LedgerTransaction[]` from global state.
- Remove `transactions` from `refreshAll()`.
- Add a `fetchTransactionsPage(params)` action that calls the API and returns the paginated response without storing it.
- Keep `accounts`, `monthlySummary`, `accountBalancesSummary` in the store (small, used globally).

#### 2.4 Composable — "Todos" tab (`composables.ts`, both stacks)
Replace the in-memory filtering chain with server-driven pagination:
- New reactive state: `todosTransactions`, `todosNextCursor`, `todosTotalCount`, `todosLoading`.
- `fetchTodosPage(reset)`: builds params from `activityFilters` + date range, calls API, appends or replaces results.
- `loadMoreTodos()`: calls `fetchTodosPage(false)` if `todosNextCursor` is not null.
- `todosHasMore`: `computed(() => todosNextCursor.value !== null)`.
- Debounced watcher on `[activityFilters.query, activityFilters.kind, todosDateFrom, todosDateTo]` that calls `fetchTodosPage(true)` with 300ms debounce on text, immediate on the rest.
- Remove: `filteredTransactions`, `todosRawTransactions`, `todosVisibleTransactions`, `todosVisibleCount` computed properties.

#### 2.5 Composable — "Cuentas" tab (`composables.ts`, both stacks)
Same pattern:
- New reactive state: `cuentasTransactions`, `cuentasNextCursor`, `cuentasTotalCount`.
- `fetchCuentasPage(reset)`: params include `account_id`, date range. After fetch, enrich each transaction with `impactValue` and `tone` client-side (same existing logic).
- Watcher on `[cuentasSelectedAccountId, cuentasDateFrom, cuentasDateTo]` calls `fetchCuentasPage(true)`.
- Remove: `cuentasRawTransactions`, `cuentasVisibleTransactions`, `cuentasVisibleCount`.

#### 2.6 Simplify `getTransactionActivityKind`
Replace client-side classification with server-provided field:
```typescript
function getTransactionActivityKind(t: LedgerTransaction) {
  return t.activity_kind ?? 'other';
}
```

#### 2.7 Mutation reload
After create/update/delete transaction or MoneyWiz import commit:
- Call `fetchTodosPage(true)` to reset from scratch.
- If Cuentas tab has a selected account, also call `fetchCuentasPage(true)`.
- Reload monthly summary and account balances as before.

#### 2.8 Vue components (both stacks)

**`AccountingMovementsAllTransactions.vue`:**
- Replace `state.todosVisibleTransactions` → `state.todosTransactions`.
- Replace `state.todosRawTransactions.length` → `state.todosTotalCount` in the "N de M" display.
- Show spinner during `state.todosLoading`.
- "Cargar mas" checks `state.todosHasMore`.

**`AccountingAccountCatalog.vue`:**
- Same pattern for Cuentas tab: replace computed slices with server-fetched arrays.
- Show `state.cuentasTotalCount`.

### 3. Validation
Run lint and typecheck in both stacks.

## Validation
- `docker compose -f core/docker-compose.yml exec frontend npm run lint`
- `docker compose -f core/docker-compose.yml exec frontend npm run format:check`
- `docker compose -f core/docker-compose.yml exec frontend npm run typecheck`
- `docker compose exec saas_frontend npm run lint`
- `docker compose exec saas_frontend npm run format:check`
- `docker compose exec saas_frontend npm run typecheck`

## Required Documentation Updates
- [ ] `core/docs/frontend/accounting-movements-ux-notes.md` — document the new pagination UX: initial load, load-more, debounced search.
- [ ] `core/docs/project-status.md` — reflect task status.
- [ ] `docs/frontend/domain-map.md` — update if composable exports change.

## Risks
1. **Race conditions on rapid filter changes**: Multiple in-flight requests could resolve out of order. Mitigation: use an `AbortController` per fetch; cancel the previous request when a new one starts.
2. **Debounce UX**: 300ms debounce on text search may feel laggy. Can be tuned after testing.
3. **Store consumers**: Other parts of the app that read `store.transactions` directly (e.g., MoneyWiz import auto-matching) will need adjustment. Mitigation: audit all `store.transactions` references during diagnosis. The auto-matching uses `accounts`, not `transactions`, so impact should be minimal.

## Completion Criteria
- [ ] All validation commands pass (both stacks)
- [ ] Initial page load fetches only 50 transactions (verify via network tab)
- [ ] "Cargar mas" fetches next page from server
- [ ] Text search triggers server-side filter with debounce
- [ ] Kind, account, date range filters work server-side
- [ ] "Cuentas" tab shows per-account transactions with correct impact values
- [ ] "N de M movimientos" shows `total_count` from server
- [ ] Creating/editing/deleting a transaction refreshes the visible list
- [ ] SaaS frontend mirrors all changes
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
