# Title
Core accounting movements QA and regression validation

## Context
This task validates the `net_worth` -> `accounting` integration contract for existing assets/liabilities in `tracking_mode=accounting`.

The goal is to prove auto-link/auto-create behavior, preserve safety (`needs_review` when auto-link is unsafe), and avoid regressions in monthly close and position activity.

## Scope
1. In scope
   - API and service contract coverage for integration states: `linked`, `auto_created`, `needs_review`
   - regression checks in `net_worth` and `monthly close`
   - coexistence and precedence checks (ledger first, legacy fallback only when ledger coverage is unsafe/absent)
2. Out of scope
   - external connector validation
   - non-Core Core packaging behavior

## Scenario Matrix (minimum)
1. Existing asset/liability without linked account
   - expected: auto-create compatible `LedgerAccount` and persist link (`auto_created`)
2. Existing asset/liability with valid `accounting_account_id`
   - expected: no new account created, existing link preserved (`linked`)
3. Invalid account candidate (foreign user, currency mismatch, type mismatch)
   - expected: do not force-link; mark as `needs_review`; keep explicit fallback behavior
4. Tracking mode switch `manual -> accounting`
   - expected: integration attempt creates or links account safely; no duplicate account
5. Tracking mode switch `accounting -> manual`
   - expected: legacy/manual behavior remains operational without breaking history
6. UI integration visibility
   - `NetWorthView`: integration state visible per position (`linked`, `auto_created`, `needs_review`)
   - `AccountingMovementsView`: selectable liquidity/account options reflect the resulting links

## Evidence Expected Per Scenario
1. API/service result
   - integration state and linked account identifier
2. Data integrity
   - no duplicate account for same position
   - ownership/currency/type constraints respected
3. User-visible behavior
   - UI state reflects integration result
   - fallback messaging appears only when `needs_review`
4. Regression safety
   - monthly close totals remain consistent with precedence rules

## Docker Validation Checklist
1. `cd core`
2. `docker compose exec backend ruff check .`
3. `docker compose exec backend mypy .`
4. `docker compose exec backend python manage.py test accounting --keepdb`
5. `docker compose exec backend python manage.py test net_worth --keepdb`
6. `docker compose exec backend python manage.py test budget --keepdb`
7. `docker compose exec frontend npm run lint`
8. `docker compose exec frontend npm run format:check`
9. `docker compose exec frontend npm run typecheck`
10. `docker compose exec frontend npm run test:unit -- src/views/__tests__/NetWorthView.spec.ts src/views/__tests__/AccountingMovementsView.spec.ts src/domains/accounting/__tests__/store.spec.ts src/views/__tests__/BudgetDashboardView.spec.ts`

Expected outcomes:
1. Integration scenarios above are covered with explicit assertions.
2. `monthly close` and `net worth` keep working with full ledger coverage and fallback only when coverage is unsafe/absent.
3. No duplicate account linkage is introduced by integration flows.

## Risks
1. Auto-create logic can accidentally create duplicate accounts for the same position.
2. Unsafe auto-linking can cross user/currency/type boundaries.
3. Precedence drift can mix ledger and legacy data inconsistently.

Mitigation:
1. Keep idempotency assertions in integration tests.
2. Keep negative-path tests for ownership/currency/type mismatches.
3. Keep explicit precedence assertions in `budget` and `net_worth` regressions.

## Completion Criteria
1. Scenario matrix is implemented in tests with evidence for API/service/UI outcomes.
2. Validation evidence shows no regression in `monthly close` and position activity.
3. Backend and frontend Docker commands for affected scope pass.
