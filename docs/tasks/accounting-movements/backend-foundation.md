# Title
Core accounting movements backend foundation

## Context
This task creates the Core `accounting` domain baseline so daily movements can coexist with current `budget` and `net_worth` behavior.

It should establish the first reusable transactional layer without breaking current monthly close, check-ins, or net-worth flows.

## Scope
1. In scope
   - `LedgerTransaction`, `LedgerEntry`, and `LedgerAccount` models
   - serializers
   - initial CRUD API
   - base monthly aggregate support
2. Out of scope
   - external importers
   - automatic migration of legacy movement data
   - advanced multi-currency rules not required for v1

## Plan
1. Diagnosis
   - inspect current relationships with `Asset`, `Liability`, `AnnualIncomeEntry`, and `AnnualExpenseEntry`
   - confirm existing `tracking_mode` and monthly-close touchpoints before adding new models
2. Change implementation
   - add the `accounting` backend app and domain models
   - implement serializer validation for balanced transactions and account compatibility
   - wire initial API routes and user scoping
   - expose base monthly aggregate endpoints or services needed by later phases
3. Validation
   - run backend quality checks and domain tests in Docker
   - verify that existing `budget` and `net_worth` tests still pass where affected
4. Documentation update
   - keep architecture and roadmap docs aligned with any contract-level change
5. Version update (SemVer)
   - adjust Core version only if the feature scope delivered warrants it under the current release policy

## Validation
List exact commands and expected outcomes.

1. `cd core`
2. `docker compose exec backend ruff check .`
3. `docker compose exec backend ruff format --check .`
4. `docker compose exec backend mypy .`
5. `docker compose exec backend python manage.py test accounting`
6. `docker compose exec backend python manage.py test budget net_worth`

Expected outcomes:
1. Quality commands exit successfully.
2. `accounting` tests cover balanced transaction rules and API protection.
3. No regression appears in affected `budget` and `net_worth` suites.

## Risks
Potential regressions and mitigation strategy.

1. Transaction-balance bugs can create inconsistent account states.
2. New account links can conflict with existing `net_worth` derivation logic.
3. Monthly aggregate helpers can accidentally duplicate or diverge from current budget logic.

Mitigation:
1. Add model/service tests before broad API expansion.
2. Keep `tracking_mode=manual` behavior unchanged.
3. Validate affected legacy suites in the same PR.

## Completion Criteria
Measurable DoD criteria for the task.

1. Balanced transactions can be created and invalid unbalanced payloads are rejected.
2. Account balances are reproducible from persisted ledger entries.
3. Endpoints are authenticated and user-scoped.
4. Backend validation commands and tests pass in Docker.
