# Frontend maintainability backlog (Core)

## Objective
Track post-refactor frontend maintainability work after the structural refactor was formally closed on 2026-03-19.

## Context
1. The structural frontend refactor is completed and archived in `terminados/frontend-refactor-roadmap.md`.
2. This document only tracks optional or incremental follow-up work.
3. Functional delivery remains the current priority unless explicitly requested otherwise.

## Contribution backlog
1. Evaluate whether any shared UI primitives from `shared-package-candidates.md` should be extracted first, starting with low-risk helpers.
2. Review residual CSS consolidation opportunities in `app.css` only when they reduce duplication across multiple screens.
3. Measure whether the remaining `lib/` and domain boundaries justify additional cleanup, keeping the current frontend contracts stable.
4. Add focused regression coverage for any future shell or domain composable changes that reopen high-risk paths.
5. Document any new frontend latency, bundle-size, or maintainability regressions only when they are backed by evidence.
6. Consider further extraction work only when there is a clear product or DX benefit, not for symmetry alone.

## Validation rule
Any follow-up change must be validated in Docker with the standard Core frontend quality and test matrix.
