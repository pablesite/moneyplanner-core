# Title
Integrar introduccion de datos con la visualizacion por categorias en Presupuesto

## Context
La fase 1 movio el CRUD anual de ingresos/gastos a `Presupuesto`, pero la pantalla sigue separada en bloques independientes: por un lado la gestion de entradas y por otro la lectura analitica por categorias/subcategorias. Esto genera doble contexto mental y friccion de uso.

## Area
`frontend`

## Stack
`core`

## Scope
1. In scope
   Unificar en `BudgetDashboardView` la introduccion/edicion de ingresos y gastos con la visualizacion por categorias del presupuesto, sin depender de dos bloques desconectados.
   Mantener el uso de stores y taxonomias existentes (`domains/data-input` y `domains/budget`) evitando duplicacion de logica.
   Permitir editar/crear desde el contexto de categoria/subcategoria (acciones in-place o drawers/modales contextuales).
   Conservar filtros clave (fiscal year, ownership, recurrente/puntual) en un unico flujo coherente.
   Replicar el comportamiento equivalente en `frontend/` (Core) por regla de espejo Core.
2. Out of scope
   Cambios de contrato backend que no sean estrictamente necesarios.
   Eliminacion completa de la ruta `/introduccion-datos` (queda para la fase de retirada del modulo).
   Refactor amplio no relacionado de `domains/budget` o `domains/data-input`.

## Plan
1. Diagnosis
   Auditar `BudgetDashboardView`, `BudgetAnnualSection`, `DataInputAnnualSections` y `useBudgetDashboardPage` para definir el punto de integracion por categoria.
   Mapear interacciones actuales de alta/edicion/borrado y detectar donde se rompe el flujo al alternar entre bloques.
2. Change implementation
   Diseñar un solo flujo: la misma seccion por categoria debe permitir ver totales, detalle y acciones de edicion/alta.
   Reusar `AnnualEntryModalForm` con contexto de categoria/subcategoria preseleccionado para reducir pasos.
   Ajustar estados vacios, errores y carga para que respondan al flujo integrado (no por bloques aislados).
   Mantener compatibilidad con cierre mensual y calculos de ejecucion.
   Replicar en Core con las mismas reglas de UX/comportamiento.
3. Validation
   Ejecutar lint, format:check, typecheck y test:unit en Core frontend y Core frontend.
   Validar manualmente que crear/editar/borrar desde categorias actualiza de forma consistente la visualizacion analitica.

## Validation
- `docker compose -f core/docker-compose.yml exec frontend npm run lint`
- `docker compose -f core/docker-compose.yml exec frontend npm run format:check`
- `docker compose -f core/docker-compose.yml exec frontend npm run typecheck`
- `docker compose -f core/docker-compose.yml exec frontend npm run test:unit`
- `docker compose exec frontend npm run lint`
- `docker compose exec frontend npm run format:check`
- `docker compose exec frontend npm run typecheck`
- `docker compose exec frontend npm run test:unit`
- Validacion manual:
  Presupuesto permite alta/edicion/borrado sin salir del contexto de categorias.
  No hay separacion UX en dos bloques independientes para introducir y visualizar presupuesto.
  Mirror Core verificado.

## Required Documentation Updates
- [ ] `core/docs/project-status.md` — actualizar estado de la fase 2 de Presupuesto
- [ ] `core/docs/roadmap/product-roadmap.md` — reflejar la fase de integracion UX datos↔categorias
- [ ] `docs/project-status.md` — reflejar avance del espejo Core
- [ ] `docs/frontend/domain-map.md` — ajustar descripcion del flujo principal de `budget`
- [ ] `core/docs/tasks/budget/phase-2-budget-category-integration/terminados/frontend.md` — mover la spec al cerrar

## Risks
1. Perder claridad si se mezclan demasiadas acciones por fila/categoria. Mitigacion: mantener jerarquia visual simple y una accion primaria clara.
2. Romper consistencia entre taxonomia y formularios contextuales. Mitigacion: reusar taxonomias y validaciones ya existentes.
3. Divergencia Core en comportamiento de UI. Mitigacion: aplicar espejo en el mismo bloque funcional y validar ambos stacks.

## Completion Criteria
- [ ] Presupuesto integra introduccion de datos y visualizacion por categorias en un unico flujo
- [ ] Alta/edicion/borrado funciona desde el contexto de categoria/subcategoria
- [ ] Mirror Core aplicado o excepcion documentada
- [ ] All validation commands pass
- [ ] Required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
