## Title
Importador MoneyWiz v1 (UI minima)

## Context
Tras definir backend de importacion, necesitamos habilitar una experiencia minima en `AccountingMovementsView` para ejecutar el flujo completo sin salir de la aplicacion: subir CSV, previsualizar, confirmar importacion y revisar resultado.

## Area
`frontend`

## Stack
`both`

## Scope
1. In scope
   - Flujo UI: subir CSV -> preview -> commit -> resultado.
   - Integracion con cliente API del dominio `accounting`.
   - Estado y manejo de errores/warnings del importador en composables/store.
   - Replicacion equivalente Core -> SaaS en el frontend espejo (`frontend/`) segun regla de espejado.
2. Out of scope
   - Rediseño visual amplio de `AccountingMovementsView`.
   - Refactor estructural general de dominios frontend.

## Plan
1. Diagnosis
   - Revisar estructura actual de `domains/accounting` y `AccountingMovementsView` en Core y SaaS.
   - Definir puntos de insercion UI sin romper flujos existentes de quick-entry/edicion.
2. Change implementation
   - Agregar llamadas API de preview/commit en `domains/accounting/api.ts`.
   - Agregar estado y acciones en composables/store.
   - Añadir bloque de importacion en la vista de movimientos con feedback claro de validaciones.
   - Replicar el cambio equivalente en `frontend/` (SaaS).
3. Validation
   - Ejecutar lint/format/typecheck de frontend Core y frontend SaaS en Docker.

## Validation
1. `docker compose -f core/docker-compose.yml exec frontend npm run lint` — lint frontend Core en verde.
2. `docker compose -f core/docker-compose.yml exec frontend npm run format:check` — formato frontend Core correcto.
3. `docker compose -f core/docker-compose.yml exec frontend npm run typecheck` — types frontend Core en verde.
4. `docker compose exec saas_frontend npm run lint` — lint frontend SaaS en verde.
5. `docker compose exec saas_frontend npm run format:check` — formato frontend SaaS correcto.
6. `docker compose exec saas_frontend npm run typecheck` — types frontend SaaS en verde.

## Required Documentation Updates
- [ ] `core/docs/project-status.md` — actualizar estado de fase frontend del importador.
- [ ] `docs/frontend/domain-map.md` — actualizar solo si cambia superficie/ruta de dominio en SaaS.

## Risks
1. Diferencias de UI entre Core y SaaS si no se aplica espejo completo.
2. Mala UX de errores puede permitir commits sin entender filas descartadas.
3. Sobrecarga visual en una vista ya extensa si no se acota el bloque de importacion.

## Completion Criteria
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)

## Assumptions (Locked)
1. El importador se expone en la vista de movimientos actual.
2. La UI de v1 es operativa/minima, no rediseño global.
3. La regla Core->SaaS de espejado es obligatoria para este cambio.
