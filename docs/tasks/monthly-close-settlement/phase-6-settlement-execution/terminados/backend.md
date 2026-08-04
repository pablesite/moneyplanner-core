# Fase 6 - Ejecucion idempotente de transferencias

## Title

Materializar recomendaciones aceptadas como transferencias ledger auditables e idempotentes.

## Context

La version 1 termina en recomendaciones que el usuario ejecuta y registra manualmente. La version 2
reduce friccion creando los movimientos internos correctos, sin convertirlos en ingreso/gasto ni
permitir duplicados al reintentar una peticion.

## Area

`backend`

## Stack

`core`

## Scope

### In scope

1. Lifecycle de recomendacion `recommended`, `accepted`, `applied`, `partially_applied`, `cancelled`.
2. Endpoint de aceptacion/aplicacion con `select_for_update` e idempotency key estable por cierre/ruta.
3. Crear transferencias `LedgerTransaction` con origen system, quick kind transfer, ownership de la
   ruta y FK explicita al settlement/recomendacion.
4. Crear una transaccion por ownership cuando una ruta fisica agregada contiene varias atribuciones.
5. No clasificar transferencias como ingreso/gasto ni volver a detectarlas como compensacion.
6. Soportar fecha real de ejecucion, importe parcial y conciliacion con una transferencia manual o
   importada compatible.
7. Impedir aplicar cierres locked, recomendaciones obsoletas o cuentas ajenas/inactivas.
8. Recalcular saldos tras aplicar y verificar que el estado objetivo se alcanza o explicar el remanente.
9. Reopen policy: no borrar movimientos aplicados; exigir reverso explicito o conservar settlement
   aplicado como hecho historico.
10. Tests de carrera, retry, rollback atomico, parcial y aislamiento.

### Out of scope

1. Iniciar transferencias bancarias externas.
2. Ejecutar FX automaticamente.
3. Borrar transferencias bancarias importadas.
4. Reescribir settlements locked.

## Plan

1. Añadir links y estados persistidos con migraciones.
2. Implementar servicio de materializacion sobre `accounting.services_quick_entry` sin duplicar
   construccion de asientos.
3. Añadir idempotencia y concurrencia transaccional.
4. Implementar matching conservador de transferencias ya registradas.
5. Integrar lifecycle de cierre y recalculo posterior.
6. Ejecutar QA integrado con la spec SaaS de fase 6.

## Validation

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations budget accounting
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend python manage.py showmigrations budget
docker compose -f core/docker-compose.yml exec backend python manage.py showmigrations accounting
docker compose -f core/docker-compose.yml exec backend python manage.py test budget accounting memberships net_worth
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
```

## Required Documentation Updates

- [x] `core/docs/architecture/architecture.md` - lifecycle y materializacion.
- [x] `core/docs/architecture/accounting-movements-architecture.md` - transferencias settlement.
- [x] `docs/architecture/api-registry.md` - endpoints apply/reconcile.
- [x] `core/docs/roadmap/product-roadmap.md` - marcar version 2 completada.
- [x] `core/docs/project-status.md` - cerrar modulo backend.

## Risks

- Reintentos pueden duplicar dinero. La idempotencia debe estar protegida por constraint de base de
  datos, no solo por una comprobacion previa.
- Reabrir un cierre aplicado puede borrar la explicacion de transferencias reales. Los movimientos
  persisten y cualquier reverso es otro asiento.
- Matching agresivo puede enlazar una transferencia bancaria incorrecta. Exigir cuentas, moneda,
  importe, ventana temporal y confirmacion cuando haya mas de una candidata.

## Completion Criteria

- [x] Applying the same recommendation twice creates one ledger transaction.
- [x] Applied transfers preserve household and member economic totals.
- [x] Partial execution exposes the exact remaining amount.
- [x] Existing compatible transfers can be linked without duplication.
- [x] Reopen and lock policies are enforced and documented.
- [x] Migrations applied and verified.
- [x] All validation commands pass.
- [x] All required documentation updates done.
- [x] Spec moved to `terminados/`.
- [x] Commit created (Conventional Commits).
