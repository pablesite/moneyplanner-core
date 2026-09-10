# Tarea 1: Composición coherente — backend

## Context
Entrega del plan solicitado el 2026-09-10 tras el diagnóstico de cartera. No tiene dependencias previas.

## Area
`backend`

## Stack
`core`

## Scope
1. Resolver clases con tenencias vigentes > desglose manual > clase efectiva. No usar fichas futuras.
2. Conservar el valor completo y publicar la fracción desconocida como unclassified y cobertura explícita.
3. Compartir lectura en Diversificación, composición del workspace y Asignación; el desglose por posición evita duplicar su valor en cada clase.
4. Conservar reglas y objetivos de compras: su adaptación a productos mixtos corresponde a la tarea 4.

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
- [x] `core/docs/architecture/architecture.md` — contrato y estado.
- [x] `core/docs/project-status.md` — contrato y estado.
- [x] `core/docs/tasks/portfolio-decision-system/README.md` — contrato y estado.

## Risks
Preservar titularidad, fechas y fuentes monetarias. No reescribir datos reales ni políticas como efecto secundario. Declarar límites pendientes sin aparentar cobertura.

## Completion Criteria
- [x] Resolver clases con tenencias vigentes > desglose manual > clase efectiva. No usar fichas futuras.
- [x] Conservar el valor completo y publicar la fracción desconocida como unclassified y cobertura explícita.
- [x] Compartir lectura en Diversificación, composición del workspace y Asignación; el desglose por posición evita duplicar su valor en cada clase.
- [x] Conservar reglas y objetivos de compras: su adaptación a productos mixtos corresponde a la tarea 4.
- [x] Calidad y tests en verde; documentación actualizada.
- [x] Spec movida a `terminados/` y commit Conventional Commits creado.

## Evidencia de validación — 2026-09-10

- Core backend: 913 tests de cartera y módulos integrados en verde.
- Core frontend: 312 tests en verde, 1 omitido por la suite.
- SaaS frontend: 362 tests en verde, incluida la regresión de presentación de fracciones por clase.
- Calidad Docker de ambos stacks: ruff, formato, mypy, eslint, prettier y typecheck en verde.
- SaaS backend: 180 tests de saas_access en verde.
- No cambia modelos: no requiere migraciones. No se modificaron tenencias, políticas ni saldos reales.
- No se ejecutó una inspección visual en navegador; la interfaz se verificó mediante tests de componentes.
