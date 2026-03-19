# Task: Frontend Refactor - Fase 2: Shell global, router y residuales

## Context
`App.vue` (~492 lineas en baseline) concentraba navegacion, menu de cuenta, sidebar, listeners globales y bloqueo de scroll mezclados con el wiring de rutas. Esta fase deja `App.vue` como ensamblador fino, mueve la logica de shell a `src/shell/`, limpia router y retira archivos residuales.

## Area
`frontend`

## Stack
`both`

## Scope ejecutado
1. Extraccion de shell de `App.vue` a `src/shell/`:
   - `AppShellLayout.vue`
   - `useAppShell.ts`
   - `appShellNav.ts`
2. Limpieza de `router.ts` y conservacion de `registerAuthGuard(router)`.
3. Eliminacion de residuales:
   - `src/components/HelloWorld.vue`
   - `src/views/SettingsFxView.vue`
   - `src/views/SettingsIpcView.vue`
   - `src/style.css`
4. Tests de shell y router:
   - `src/shell/__tests__/useAppShell.spec.ts`
   - `src/router.spec.ts`
5. Replicacion equivalente en SaaS (`frontend/`).

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

Resultado de cierre (2026-03-19):
1. Core frontend:
   - `lint`: verde
   - `typecheck`: verde
   - `test:coverage`: verde (`statements 98.29%`, `lines 98.29%`, `functions 92.41%`, `branches 81.50%`)
2. SaaS frontend:
   - `lint`: verde
   - `typecheck`: verde
   - `test:coverage`: verde (`statements 98.29%`, `lines 98.29%`, `functions 92.41%`, `branches 81.53%`)

Checks estructurales:
1. `core/frontend/src/App.vue` y `frontend/src/App.vue`: 13 lineas.
2. `core/frontend/src/router.ts` y `frontend/src/router.ts`: 41 lineas.
3. `HelloWorld`, `SettingsFxView`, `SettingsIpcView` y `style.css` eliminados en ambos stacks.

## Required Documentation Updates
- [x] `core/docs/roadmap/frontend-refactor-roadmap.md` - estado Fase 2 actualizado
- [x] `core/docs/project-status.md` - Fase 2 marcada como completada
- [x] `docs/roadmap/frontend-refactor-roadmap.md` - espejo SaaS actualizado

## Completion Criteria
- [x] `App.vue` reducido a ensamblador fino (< 150 lineas)
- [x] 0 referencias a archivos residuales borrados
- [x] Tests de shell en verde con cobertura >=80%
- [x] `lint`, `typecheck`, `test:coverage` >=80% en verde - Core y SaaS
- [x] Documentacion requerida actualizada
- [x] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits)
