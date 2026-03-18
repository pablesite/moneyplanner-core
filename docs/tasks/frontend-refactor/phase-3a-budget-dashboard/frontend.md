# Task: Frontend Refactor — Fase 3a: Descomposición de BudgetDashboardView

## Context
`BudgetDashboardView.vue` tiene 5,512 líneas y es la vista más grande del frontend. Mezcla
modo presupuesto anual, modo cierre mensual, ledger coverage, check-ins de ingresos/gastos/
liquidez y sugerencias derivadas del ledger en un único archivo sin fronteras claras. Esta
fase la descompone en composables de página y secciones sin cambiar ningún comportamiento.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Extraer composables de página para filtros, fetch y acciones del presupuesto.
2. Crear componentes de sección para los bloques principales.
3. Reducir la vista al wiring de secciones (objetivo: < 400 líneas).
4. Tests unitarios para los composables extraídos (≥80% cobertura).

**Out of scope:**
1. Cambios de comportamiento o lógica de negocio.
2. Modificaciones de contratos con el backend.
3. Rediseño de UI.

## Plan

### Diagnosis
1. Leer `BudgetDashboardView.vue` completo. Identificar:
   - Bloques de template claramente separables (modo anual, modo cierre, check-ins, sugerencias)
   - Lógica de fetch y estado (qué APIs llama, qué stores usa)
   - Side effects y acciones de usuario
   - Derivadas computadas complejas
2. Mapear qué props/datos comparten las secciones entre sí.

### Change implementation
1. **Composable principal de página:** `domains/budget/composables/useBudgetDashboard.ts`
   - fetch de datos del presupuesto
   - estado de filtros (año, mes activo, modo)
   - acciones de usuario (cambiar modo, actualizar check-in)
   - derivadas complejas (cobertura del ledger, sugerencias)

2. **Secciones como componentes:**
   - `BudgetAnnualSection.vue` — modo presupuesto anual
   - `BudgetMonthlyClosure.vue` — modo cierre mensual
   - `BudgetCheckins.vue` — check-ins ingresos/gastos/liquidez
   - `BudgetLedgerSuggestions.vue` — sugerencias derivadas del ledger
   Cada componente recibe datos y emite acciones vía props/emits; sin acceso directo a stores.

3. **Vista resultante** (`BudgetDashboardView.vue`):
   - Instancia `useBudgetDashboard()`
   - Renderiza las secciones pasando los datos como props
   - Sin fetch directo, sin derivadas complejas, sin imports de `@/lib/api`

4. **Tests:**
   - `domains/budget/__tests__/useBudgetDashboard.spec.ts` — comportamiento del composable
   - Tests para cada sección si tiene lógica propia relevante

### SaaS Replication
Aplicar los mismos cambios en `frontend/` SaaS. Esta vista no tiene diferencias entre Core
y SaaS, por lo que la replicación es directa.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas; BudgetDashboardView <400 líneas

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
```

## Required Documentation Updates
- [ ] `core/docs/roadmap/frontend-refactor-roadmap.md` — actualizar estado Fase 3a
- [ ] `core/docs/project-status.md` — marcar Fase 3a como completada

## Risks
- **Riesgo:** esta es la vista más grande y compleja; puede haber dependencias cruzadas ocultas.
  **Mitigación:** extraer un composable a la vez, ejecutar typecheck después de cada extracción.
- **Riesgo:** los check-ins y el modo cierre pueden compartir estado; una extracción incorrecta
  puede romper la reactividad de Vue.
  **Mitigación:** mapear el grafo de dependencias reactivas antes de mover nada; probar en browser.

## Completion Criteria
- [ ] `BudgetDashboardView.vue` < 400 líneas (wiring + composición de página)
- [ ] Composables extraídos con tests ≥80% cobertura
- [ ] Sin cambios de comportamiento observados en browser
- [ ] `lint`, `typecheck`, `test:coverage` ≥80% en verde — Core y SaaS
- [ ] Documentación requerida actualizada
- [ ] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits)
