# Task: Frontend Refactor — 3d Phase: GuidePhaseDetailView Decomposition

## Context
`GuidePhaseDetailView.vue` has 2,207 lines and concentrates scoring, diagnostics and formats
display that also uses `HomeView.vue`. This phase extracts the shared logic to the
domain `guide`, breaks the view into sections and eliminates duplication with HomeView.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Extract scoring, diagnostics and shared formats to `domains/guide/`.
2. Create section components for the guide blocks.
3. Reduce the view to the wiring of sections (goal: < 400 lines).
4. Eliminate duplication of calculations between `GuidePhaseDetailView` and `HomeView`.
5. Unit tests for the extracted composables (≥80% coverage).

**Out of scope:**
1. Changes to the content or logic of the financial coach.
2. UX redesign of the guide.
3. Fases del coach no implementadas.

## Plan

### Diagnosis
1. Leer `GuidePhaseDetailView.vue` completo e identificar:
- Duplicate scoring/diagnosis logic or similar to `HomeView.vue`
- Phase display formats
- Side effects (fetch de datos del scoring)
2. Leer `HomeView.vue` y comparar con `GuidePhaseDetailView.vue` para detectar duplicaciones.
3. Revisar `domains/guide/` actual: `phases.ts`, `phaseDiagnostics.ts`, `scoreVisuals.ts`.

### Change implementation
1. **Consolidar en `domains/guide/`:**
- Move scoring calculations that are in the view to `phaseDiagnostics.ts` or new file.
- Move display formats shared with HomeView to `scoreVisuals.ts`.
   - Actualizar `domains/guide/index.ts` con las nuevas exportaciones.

2. **Page Composable:** `useGuidePhaseDetail.ts`
- phase data fetch
- score and health status calculation
- navigation status between phases

3. **Secciones como componentes:**
   - `GuidePhaseSummary.vue` — cabecera de fase, score, badge
- `GuidePhaseDiagnostics.vue` — diagnostics and recommendations
   - `GuidePhaseProgress.vue` — progreso y criterios de la fase
   Reusar los componentes de `domains/guide/components/` existentes.

4. **Adjust `HomeView.vue`:** replace duplicate code by domain imports.

5. **Tests:**
   - Ampliar `domains/guide/__tests__/phaseDiagnostics.spec.ts` con los casos nuevos
   - `domains/guide/__tests__/useGuidePhaseDetail.spec.ts`

### Core validation
This view is identical in Core. Direct replication.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas; GuidePhaseDetailView <400 líneas

# Core
docker compose exec frontend npm run lint
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run test:coverage
```

## Required Documentation Updates
- [x] `core/docs/roadmap/terminados/frontend-refactor-roadmap.md` — update Phase 3d state
- [x] `core/docs/project-status.md` — marcar Fase 3d como completada

## Risks
- **Risk:** `HomeView.vue` and `GuidePhaseDetailView.vue` may share reactive status
in non-obvious ways. **Mitigation:** audit the stores used in both views before
move logic; do not create circular dependencies between domain and view.

## Completion Criteria
- [x] `GuidePhaseDetailView.vue` < 400 lines
- [x] 0 duplication of calculations between GuidePhaseDetailView and HomeView
- [x] Composables extracted with tests ≥80% coverage
- [ ] Sin cambios de comportamiento observados en browser
- [x] `lint`, `typecheck`, `test:coverage` ≥80% en verde — Core
- [x] Updated required documentation
- [x] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits)

