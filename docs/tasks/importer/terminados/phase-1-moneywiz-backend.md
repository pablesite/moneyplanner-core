## Title
Importador MoneyWiz v1 (backend)

## Context
We need to incorporate massive import of movements from MoneyWiz to populate real accounting and validate the end-to-end behavior of Core with daily use data. This phase defines the backend foundation and the technical contract to execute secure and repeatable imports.

## Area
`backend`

## Stack
`core`

## Scope
1. In scope
   - Parser CSV MoneyWiz (incluyendo encabezado `sep=` y formato numerico/fechas del export real).
- Flow `preview` + `commit` for batch import.
   - Idempotencia por huella de fila (reimport sin duplicados).
   - Auto-creacion de `LedgerAccount` cuando falte cuenta destino/origen.
   - Fallback seguro de clasificacion cuando no exista mapeo exacto de categoria.
   - Endpoints backend de importacion en el dominio `accounting`.
2. Out of scope
- Frontend/backend architecture refactors outside the importer.
   - Billing, accesos SaaS o logica de suscripciones.
   - Importador Excel como fuente primaria (Excel queda para contraste/validacion).

## Plan
1. Diagnosis
   - Revisar formato real del CSV MoneyWiz y diferencias frente a CSV estandar.
   - Confirmar reglas de mapeo con taxonomia de `budget`/`accounting` y contratos de `quick-entry`.
2. Change implementation
   - Implementar servicio de parsing y normalizacion.
   - Implementar preview (estadisticas, warnings, errores por fila, cuentas detectadas).
   - Implementar commit idempotente con persistencia de huella y reporte final.
- Expose endpoints under `api/accounting/` and unit tests/integration flow.
3. Validation
   - Ejecutar calidad backend y test suite de `accounting` en Docker Core.

## Validation
1. `docker compose -f core/docker-compose.yml exec backend ruff check .` — sin errores.
2. `docker compose -f core/docker-compose.yml exec backend ruff format --check .` — sin cambios pendientes de formato.
3. `docker compose -f core/docker-compose.yml exec backend mypy .` — typecheck en verde.
4. `docker compose -f core/docker-compose.yml exec backend python manage.py test accounting` — tests del dominio contable en verde.

## Required Documentation Updates
- [ ] `core/docs/project-status.md` — register task per phase and update status on shutdown.
- [ ] `core/docs/roadmap/product-roadmap.md` — reflect status of the MoneyWiz importer in accounting/import.
- [ ] `core/docs/architecture/architecture.md` — documentar API publica si se publica nuevo endpoint de importacion.

## Risks
1. Mapeo de categorias MoneyWiz -> taxonomia Core incompleto puede degradar resumenes mensuales.
2. Auto-creacion de cuentas puede generar cuentas operativas redundantes si el matching de nombres no es robusto.
3. Idempotencia mal definida puede duplicar movimientos o bloquear importes legitimos repetidos.

## Completion Criteria
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)

## Assumptions (Locked)
1. MoneyWiz es la fuente canonica de importacion.
2. Excel se usa como contraste y validacion, no como fuente primaria v1.
3. La idempotencia por huella es obligatoria.
4. Cuentas faltantes se auto-crean en backend.
5. Categorias no mapeables aplican fallback seguro con warning.
