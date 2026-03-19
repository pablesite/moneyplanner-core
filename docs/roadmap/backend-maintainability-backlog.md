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
4. Add performance tests for `build_monthly_accounting_summary` with high entry volume.
5. Measure and document latency baseline for critical `accounting`, `budget`, and `net_worth` endpoints.
6. Evaluate additional partition opportunities only when agreed complexity thresholds are exceeded.

## Validation rule
Any follow-up change must be validated in Docker with the standard Core backend quality and test matrix.
