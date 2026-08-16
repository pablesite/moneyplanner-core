# Cartera - Fase 5: QA de migracion y conciliacion

## Context
La fase combina datos historicos, asientos nuevos e importaciones externas. Un fallo puede duplicar efectivo o unidades y requiere validacion transversal.

## Area
`qa`

## Stack
`both`

## Scope
Validar migracion no destructiva, doble entrada, unidades/efectivo, reimport idempotente, colisiones, import parcial, rollback, corporate actions, archivo/reapertura y recalculo de rendimiento.

## Plan
1. Capturar hashes y conteos del ledger antes/despues del bootstrap.
2. Ejecutar operaciones e importaciones validas, duplicadas y fallidas.
3. Validar en API y navegador la conciliacion y el rollback atomico.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio accounting
docker compose -f docker-compose.dev.yml --env-file .env.dev exec saas_frontend npm run test
```

## Required Documentation Updates
- [ ] `core/docs/architecture/accounting-movements-architecture.md` - invariantes verificados.
- [ ] Project status de Core y SaaS.

## Risks
Los fixtures sinteticos pueden no reproducir formatos reales; incluir al menos dos CSV anonimizados y conservarlos como fixtures sin datos sensibles.

## Completion Criteria
- [ ] Cero asientos historicos modificados por bootstrap/import.
- [ ] Toda operacion confirmada reconcilia efectivo, unidades y ledger.
- [ ] Evidencia manual con al menos dos formatos CSV.
- [ ] Commit y estado de fase completados.
- [ ] Spec movida a `terminados/`.
