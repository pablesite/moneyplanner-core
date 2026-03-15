# Title
Core accounting movements QA and regression validation

## Context
This task validates the new `accounting` initiative without allowing regressions in current Core budget, monthly close, and net-worth behavior.

The goal is to prove both the new contracts and the temporary coexistence between ledger-based execution and legacy flows.

## Scope
1. In scope
   - API contract coverage for `accounting`
   - regression checks in net worth
   - regression checks in monthly close
   - coexistence scenarios between legacy flows and ledger-based flows
2. Out of scope
   - external connector validation
   - non-Core SaaS packaging behavior

## Plan
1. Diagnosis
   - inspect affected test suites in `accounting`, `budget`, and `net_worth`
   - identify critical monthly-close and position-activity paths that must not regress
2. Change implementation
   - add or expand contract tests for `accounting`
   - add regression scenarios for monthly close and net worth integration points
   - document any known coverage gaps found during validation
3. Validation
   - run backend and frontend quality/test commands in Docker
   - confirm coexistence scenarios explicitly
4. Documentation update
   - update task notes or roadmap references only if validation reveals changes in agreed behavior
5. Version update (SemVer)
   - no version decision is made by QA alone; follow the release policy used by the implementing change

## Validation
List exact commands and expected outcomes.

1. `cd core`
2. `docker compose exec backend python manage.py test accounting`
3. `docker compose exec backend python manage.py test budget`
4. `docker compose exec backend python manage.py test net_worth`
5. `docker compose exec frontend npm run lint`
6. `docker compose exec frontend npm run format:check`
7. `docker compose exec frontend npm run typecheck`

Expected outcomes:
1. `accounting` API contracts are covered.
2. Monthly close keeps working with full ledger coverage and partial fallback coverage.
3. Net-worth position activity keeps working for both `manual` and `accounting` cases.

## Risks
Potential regressions and mitigation strategy.

1. Ledger and legacy flows can disagree on execution totals.
2. Net-worth activity views can regress when a position switches tracking mode.
3. Monthly close can silently mix incompatible data sources.

Mitigation:
1. Keep explicit coexistence scenarios in tests.
2. Validate both full and partial coverage paths.
3. Record any remaining blind spots as follow-up debt instead of assuming safety.

## Completion Criteria
Measurable DoD criteria for the task.

1. A scenario matrix covers API contracts, monthly close, and net-worth integration.
2. Validation evidence shows no regression in `monthly close` and `position activity`.
3. Affected backend and frontend validation commands pass.
