# Task: Frontend Refactor — Fase 3c: Descomposición de DataInputView

## Context
`DataInputView.vue` tiene 2,742 líneas y mezcla gestión de patrimonio, ingresos anuales,
gastos anuales, import/export portable y filtros de ownership en un único archivo.
Esta fase la descompone en composables de página y secciones sin cambiar comportamiento.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Extraer composables de página por área funcional (patrimonio, ingresos, gastos, portable).
2. Crear componentes de sección para los bloques principales.
3. Reducir la vista al wiring de secciones (objetivo: < 400 líneas).
4. Tests unitarios para los composables extraídos (≥80% cobertura).

**Out of scope:**
1. Cambios de comportamiento o lógica de negocio.
2. Modificaciones de contratos con el backend.
3. Rediseño de UI.

## Plan

### Diagnosis
1. Leer `DataInputView.vue` completo. Identificar:
   - Bloques de template separables (patrimonio, ingresos, gastos, portable, ownership filters)
   - Mezcla actual entre patrimonio, presupuestos y portabilidad
   - Stores y APIs que usa (data-input, net-worth, people)
   - Side effects de importación/exportación

### Change implementation
1. **Composable de filtros de ownership:** `useDataInputFilters.ts`
   - filtros por persona/ownership compartidos entre secciones

2. **Secciones como componentes:**
   - `DataInputPatrimony.vue` — activos, pasivos, liquidez
   - `DataInputIncome.vue` — ingresos anuales previstos
   - `DataInputExpenses.vue` — gastos anuales previstos
   - `DataInputPortable.vue` — import/export portable (wrapping de `portableBundle.ts`)
   Cada componente recibe datos por props y emite acciones; sin acceso directo a stores.

3. **Vista resultante** (`DataInputView.vue`):
   - Instancia los composables
   - Renderiza las secciones
   - Sin lógica de negocio inline

4. **Tests:**
   - `domains/data-input/__tests__/useDataInputFilters.spec.ts`
   - Tests de integración para el flujo portable si no existen

### SaaS Replication
Esta vista es idéntica en Core y SaaS. Replicación directa.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas; DataInputView <400 líneas

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
```

## Required Documentation Updates
- [ ] `core/docs/roadmap/frontend-refactor-roadmap.md` — actualizar estado Fase 3c
- [ ] `core/docs/project-status.md` — marcar Fase 3c como completada

## Risks
- **Riesgo:** `DataInputView` puede tener estado compartido entre secciones (p.ej. el filtro
  de ownership afecta a todas las secciones). **Mitigación:** extraer el filtro como composable
  compartido antes de separar las secciones.
- **Riesgo:** el flujo de importación portable tiene side effects complejos (parseo, validación,
  preview antes de confirmar). **Mitigación:** aislarlo en `DataInputPortable.vue` + composable
  dedicado; no dividir el flujo de importación en múltiples componentes.

## Completion Criteria
- [ ] `DataInputView.vue` < 400 líneas (wiring + composición de página)
- [ ] Composables extraídos con tests ≥80% cobertura
- [ ] Sin cambios de comportamiento observados en browser
- [ ] `lint`, `typecheck`, `test:coverage` ≥80% en verde — Core y SaaS
- [ ] Documentación requerida actualizada
- [ ] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits)
