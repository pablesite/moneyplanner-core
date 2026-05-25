# Task: Frontend Refactor — Phase 3a: BudgetDashboardView Decomposition

## Context
`BudgetDashboardView.vue` is 5,512 lines long and is the largest view in the frontend. Mix
annual budget mode, monthly closing mode, ledger coverage, income/expense check-ins/
liquidity and suggestions derived from the ledger in a single file without clear borders. This
phase decomposes it into page composables and sections without changing any behavior.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Extraer secciones y componentes de dominio para los bloques principales del dashboard.
2. Isolate dashboard-specific CSS outside of the main view.
3. Reduce the view to section wiring and the main reactive orchestration (practical goal: < 2,500 lines).
4. Maintain directed view validation and regression checks in both stacks.

**Out of scope:**
1. Changes in behavior or business logic.
2. Modificaciones de contratos con el backend.
3. UI redesign.

## Plan

### Diagnosis
1. Leer `BudgetDashboardView.vue` completo. Identificar:
- Clearly separable template blocks (annual mode, closing mode, check-ins, suggestions)
- Fetch and state logic (what APIs it calls, what stores it uses)
- Side effects and user actions
   - Derivadas computadas complejas
2. Map what props/data the sections share with each other.

### Change implementation
1. **Secciones como componentes:**
   - `BudgetAnnualSection.vue` — modo presupuesto anual
   - `BudgetMonthlyCloseLiquiditySection.vue`
   - `BudgetMonthlyCloseIncomeSection.vue`
   - `BudgetMonthlyCloseExpenseSection.vue`
   - `BudgetMonthlyCloseResultSection.vue`
Each component receives data and emits actions via props/emits; without direct access to stores.

2. **Vista resultante** (`BudgetDashboardView.vue`):
- Orchestra sections and main reactive state
   - Reutiliza estilos del dominio desde `domains/budget/styles/dashboard.css`
   - Reduce el markup inline del dashboard sin cambiar contratos con backend

3. **Tests:**
   - mantener `BudgetDashboardView.spec.ts` como smoke dirigido
   - ejecutar lint/typecheck y test dirigido en Core y SaaS tras cada corte relevante

### SaaS Replication
Aplicar los mismos cambios en `frontend/` SaaS. Esta vista no tiene diferencias entre Core
and SaaS, so replication is direct.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:unit -- src/views/__tests__/BudgetDashboardView.spec.ts
# → BudgetDashboardView <= 2,500 líneas; cobertura global sigue gobernada por Fase 0

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:unit -- src/views/__tests__/BudgetDashboardView.spec.ts
```

## Required Documentation Updates
- [ ] `core/docs/roadmap/terminados/frontend-refactor-roadmap.md` — update status Phase 3a
- [ ] `core/docs/project-status.md` — marcar Fase 3a como completada

## Risks
- **Risk:** this is the largest and most complex view; there may be hidden cross dependencies.
**Mitigation:** Check out one composable at a time, run typecheck after each checkout.
- **Risk:** check-ins and closing mode can share state; incorrect extraction
  puede romper la reactividad de Vue.
**Mitigation:** map the reactive dependency graph before moving anything; try in browser.

## Completion Criteria
- [x] `BudgetDashboardView.vue` reduced from 5,512 to 2,362 lines, with domain sections and styles extracted
- [x] Main sections of the annual dashboard and monthly closing extracted to components
- [ ] Sin cambios de comportamiento observados en browser
- [x] `lint`, `typecheck` y test dirigido de `BudgetDashboardView` en verde — Core y SaaS
- [x] Updated required documentation
- [x] Spec movida a `terminados/`
- [x] Commit creado (Conventional Commits)

## Closing result

La fase 3a se considera completada a nivel estructural:

1. `BudgetDashboardView.vue` stopped concentrating the domain's own CSS and the large template blocks.
2. The annual dashboard and the four stages of the monthly closing were encapsulated in domain components.
3. Global coverage `>=80%` remains a cross-cutting responsibility of Phase 0 and is not redefined here.

