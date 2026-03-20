# Title
Eliminar el modulo Introduccion de Datos tras recolocar sus ultimas funciones

## Context
Una vez que `Presupuesto` absorba el CRUD anual de ingresos y gastos, `Introduccion de Datos` quedara como un contenedor legacy con patrimonio y portable data. El roadmap de Core marca su eliminacion como prioridad alta, pero no puede cerrarse hasta recolocar esas funciones en sus homes definitivos: patrimonio en `/patrimonio` y portable data en `/account`.

## Area
`frontend`

## Stack
`both`

## Scope
1. In scope
   Eliminar la ruta `/introduccion-datos` y su acceso principal en Core y SaaS.
   Recolocar patrimonio para que se gestione solo desde `/patrimonio`.
   Recolocar `Exportar datos`, `Importar datos` y `Reemplazar datos` en `/account`.
   Limpiar referencias de navegacion, guias, estados vacios y tests que dependan del modulo.
   Actualizar la documentacion funcional y de capacidades afectada.
2. Out of scope
   Cambios backend en portable data.
   Rediseno amplio de `/account` mas alla del bloque necesario para alojar portable data.
   Nuevas capacidades comerciales o cambios de packaging fuera de la retirada del modulo.

## Plan
1. Diagnosis
   Auditar referencias a `/introduccion-datos` en router, shell, guide, tests y docs de Core/SaaS.
   Revisar el bloque actual de portable data para extraerlo del flujo de `DataInputView` sin cambiar su contrato.
2. Change implementation
   Integrar portable data en `/account` manteniendo export, import y replace.
   Confirmar que activos y pasivos ya se gestionan completamente desde `Patrimonio`.
   Eliminar la vista `DataInputView`, la ruta, su item de navegacion y los CTAs residuales.
   Aplicar el espejo equivalente en SaaS.
3. Validation
   Validar routing, navegacion y tests en ambos frontends.
   Verificar manualmente que no queda ninguna accion principal de producto que exija visitar `/introduccion-datos`.

## Validation
- `docker compose -f core/docker-compose.yml exec frontend npm run lint` -> sin errores
- `docker compose -f core/docker-compose.yml exec frontend npm run format:check` -> sin cambios pendientes
- `docker compose -f core/docker-compose.yml exec frontend npm run typecheck` -> sin errores
- `docker compose -f core/docker-compose.yml exec frontend npm run test:unit` -> suites afectadas en verde
- `docker compose exec saas_frontend npm run lint` -> sin errores
- `docker compose exec saas_frontend npm run format:check` -> sin cambios pendientes
- `docker compose exec saas_frontend npm run typecheck` -> sin errores
- `docker compose exec saas_frontend npm run test:unit` -> suites afectadas en verde
- Validacion manual:
  `/account` expone export, import y replace.
  `/patrimonio` cubre el flujo de activos y pasivos sin dependencia de `Introduccion de Datos`.
  Ninguna ruta o CTA visible lleva a `/introduccion-datos`.

## Required Documentation Updates
- [ ] `core/docs/project-status.md` — cerrar la tarea de eliminacion del modulo
- [ ] `core/docs/roadmap/product-roadmap.md` — marcar `Modulo Introduccion de Datos` como migrado/eliminado
- [ ] `core/docs/architecture/architecture.md` — retirar `Data input` del scope de modulos activos si deja de existir como modulo
- [ ] `docs/project-status.md` — actualizar el espejo SaaS y la consolidacion funcional v1
- [ ] `docs/frontend/domain-map.md` — eliminar la ruta `/introduccion-datos` y reflejar portable data en `account`
- [ ] `docs/architecture/capabilities-matrix.md` — ajustar `core.dataInput` si pasa a legacy/compatibilidad
- [ ] `core/docs/tasks/data-input/phase-1-module-removal/terminados/frontend.md` — mover la spec al cerrar la tarea

## Risks
1. Romper portable data al moverlo a `/account` sin conservar bien el estado y los mensajes UX. Mitigacion: extraer el bloque con contrato estable y validar import/export manualmente.
2. Mantener referencias residuales a la ruta eliminada en guide o nav. Mitigacion: barrido completo de Core y SaaS antes de cerrar.
3. Mezclar eliminacion de modulo con rediseno grande de cuenta. Mitigacion: limitar el cambio a alojar portable data de forma funcional.

## Completion Criteria
- [ ] `Introduccion de Datos` deja de existir como modulo/ruta en Core y SaaS
- [ ] Portable data funciona desde `/account`
- [ ] Patrimonio queda como unico home de activos y pasivos
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
