# Cartera - Fase 5: operaciones completas e importacion

## Area
`backend`

## Stack
`core`

## Scope
1. Modelar metadata de compra/venta enlazada a ledger: unidades, precio, divisa, fee e identificador externo.
2. Exigir para operaciones nuevas transferencia a efectivo del contenedor y compra posterior.
3. Soportar dividendos/intereses a efectivo, fees, valoracion manual, split, cambio de identificador, traspaso y ajuste auditado.
4. Interpretar historico banco -> activo como `funded_purchase` sin mutarlo.
5. Archivar/reabrir posiciones sin perder historico.
6. Crear pipeline CSV generico: upload, mapping, normalizacion, preview, errores por fila, idempotencia y cola de conciliacion.
7. Mantener P&L no fiscal; no implementar FIFO fiscal ni credenciales de broker.

## Plan
1. Definir esquema normalizado y transacciones atomicas.
2. Implementar operaciones y corporate actions.
3. Implementar staging/import/conciliacion y recalculo incremental.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio accounting
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend mypy .
```

## Required Documentation Updates
- [ ] Arquitectura Core de portfolio y accounting.
- [ ] `docs/architecture/api-registry.md`.
- [ ] Project status de Core y SaaS.

## Risks
Duplicar una operacion altera efectivo, unidades y rendimiento. Toda importacion confirma en una transaccion y conserva fingerprint/procedencia.

## Completion Criteria
- [ ] Operaciones nuevas reconcilian ledger, efectivo y posicion.
- [ ] Reimportar el mismo fichero es idempotente.
- [ ] Historico existente no se modifica.
- [ ] Tests, docs y commit completados.

