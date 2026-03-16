# Community Roadmap

## Objective
Consolidate a strong open-core base that is useful on its own and easy to improve with community help.

## Current Priorities
1. Stability and bug fixing in existing flows
2. Lower-friction data input UX
3. Quality through tests and validation
4. Backend refactoring in small maintainable phases
5. Accounting and daily-movement rollout in small phases without breaking net worth, budget, or monthly close
6. Documentation and contributor onboarding

## Roadmap Status
### Terminados
1. Accounting movements roadmap: `terminados/accounting-movements-roadmap.md`
   - Estado: terminado
   - Lectura: las fases 1-5 y la subfase 4b figuran como implementadas y cerradas.
   - Tasks asociadas terminadas:
     - `../tasks/accounting-movements/terminados/backend-foundation.md`
     - `../tasks/accounting-movements/terminados/frontend-foundation.md`
     - `../tasks/accounting-movements/terminados/qa-validation.md`
2. Market data sync roadmap: `terminados/market-data-sync-roadmap.md`
   - Estado: terminado
   - Lectura: el codigo, Docker, la UX observacional de `/data` y las docs operativas ya reflejan las fases 1-6 cerradas.

### Activos y a medio
1. Backend refactor roadmap: `backend-refactor-roadmap.md`
   - Estado: activo y a medio
   - Lectura: mantiene fases y checklist abiertos sobre hotspots reales del backend.
2. Accounting category-budget separation roadmap: `accounting-category-budget-separation-roadmap.md`
   - Estado: activo y a medio
   - Lectura: la fase 1 figura implementada y las fases 2+ siguen pendientes.

### Por empezar
1. Frontend refactor roadmap: `frontend-refactor-roadmap.md`
   - Estado: por empezar
   - Lectura: define baseline y fases, pero todavia no registra ejecucion cerrada.

## Product Areas In Evolution
1. Net worth
2. Budget and monthly close
3. Financial guide v1
4. Family and ownership
5. Financial simulator
6. Accounting
7. Investment portfolio
8. Market data and auxiliary datasets

## Good Contribution Candidates
1. Better empty states and error messages
2. Regression tests for critical flows
3. Accessibility and responsive improvements
4. Export/import validation improvements
5. Developer experience scripts and documentation
6. Small backend refactors preceded by tests

## Lower Priority For Now
1. Large new modules before stabilizing existing ones
2. Commercial packaging changes
3. Complex external integrations
4. Large refactors without clear quality or user impact
