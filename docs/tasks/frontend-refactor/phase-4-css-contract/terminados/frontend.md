# Task: Frontend Refactor — Fase 4: CSS contract y contrato visual

## Context
`app.css` has 20,633 lines and is the largest file in the frontend. The great views
acumulan CSS ad hoc en `<style scoped>` que duplica patrones ya definidos en `app.css`.
This phase consolidates shared visual patterns, reduces ad hoc page CSS, and
prepares CSS tokens for future extraction as a shared package.
It should be executed after Phase 3 (the views are already broken down into sections).

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Consolidar en `app.css` los patrones visuales usados en ≥2 pantallas.
2. Reducir `<style scoped>` en vistas y componentes principales.
3. Evaluar y decidir el destino de `guide-home.css`, `guide-score.css`, `data-input.css`.
4. Estandarizar estados loading/empty/error/success.
5. Documentar los tokens/patrones candidatos a `shared/styles/` futuro.
6. Update canonical frontend docs.

**Out of scope:**
1. Visual redesign.
2. Migration to an external design system (Tailwind tokens, etc.).
3. Cambios de comportamiento.

## Plan

### Diagnosis
1. Audit `app.css` (20,633 lines): identify sections (page shell, section shell,
   action bars, state blocks, filtros, metric cards, tablas, modales).
2. Auditar `<style scoped>` en las siguientes vistas post-Fase 3:
   - `App.vue`, `BudgetDashboardView.vue`, `NetWorthView.vue`
   - `GuidePhaseDetailView.vue`, `AccountingMovementsView.vue`
   - `domains/net-worth/components/ItemForm.vue`
3. Identificar patrones duplicados entre `<style scoped>` y `app.css`.
4. Revisar `guide-home.css`, `guide-score.css`, `data-input.css`:
Are they candidates to merge into `app.css` or to stay separate?

### Change implementation
1. **Consolidar patrones en `app.css`:**
- Page shell: page structure (header + main + aside)
- Section shell: section cards and blocks
- Action bars: action buttons in context
   - State blocks: loading spinner, empty state, error state, success state
   - Filtros: pill filters, dropdown filters
   - Metric cards: KPIs y cifras destacadas
- Tables/lists: repetitive data layouts
   - Modales: overlay, panel, header, footer

2. **Reducir `<style scoped>`:**
- For each pattern identified in `<style scoped>` that already exists in `app.css`:
     reemplazar el CSS local por la clase de `app.css`.
- Keep CSS local only when isolation has a clear reason.

3. **Decide CSS destination per module:**
- `guide-home.css` and `guide-score.css`: if the patterns are only used by the guide → keep;
     si se reutilizan en otras pantallas → mergear en `app.css`.
- `data-input.css`: same logic.

4. **Documentar shared package prep:**
- Add section to roadmap: which `app.css` Core tokens and patterns are candidates for
`shared/styles/` future (colors, typography, breakpoints, state blocks).

5. **Actualizar docs:**
   - `docs/frontend/frontend-visual-guide.md`
   - `docs/frontend/frontend-css-workflow.md`

### Core validation
Aplicar los mismos cambios en `frontend/` Core.
The CSS patterns are identical on both frontends; replication is direct.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run format:check
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas; format:check verde

# Core
docker compose exec frontend npm run lint
docker compose exec frontend npm run format:check
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run test:coverage
```

## Required Documentation Updates
- [x] `docs/frontend/frontend-visual-guide.md` — actualizar con patrones consolidados
- [x] `docs/frontend/frontend-css-workflow.md` — actualizar workflow si cambia la estructura de CSS
- [x] `core/docs/roadmap/terminados/frontend-refactor-roadmap.md` — update status Phase 4
- [x] `core/docs/project-status.md` — marcar Fase 4 como completada

## Risks
- **Riesgo:** mover CSS de `<style scoped>` a `app.css` puede crear colisiones de clase si hay
generic names. **Mitigation:** use section prefixes (`.budget-`, `.net-worth-`, etc.)
  en las clases consolidadas; auditar colisiones con grep antes de mover.
- **Risk:** `app.css` already has 20K lines — adding more without organization makes the situation worse.
**Mitigation:** before consolidating, organize `app.css` by sections with clear comments.

## Completion Criteria
- [x] Patrones de page shell, section shell, state blocks consolidados en `app.css`
- [x] `<style scoped>` reducido en las vistas principales
- [x] `guide-home.css`, `guide-score.css`, `data-input.css` with decision made and executed
- [x] Tokens candidatos a shared package documentados en el roadmap
- [x] Updated canonical frontend docs
- [x] `lint`, `format:check`, `typecheck`, `test:coverage` ≥80% en verde — Core
- [x] Spec movida a `terminados/`
- [x] Commit creado (Conventional Commits)

