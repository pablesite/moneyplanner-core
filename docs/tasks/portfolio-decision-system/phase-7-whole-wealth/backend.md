# Tarea 7: Decisiones sobre todo el patrimonio — backend

## Context
Entrega del plan solicitado el 2026-09-10 tras el diagnóstico de cartera. Depende de la tarea 6.

## Area
`backend`

## Stack
`core`

## Scope
1. Integrar lecturas de Mi Plan, patrimonio, deuda, reservas y necesidades futuras sin duplicar inventario ni escribir presupuesto desde cartera.
2. Evaluar capacidad de inversión y concentración conjunta separando capital invertible, emergencia y gastos comprometidos.
3. Medir efectos por titularidad y horizonte sin prometer superioridad permanente.

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
- [ ] Integrar lecturas de Mi Plan, patrimonio, deuda, reservas y necesidades futuras sin duplicar inventario ni escribir presupuesto desde cartera.
- [ ] Evaluar capacidad de inversión y concentración conjunta separando capital invertible, emergencia y gastos comprometidos.
- [ ] Medir efectos por titularidad y horizonte sin prometer superioridad permanente.
- [ ] Calidad y tests en verde; documentación actualizada.
- [ ] Spec movida a `terminados/` y commit Conventional Commits creado.
