# Cartera - Fase 1: fundacion de dominio y migracion

## Context
Core necesita separar contenedor, instrumento, posicion y calidad sin duplicar `Asset`, `LedgerAccount` ni `LedgerTransaction`. Esta fase no calcula rendimiento ni cambia saldos.

## Area
`backend`

## Stack
`core`

## Scope
1. Crear app `portfolio` y modelos base definidos en `../README.md`.
2. Garantizar una cartera global por usuario y aislamiento multiusuario.
3. Modelar contenedores, efectivo por divisa, instrumentos custom/canonicos, posiciones y titularidad historica inmutable.
4. Crear migracion idempotente para todos los `Asset(category=investments)`, activos y archivados, conservando enlaces contables.
5. Clasificar `value_based|units_based` sin inferir unidades dudosas y calcular los dos ejes de cobertura.
6. Exponer CRUD y endpoint de auditoria/migration readiness bajo `/api/portfolio/`.
7. Fuera de alcance: precios, rendimiento, operaciones nuevas y UI.

## Plan
1. Auditar constraints reales de `Asset`, ownership y cuentas de broker.
2. Implementar modelos, servicios de bootstrap y serializers thin.
3. Ejecutar migraciones, probar idempotencia y revisar el resultado con datos reales.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py makemigrations portfolio
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py migrate
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py showmigrations portfolio
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio net_worth accounting memberships
```

## Required Documentation Updates
- [x] `core/docs/architecture/architecture.md` - dominio y fuentes de verdad.
- [x] `core/docs/architecture/accounting-movements-architecture.md` - enlace no duplicado con portfolio.
- [x] `core/docs/project-status.md` y `docs/project-status.md` - estado de fase.

## Risks
La inferencia de contenedor o unidades puede ser falsa. Solo automatizar enlaces inequívocos y emitir `needs_review` para el resto; no reescribir ledger ni ownership historico.

## Completion Criteria
- [x] Migracion aplicada, verificada e idempotente.
- [x] Todos los activos de inversion tienen posicion o incidencia explicita.
- [x] Tests de aislamiento y constraints pasan.
- [x] Documentacion y commit `feat(portfolio): add portfolio domain foundation` completados.
