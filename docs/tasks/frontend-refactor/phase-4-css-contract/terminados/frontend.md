# Task: Frontend Refactor — Fase 4: CSS contract y contrato visual

## Context
`app.css` tiene 20,633 líneas y es el fichero más grande del frontend. Las vistas grandes
acumulan CSS ad hoc en `<style scoped>` que duplica patrones ya definidos en `app.css`.
Esta fase consolida los patrones visuales compartidos, reduce el CSS de página ad hoc y
prepara los tokens CSS para una futura extracción como shared package.
Debe ejecutarse después de Fase 3 (las vistas ya están descompuestas en secciones).

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
6. Actualizar docs frontend canónicas.

**Out of scope:**
1. Rediseño visual.
2. Migración a un sistema de diseño externo (Tailwind tokens, etc.).
3. Cambios de comportamiento.

## Plan

### Diagnosis
1. Auditar `app.css` (20,633 líneas): identificar secciones (page shell, section shell,
   action bars, state blocks, filtros, metric cards, tablas, modales).
2. Auditar `<style scoped>` en las siguientes vistas post-Fase 3:
   - `App.vue`, `BudgetDashboardView.vue`, `NetWorthView.vue`
   - `GuidePhaseDetailView.vue`, `AccountingMovementsView.vue`
   - `domains/net-worth/components/ItemForm.vue`
3. Identificar patrones duplicados entre `<style scoped>` y `app.css`.
4. Revisar `guide-home.css`, `guide-score.css`, `data-input.css`:
   ¿son candidatos a mergearse en `app.css` o a mantenerse separados?

### Change implementation
1. **Consolidar patrones en `app.css`:**
   - Page shell: estructura de página (header + main + aside)
   - Section shell: tarjetas y bloques de sección
   - Action bars: botones de acción en contexto
   - State blocks: loading spinner, empty state, error state, success state
   - Filtros: pill filters, dropdown filters
   - Metric cards: KPIs y cifras destacadas
   - Tablas/listas: layouts repetitivos de datos
   - Modales: overlay, panel, header, footer

2. **Reducir `<style scoped>`:**
   - Por cada patrón identificado en `<style scoped>` que ya existe en `app.css`:
     reemplazar el CSS local por la clase de `app.css`.
   - Mantener CSS local solo cuando el aislamiento tenga una razón clara.

3. **Decidir destino de CSS por módulo:**
   - `guide-home.css` y `guide-score.css`: si los patrones solo los usa la guía → mantener;
     si se reutilizan en otras pantallas → mergear en `app.css`.
   - `data-input.css`: misma lógica.

4. **Documentar shared package prep:**
   - Añadir sección al roadmap: qué tokens y patrones de `app.css` Core son candidatos a
     `shared/styles/` futuro (colores, tipografía, breakpoints, state blocks).

5. **Actualizar docs:**
   - `docs/frontend/frontend-visual-guide.md`
   - `docs/frontend/frontend-css-workflow.md`

### SaaS Replication
Aplicar los mismos cambios en `frontend/` SaaS.
Los patrones CSS son idénticos en ambos frontends; la replicación es directa.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run format:check
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas; format:check verde

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run format:check
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
```

## Required Documentation Updates
- [x] `docs/frontend/frontend-visual-guide.md` — actualizar con patrones consolidados
- [x] `docs/frontend/frontend-css-workflow.md` — actualizar workflow si cambia la estructura de CSS
- [x] `core/docs/roadmap/frontend-refactor-roadmap.md` — actualizar estado Fase 4
- [x] `core/docs/project-status.md` — marcar Fase 4 como completada

## Risks
- **Riesgo:** mover CSS de `<style scoped>` a `app.css` puede crear colisiones de clase si hay
  nombres genéricos. **Mitigación:** usar prefijos de sección (`.budget-`, `.net-worth-`, etc.)
  en las clases consolidadas; auditar colisiones con grep antes de mover.
- **Riesgo:** `app.css` ya tiene 20K líneas — añadir más sin organización empeora la situación.
  **Mitigación:** antes de consolidar, organizar `app.css` por secciones con comentarios claros.

## Completion Criteria
- [x] Patrones de page shell, section shell, state blocks consolidados en `app.css`
- [x] `<style scoped>` reducido en las vistas principales
- [x] `guide-home.css`, `guide-score.css`, `data-input.css` con decisión tomada y ejecutada
- [x] Tokens candidatos a shared package documentados en el roadmap
- [x] Docs frontend canónicas actualizadas
- [x] `lint`, `format:check`, `typecheck`, `test:coverage` ≥80% en verde — Core y SaaS
- [x] Spec movida a `terminados/`
- [x] Commit creado (Conventional Commits)
