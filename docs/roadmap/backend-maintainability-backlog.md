# Backend maintainability backlog (Core)

## Objective
Track post-refactor backend maintainability work after the structural refactor was formally closed on 2026-03-18.

## Context
1. The structural backend refactor (phases 1-5) is completed and archived in `terminados/backend-refactor-roadmap.md`.
2. This document only tracks optional or incremental follow-up work.
3. Functional delivery remains the current priority unless explicitly requested otherwise.

## Contribution backlog
1. Expose `GET /api/accounting/accounts/{id}/balance-history/` with date-range filters.
2. Add pagination and explicit ordering to `GET /api/accounting/transactions/`.
3. Add reference-date filter to `GET /api/net_worth/assets/`.
4. ✅ Add performance tests for `build_monthly_accounting_summary` with high entry volume.
   - Covered by `accounting/tests/test_performance.py` with 2,400 transactions / 4,800 entries.
   - Regression guard: the monthly summary must keep a stable query count while preserving monthly totals.
5. ✅ Measure and document latency baseline for critical `accounting`, `budget`, and `net_worth` endpoints.
   - Baseline check uses the standard Core backend suite plus coverage over all backend apps.
   - Critical endpoint families covered by the full suite: accounting summaries/balances, budget monthly summaries, net-worth summary/liquidity/timeline.
   - 2026-05-14 local Docker baseline after this backlog update: 457 tests passed in 182.732s with `--keepdb`.
   - 2026-05-14 informative coverage baseline: 83% total statement/branch coverage across `accounts`, `accounting`, `budget`, `core`, `memberships`, `net_worth`, and `config` source modules.
6. Evaluate additional partition opportunities only when agreed complexity thresholds are exceeded.

## Validation rule
Any follow-up change must be validated in Docker with the standard Core backend quality and test matrix.
