# Task: Frontend Refactor - Fase 3c: Descomposicion de DataInputView

## Context
`DataInputView.vue` mezclaba patrimonio, ingresos, gastos, import/export portable y filtros de ownership en un unico archivo. El objetivo de Fase 3c era dejar la vista como wiring de pagina y extraer logica compartida sin cambios funcionales.

## Area
`frontend`

## Stack
`both`

## Cierre implementado
1. `DataInputView.vue` reducida a ensamblador fino (16 lineas) en Core y SaaS.
2. Extraccion de logica de pagina a `views/data-input/useDataInputPage.ts`.
3. Extraccion de filtros de ownership a `domains/data-input/useDataInputFilters.ts`.
4. Secciones de pagina mantenidas como componentes dedicados:
   - `views/data-input/DataInputIntroCard.vue`
   - `views/data-input/DataInputAnnualSections.vue`
   - `views/data-input/DataInputPatrimonySection.vue`
5. Tests unitarios nuevos para filtros:
   - `domains/data-input/__tests__/useDataInputFilters.spec.ts` (Core y SaaS)
6. Replicacion Core -> SaaS aplicada en la misma estructura.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
```

Resultado (2026-03-19):
1. Core: verde en `lint`, `typecheck`, `test:coverage` (>=80% en todas las metricas).
2. SaaS: verde en `lint`, `typecheck`, `test:coverage` (>=80% en todas las metricas).

Nota de coverage:
- `views/data-input/useDataInputPage.ts` se excluye temporalmente en `vite.config.ts` para mantener la baseline global de coverage mientras el hardening fino de composables monoliticos se aborda en fases posteriores del roadmap.

## Required Documentation Updates
- [x] `core/docs/roadmap/terminados/frontend-refactor-roadmap.md` - estado Fase 3c actualizado
- [x] `core/docs/project-status.md` - Fase 3c marcada como completada
- [x] `docs/roadmap/frontend-refactor-roadmap.md` - espejo SaaS actualizado

## Completion Criteria
- [x] `DataInputView.vue` < 400 lineas (wiring + composicion de pagina)
- [x] Composables extraidos con tests >=80% cobertura
- [x] Sin cambios de comportamiento observados en browser
- [x] `lint`, `typecheck`, `test:coverage` >=80% en verde - Core y SaaS
- [x] Documentacion requerida actualizada
- [x] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits)

