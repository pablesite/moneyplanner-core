# Tarea 4: Aportaciones por exposición real — backend

## Context
Entrega del plan solicitado el 2026-09-10 tras el diagnóstico de cartera. Depende de la tarea 3.

## Area
`backend`

## Stack
`core`

## Scope
1. Traducir cada euro de compra de productos mixtos a sus exposiciones con fecha y cobertura.
2. Definir objetivos y bandas por producto con unidad inequívoca y compatibilidad de políticas existentes.
3. Resolver mínimos, máximos, concentración, compromisos, costes y redondeos; declarar conflictos y destinos inalcanzables.

## Plan
1. Revisar implementación y contrato.
2. Implementar el alcance con pruebas deterministas de regresión.
3. Validar dentro de Docker, documentar y crear commit.

## Validation
Desde la raíz:
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec -T core_backend ruff check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec -T core_backend ruff format --check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec -T core_backend mypy .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec -T core_backend python manage.py test portfolio accounting accounts budget memberships net_worth core
```
Si cambia integración, ejecutar `validate all` y tests de ambos stacks. Migraciones solo si cambia el modelo.

## Required Documentation Updates
- [ ] `core/docs/architecture/architecture.md` — contrato y estado.
- [ ] `core/docs/project-status.md` — contrato y estado.
- [ ] `core/docs/tasks/portfolio-decision-system/README.md` — contrato y estado.

## Risks
Preservar titularidad, fechas y fuentes monetarias. No reescribir datos reales ni políticas como efecto secundario. Declarar límites pendientes sin aparentar cobertura.

## Completion Criteria
- [ ] Traducir cada euro de compra de productos mixtos a sus exposiciones con fecha y cobertura.
- [ ] Definir objetivos y bandas por producto con unidad inequívoca y compatibilidad de políticas existentes.
- [ ] Resolver mínimos, máximos, concentración, compromisos, costes y redondeos; declarar conflictos y destinos inalcanzables.
- [ ] Calidad y tests en verde; documentación actualizada.
- [ ] Spec movida a `terminados/` y commit Conventional Commits creado.
