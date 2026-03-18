# Task: Frontend Refactor — Fase 3d: Descomposición de GuidePhaseDetailView

## Context
`GuidePhaseDetailView.vue` tiene 2,207 líneas y concentra scoring, diagnósticos y formatos
de visualización que también usa `HomeView.vue`. Esta fase extrae la lógica compartida al
dominio `guide`, descompone la vista en secciones y elimina la duplicación con HomeView.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Extraer scoring, diagnósticos y formatos compartidos a `domains/guide/`.
2. Crear componentes de sección para los bloques de la guía.
3. Reducir la vista al wiring de secciones (objetivo: < 400 líneas).
4. Eliminar duplicación de cálculos entre `GuidePhaseDetailView` y `HomeView`.
5. Tests unitarios para los composables extraídos (≥80% cobertura).

**Out of scope:**
1. Cambios de contenido o lógica del coach financiero.
2. Rediseño de UX de la guía.
3. Fases del coach no implementadas.

## Plan

### Diagnosis
1. Leer `GuidePhaseDetailView.vue` completo e identificar:
   - Lógica de scoring/diagnóstico duplicada o similar a `HomeView.vue`
   - Formatos de visualización de fases
   - Side effects (fetch de datos del scoring)
2. Leer `HomeView.vue` y comparar con `GuidePhaseDetailView.vue` para detectar duplicaciones.
3. Revisar `domains/guide/` actual: `phases.ts`, `phaseDiagnostics.ts`, `scoreVisuals.ts`.

### Change implementation
1. **Consolidar en `domains/guide/`:**
   - Mover cálculos de scoring que estén en la vista a `phaseDiagnostics.ts` o nuevo fichero.
   - Mover formatos de visualización compartidos con HomeView a `scoreVisuals.ts`.
   - Actualizar `domains/guide/index.ts` con las nuevas exportaciones.

2. **Composable de página:** `useGuidePhaseDetail.ts`
   - fetch de datos de la fase
   - cálculo de score y estado de salud
   - estado de navegación entre fases

3. **Secciones como componentes:**
   - `GuidePhaseSummary.vue` — cabecera de fase, score, badge
   - `GuidePhaseDiagnostics.vue` — diagnósticos y recomendaciones
   - `GuidePhaseProgress.vue` — progreso y criterios de la fase
   Reusar los componentes de `domains/guide/components/` existentes.

4. **Ajustar `HomeView.vue`:** reemplazar código duplicado por importaciones del dominio.

5. **Tests:**
   - Ampliar `domains/guide/__tests__/phaseDiagnostics.spec.ts` con los casos nuevos
   - `domains/guide/__tests__/useGuidePhaseDetail.spec.ts`

### SaaS Replication
Esta vista es idéntica en Core y SaaS. Replicación directa.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas; GuidePhaseDetailView <400 líneas

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
```

## Required Documentation Updates
- [ ] `core/docs/roadmap/frontend-refactor-roadmap.md` — actualizar estado Fase 3d
- [ ] `core/docs/project-status.md` — marcar Fase 3d como completada

## Risks
- **Riesgo:** `HomeView.vue` y `GuidePhaseDetailView.vue` pueden compartir estado reactivo
  de formas no evidentes. **Mitigación:** auditar los stores usados en ambas vistas antes de
  mover lógica; no crear dependencias circulares entre dominio y vista.

## Completion Criteria
- [ ] `GuidePhaseDetailView.vue` < 400 líneas
- [ ] 0 duplicación de cálculos entre GuidePhaseDetailView y HomeView
- [ ] Composables extraídos con tests ≥80% cobertura
- [ ] Sin cambios de comportamiento observados en browser
- [ ] `lint`, `typecheck`, `test:coverage` ≥80% en verde — Core y SaaS
- [ ] Documentación requerida actualizada
- [ ] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits)
