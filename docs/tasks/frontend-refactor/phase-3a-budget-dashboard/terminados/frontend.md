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
1. Extraer secciones y componentes de dominio para los bloques principales del dashboard.
2. Aislar el CSS específico del dashboard fuera de la vista principal.
3. Reducir la vista al wiring de secciones y a la orquestación reactiva principal (objetivo práctico: < 2,500 líneas).
4. Mantener validación dirigida de la vista y checks de regresión en ambos stacks.

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
1. **Secciones como componentes:**
   - `BudgetAnnualSection.vue` — modo presupuesto anual
   - `BudgetMonthlyCloseLiquiditySection.vue`
   - `BudgetMonthlyCloseIncomeSection.vue`
   - `BudgetMonthlyCloseExpenseSection.vue`
   - `BudgetMonthlyCloseResultSection.vue`
   Cada componente recibe datos y emite acciones vía props/emits; sin acceso directo a stores.

2. **Vista resultante** (`BudgetDashboardView.vue`):
   - Orquesta secciones y estado reactivo principal
   - Reutiliza estilos del dominio desde `domains/budget/styles/dashboard.css`
   - Reduce el markup inline del dashboard sin cambiar contratos con backend

3. **Tests:**
   - mantener `BudgetDashboardView.spec.ts` como smoke dirigido
   - ejecutar lint/typecheck y test dirigido en Core y SaaS tras cada corte relevante

### SaaS Replication
Aplicar los mismos cambios en `frontend/` SaaS. Esta vista no tiene diferencias entre Core
y SaaS, por lo que la replicación es directa.

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
- [ ] `core/docs/roadmap/terminados/frontend-refactor-roadmap.md` — actualizar estado Fase 3a
- [ ] `core/docs/project-status.md` — marcar Fase 3a como completada

## Risks
- **Riesgo:** esta es la vista más grande y compleja; puede haber dependencias cruzadas ocultas.
  **Mitigación:** extraer un composable a la vez, ejecutar typecheck después de cada extracción.
- **Riesgo:** los check-ins y el modo cierre pueden compartir estado; una extracción incorrecta
  puede romper la reactividad de Vue.
  **Mitigación:** mapear el grafo de dependencias reactivas antes de mover nada; probar en browser.

## Completion Criteria
- [x] `BudgetDashboardView.vue` reducida desde 5,512 a 2,362 líneas, con secciones y estilos del dominio extraídos
- [x] Secciones principales del dashboard anual y del cierre mensual extraídas a componentes
- [ ] Sin cambios de comportamiento observados en browser
- [x] `lint`, `typecheck` y test dirigido de `BudgetDashboardView` en verde — Core y SaaS
- [x] Documentación requerida actualizada
- [x] Spec movida a `terminados/`
- [x] Commit creado (Conventional Commits)

## Resultado de cierre

La fase 3a se considera completada a nivel estructural:

1. `BudgetDashboardView.vue` dejó de concentrar el CSS propio del dominio y los bloques grandes de template.
2. El dashboard anual y las cuatro etapas del cierre mensual quedaron encapsulados en componentes del dominio.
3. La cobertura global `>=80%` sigue siendo una responsabilidad transversal de la Fase 0 y no se redefine aquí.

