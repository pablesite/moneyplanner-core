# Title
Core accounting movements frontend foundation

## Context
This task introduces the first frontend layer for daily accounting movements in Core while preserving current `BudgetDashboardView`, `NetWorthView`, and data-input responsibilities.

It should make the new backend usable without forcing a full UX rewrite of existing financial flows.

## Scope
1. In scope
   - movement store
   - chronological movement list
   - fast manual entry
   - advanced form state
   - light integration with net worth or monthly close
2. Out of scope
   - bank import
   - advanced analytical dashboards
   - full replacement of `DataInputView`

## Plan
1. Diagnosis
   - inspect current `BudgetDashboardView`, `NetWorthView`, and existing domain-store patterns
   - confirm where `tracking_mode=accounting` should surface UI affordances
2. Change implementation
   - add `frontend/src/domains/accounting/*`
   - implement client models, API adapter, and store
   - add a basic list plus fast-entry flow
   - add advanced form support with progressive disclosure
   - integrate visible accounting activity into `NetWorthView` or ledger-backed execution into `BudgetDashboardView`
3. Validation
   - run frontend quality checks in Docker
   - verify no type regressions in touched views and stores
4. Documentation update
   - keep UX notes aligned if the implemented interaction model changes materially
5. Version update (SemVer)
   - adjust Core version only if the delivered user-facing scope requires it under the current release policy

## Validation
List exact commands and expected outcomes.

1. `cd core`
2. `docker compose exec frontend npm run lint`
3. `docker compose exec frontend npm run format:check`
4. `docker compose exec frontend npm run typecheck`

Expected outcomes:
1. Frontend quality commands exit successfully.
2. The movement UI can read backend `accounting` data.
3. At least one existing Core surface exposes visible accounting integration.

## Risks
Potential regressions and mitigation strategy.

1. The movement UI can become too complex for simple entry cases.
2. New domain state can drift from current Core store patterns.
3. Integration into net worth or monthly close can overload already dense screens.

Mitigation:
1. Keep fast-entry visible by default.
2. Use progressive disclosure for advanced controls.
3. Limit initial integration to one clear contextual block.

## Completion Criteria
Measurable DoD criteria for the task.

1. Basic movement create/edit flow works against the `accounting` backend.
2. Empty, loading, and error states are handled.
3. The frontend reads backend `accounting` resources through a dedicated domain layer.
4. Visible integration exists in `NetWorthView` or `BudgetDashboardView`.
