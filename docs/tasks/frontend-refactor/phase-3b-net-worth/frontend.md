# Task: Frontend Refactor — Fase 3b: Descomposición de NetWorthView

## Context
`NetWorthView.vue` tiene 3,608 líneas y mezcla filtros de ownership, timeline de evolución,
analítica y ratios, detalle de posición y actividad ledger contextual en un único archivo.
Esta fase la descompone en composables de página y secciones sin cambiar comportamiento.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Extraer composables de página para fetch, filtros y derivadas de net worth.
2. Crear componentes de sección para los bloques principales.
3. Reducir la vista al wiring de secciones (objetivo: < 400 líneas).
4. Reubicar cálculos que hoy viven en la vista a composables del dominio `net-worth`.
5. Tests unitarios para los composables extraídos (≥80% cobertura).

**Out of scope:**
1. Cambios de comportamiento o lógica de negocio.
2. Modificaciones de contratos con el backend.
3. Rediseño de UI.

## Plan

### Diagnosis
1. Leer `NetWorthView.vue` completo. Identificar:
   - Bloques de template separables (filtros de ownership, timeline, analítica, detalle, actividad ledger)
   - Cálculos de ratios y derivadas (deben ir a `domains/net-worth/composables.ts` o composable de página)
   - APIs y stores que usa la vista
   - Dependencias reactivas entre secciones
2. Revisar `domains/net-worth/composables.ts` y `domains/net-worth/store.ts` actuales para
   entender qué ya existe y qué hay que extraer.

### Change implementation
1. **Composable principal de página:** `domains/net-worth/composables/useNetWorthPage.ts`
   - fetch de activos, pasivos y snapshots
   - filtros de ownership (por persona, por tipo)
   - cálculos derivados: ratio deuda/patrimonio, liquidez, distribución
   - estado de período seleccionado

2. **Secciones como componentes:**
   - `NetWorthFilters.vue` — filtros de ownership y período
   - `NetWorthTimeline.vue` — gráfica de evolución temporal
   - `NetWorthAnalytics.vue` — ratios y analítica
   - `NetWorthPositionDetail.vue` — detalle de posición (activos/pasivos agrupados)
   - `NetWorthLedgerActivity.vue` — actividad ledger contextual
   Cada componente recibe datos por props y emite acciones; sin acceso directo a stores.

3. **Reubicar cálculos:**
   - Los cálculos de ratios que hoy viven en la vista deben moverse a `domains/net-worth/composables.ts`
     si son reutilizables, o al composable de página si son específicos de esta vista.

4. **Vista resultante** (`NetWorthView.vue`):
   - Instancia `useNetWorthPage()`
   - Renderiza las secciones pasando datos como props
   - Sin fetch directo ni cálculos complejos

5. **Tests:**
   - `domains/net-worth/__tests__/useNetWorthPage.spec.ts`
   - Ajustar `composables.spec.ts` existente si se mueve lógica

### SaaS Replication
Esta vista es idéntica en Core y SaaS. Replicación directa.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas; NetWorthView <400 líneas

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
```

## Required Documentation Updates
- [ ] `core/docs/roadmap/frontend-refactor-roadmap.md` — actualizar estado Fase 3b
- [ ] `core/docs/frontend/net-worth-ux-notes.md` — si cambian componentes de la vista
- [ ] `core/docs/project-status.md` — marcar Fase 3b como completada

## Risks
- **Riesgo:** `net-worth/composables.ts` ya existe y tiene dependencia de `@/stores/netWorth`
  (wrapper puente). Esta Fase debe ejecutarse después de Fase 1 (arch boundaries).
  **Mitigación:** verificar que Fase 1 está completada antes de iniciar esta.
- **Riesgo:** el warning de `onMounted` fuera de instancia activa en `composables.spec.ts`
  puede reaparecer o empeorar. **Mitigación:** resolver el warning en esta fase si aflora.

## Completion Criteria
- [ ] `NetWorthView.vue` < 400 líneas (wiring + composición de página)
- [ ] Composables extraídos con tests ≥80% cobertura
- [ ] 0 imports de `@/stores/netWorth` en la vista
- [ ] Sin cambios de comportamiento observados en browser
- [ ] `lint`, `typecheck`, `test:coverage` ≥80% en verde — Core y SaaS
- [ ] Documentación requerida actualizada
- [ ] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits)
