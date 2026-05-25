# Core UI Extraction Candidates

_Documentary closing date: 2026-03-19_

This document records Core frontend areas that are clean enough to extract into
internal reusable modules later. It does not define a separate product or a
cross-repository contract.

## Context

The structural frontend refactor is closed. The resulting domain boundaries are
useful inside Core because they make each screen easier to test, maintain, and
incrementally improve.

## Candidates

| Domain | Status | Reason |
|--------|--------|--------|
| `net-worth` | Ready | Domain structure is separated and dependencies are narrow. |
| `people` | Ready | Components and composables are cohesive. |
| `guide` | Ready | Calculations and view state are isolated from routing. |
| `ui` | Ready | Shared visual primitives are reused across screens. |
| `budget` | Later | Larger surface; extract only after future budget changes settle. |

## Not Extraction Targets

| Element | Reason |
|---------|--------|
| `auth` | It owns application session behavior. |
| `capabilities` | It represents product packaging decisions inside Core. |
| `lib/api.ts` | It owns the runtime HTTP client contract. |

## Rules

1. Keep domain boundaries stable before extracting reusable code.
2. Extract pure helpers and visual primitives before stateful composables.
3. Avoid extraction unless it reduces real duplication or testing friction.
4. Keep functional delivery ahead of symmetry work.

## Next Steps

1. Maintain the current Core domain structure.
2. Revisit extraction only when a concrete feature creates repeated UI or logic.
3. Track follow-up work in `docs/roadmap/frontend-maintainability-backlog.md`.
