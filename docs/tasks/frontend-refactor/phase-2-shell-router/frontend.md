# Task: Frontend Refactor — Fase 2: Shell global, router y residuales

## Context
`App.vue` (~492 líneas) concentra navegación, menú de cuenta, sidebar, listeners globales y
bloqueo de scroll mezclados con el wiring de rutas. El router tiene imports desordenados.
Hay cuatro archivos residuales sin propósito real. Esta fase deja `App.vue` como ensamblador
fino y retira los residuales.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Extraer lógica de shell de `App.vue` a composables/componentes de shell.
2. Limpiar `router.ts` (ordenar imports, meta consistente).
3. Retirar `SettingsFxView.vue` y `SettingsIpcView.vue` (7 líneas cada una, sin contenido real).
4. Retirar `components/HelloWorld.vue` y `style.css`.
5. Añadir o ajustar tests de shell y router.

**Out of scope:**
1. Descomposición de las vistas grandes (Fase 3).
2. Cambios de rutas públicas.
3. Lógica de negocio de dominios.

## Plan

### Diagnosis
1. Leer `App.vue` completo e identificar bloques extraíbles:
   - Navegación principal / sidebar items
   - Menú de cuenta (avatar, logout, etc.)
   - Control de apertura/cierre del sidebar
   - Listeners globales (resize, keyboard, etc.)
   - Lógica de bloqueo de scroll
2. Leer `router.ts` completo e identificar: imports desordenados, rutas sin meta, inconsistencias.
3. Verificar que `SettingsFxView.vue` y `SettingsIpcView.vue` no tienen referencias activas.
4. Verificar que `HelloWorld.vue` y `style.css` no tienen referencias activas.

### Change implementation
1. **Extraer shell de `App.vue`:**
   - Crear `src/shell/` (o `domains/shell/` si hay lógica de negocio).
   - Extraer cada bloque identificado en un composable o componente dedicado:
     - `useNavigation.ts` — sidebar items, active route
     - `useSidebar.ts` — open/close state
     - `useGlobalListeners.ts` — resize, keyboard listeners
     - `AppNavigation.vue` — template de la barra de navegación
   - `App.vue` queda solo con: `<router-view>`, `<AppNavigation>` y el composable de shell.

2. **Limpiar `router.ts`:**
   - Ordenar imports alfabéticamente por ruta.
   - Homogeneizar `meta` (solo donde aporta a shell o auth guard).
   - `registerAuthGuard(router)` sigue desacoplado del wiring visual.

3. **Retirar residuales:**
   - Borrar `views/SettingsFxView.vue` y `views/SettingsIpcView.vue`.
   - Eliminar las rutas correspondientes de `router.ts` si las tiene.
   - Borrar `components/HelloWorld.vue` y `src/style.css`.
   - Verificar que no quedan imports huérfanos.

4. **Tests de shell y router:**
   - `router.spec.ts` existente: verificar que sigue pasando; ajustar si se borran rutas.
   - Añadir tests para los composables de shell extraídos (`useNavigation`, `useSidebar`).

### SaaS Replication
Aplicar los mismos cambios en `frontend/` SaaS.
- `SettingsFxView` y `SettingsIpcView` probablemente no existen en SaaS o son también residuales;
  verificar antes de actuar.
- Preservar la URL de auth de SaaS en el router.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas

# Verificar que no quedan residuales:
grep -r "HelloWorld\|SettingsFxView\|SettingsIpcView\|style.css" \
  core/frontend/src --include="*.ts" --include="*.vue"
# → 0 resultados (excepto los ficheros que se borraron)

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
```

## Required Documentation Updates
- [ ] `core/docs/roadmap/frontend-refactor-roadmap.md` — actualizar estado Fase 2
- [ ] `core/docs/project-status.md` — marcar Fase 2 como completada

## Risks
- **Riesgo:** `App.vue` puede tener lógica de auth (redirect, session check) mezclada con shell.
  **Mitigación:** esa lógica debe quedarse en `domains/auth/guard.ts`, no moverse a shell.
- **Riesgo:** borrar vistas puede dejar rutas huérfanas y errores en runtime.
  **Mitigación:** grep de referencias antes de borrar; ejecutar `typecheck` inmediatamente después.

## Completion Criteria
- [ ] `App.vue` reducido a ensamblador fino (< 150 líneas razonable)
- [ ] 0 referencias a archivos residuales borrados
- [ ] Tests de shell en verde con cobertura ≥80%
- [ ] `lint`, `typecheck`, `test:coverage` ≥80% en verde — Core y SaaS
- [ ] Documentación requerida actualizada
- [ ] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits)
