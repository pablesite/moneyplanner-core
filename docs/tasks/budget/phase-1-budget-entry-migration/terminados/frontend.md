# Title
Migrar altas y bajas anuales de ingresos y gastos a Presupuesto

## Context
El roadmap de Core marca como siguiente tarea disponible mover la gestion anual de ingresos y gastos desde `Introduccion de Datos` a `Presupuesto`. Hoy `BudgetDashboardView` consume esos mismos datos via endpoints de `budget`, pero el CRUD sigue encapsulado en `DataInputAnnualSections`, lo que mantiene un flujo duplicado y deja a `Presupuesto` incompleto para la v1.

## Area
`frontend`

## Stack
`core`

## Scope
1. In scope
   Integrar en `BudgetDashboardView` una gestion visible de ingresos y gastos anuales dentro del flujo de `Presupuesto`.
   Reutilizar stores, taxonomias y formularios ya existentes en `domains/data-input` siempre que no obliguen a mantener el flujo antiguo.
   Sustituir enlaces y estados vacios que hoy empujan a `/introduccion-datos` para crear o completar presupuesto anual.
   Retirar de `DataInputView` las secciones de ingresos y gastos para evitar doble punto de edicion durante la transicion.
   Replicar el cambio equivalente en `frontend/` por la regla de espejado Core.
2. Out of scope
   Eliminar aun la ruta `/introduccion-datos`.
   Redisenar patrimonio, portable data o `/account`.
   Cambiar contratos backend si el frontend puede resolverse con los endpoints actuales.
   Refactor amplio de `domains/data-input` o `domains/budget`.

## Plan
1. Diagnosis
   Revisar `BudgetDashboardView`, `BudgetAnnualSection`, `DataInputAnnualSections` y `AnnualEntryModalForm` para decidir que piezas se extraen o reutilizan.
   Confirmar todos los puntos de navegacion Core que hoy enlazan a `/introduccion-datos`.
2. Change implementation
   Anadir a `Presupuesto` una zona integrada para ingresos y gastos anuales con acciones de alta, edicion y borrado.
   Mantener la logica de datos sobre `annual-income` y `annual-expense` usando los stores actuales o wrappers finos sobre ellos, sin duplicar reglas de taxonomia ni parseo.
   Convertir el estado vacio de `Presupuesto` en un CTA interno al alta de presupuesto, no a la vista antigua.
   Dejar `DataInputView` como vista transitoria limitada a patrimonio y portable data.
   Reflejar el mismo comportamiento en el Core frontend salvo diferencias documentadas de empaquetado.
3. Validation
   Validar lint, format, typecheck y unit tests en Core frontend y Core frontend.
   Verificar manualmente que no queda ningun flujo principal de presupuesto dependiendo de `/introduccion-datos`.

## Validation
- `docker compose -f core/docker-compose.yml exec frontend npm run lint` -> sin errores
- `docker compose -f core/docker-compose.yml exec frontend npm run format:check` -> sin cambios pendientes
- `docker compose -f core/docker-compose.yml exec frontend npm run typecheck` -> sin errores
- `docker compose -f core/docker-compose.yml exec frontend npm run test:unit` -> suites afectadas en verde
- `docker compose exec frontend npm run lint` -> sin errores
- `docker compose exec frontend npm run format:check` -> sin cambios pendientes
- `docker compose exec frontend npm run typecheck` -> sin errores
- `docker compose exec frontend npm run test:unit` -> suites afectadas en verde
- Validacion manual:
  `Presupuesto` permite alta, edicion y borrado de ingreso anual.
  `Presupuesto` permite alta, edicion y borrado de gasto anual.
  El estado vacio de `Presupuesto` ya no redirige a `Introduccion de Datos`.
  `DataInputView` ya no expone gestion anual de ingresos/gastos.

## Required Documentation Updates
- [x] `core/docs/project-status.md` — mover el estado de la tarea y reflejar el avance de `Presupuesto`
- [x] `core/docs/roadmap/product-roadmap.md` — marcar que la migracion a `Presupuesto` ya esta ejecutada
- [x] `core/docs/architecture/architecture.md` — ajustar el scope del producto si `Data Input` deja de ser modulo activo de flujo principal
- [x] `docs/project-status.md` — reflejar el espejo Core y el avance de consolidacion funcional v1
- [x] `docs/frontend/domain-map.md` — actualizar el flujo principal de `budget` y el rol transitorio de `data-input`
- [x] `core/docs/tasks/budget/phase-1-budget-entry-migration/terminados/frontend.md` — mover la spec al cerrar la tarea

## Risks
1. Reintroducir duplicacion entre `budget` y `data-input` si se copian formularios o stores en vez de extraer piezas reutilizables. Mitigacion: reutilizar primitivas existentes y centralizar la logica de datos.
2. Dejar enlaces huérfanos a `/introduccion-datos` en Core o Core. Mitigacion: auditar router, nav, guide y empty states antes de cerrar.
3. Romper el flujo de gastos generados por pasivos al mover la edicion al presupuesto. Mitigacion: conservar la integracion con `net-worth` y validar el caso de gasto generado por pasivo.

## Completion Criteria
- [x] `Presupuesto` gestiona ingresos y gastos anuales sin depender de `Introduccion de Datos`
- [x] `DataInputView` queda reducido a patrimonio + portable data
- [x] Mirror Core aplicado o excepcion documentada
- [x] All validation commands pass
- [x] All required documentation updates done
- [x] Spec moved to `terminados/`
- [x] Commit created (Conventional Commits)
