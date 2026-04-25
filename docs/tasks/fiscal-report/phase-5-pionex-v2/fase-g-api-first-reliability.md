# Phase 5G - API-first reliability gates Pionex

## Context

La simulacion con `finance_data/pionex` mostro que el motor fiscal puede producir
importes diagnosticos, pero todavia no debe considerarse plenamente declarable
cuando faltan datos materiales.

Hallazgos principales:

1. El flujo de producto ya tiene `sync_pionex` API-first para fills spot, Dual
   Investment, bots y balances.
2. La simulacion uso CSV porque no habia credenciales reales disponibles en el
   entorno.
3. Hay categorias que hoy dependen de CSV o no estan confirmadas via API:
   `CommissionIn`, staking/rebase, futuros cerrados y depositos/retiros.
4. Las ventas con gaps de coste, especialmente USDC procedente de depositos,
   pueden inflar ganancias porque el valor de adquisicion queda en 0.
5. El informe necesita distinguir entre importes diagnosticos y resumen
   declarable.

## Area

`backend`

## Stack

`core`

## Scope

### In scope

- Consolidar Pionex como ingesta API-first.
- Mantener CSV solo como fallback auditado.
- Anadir comparacion API/CSV cuando existan ambas fuentes.
- Modelar depositos/retiros como transferencias auditables o gaps de base
  externa.
- Evitar que ventas sin base de coste completa inflen el resumen declarable.
- Anadir bloque `reliability` al payload de `fiscal-report`.
- Bloquear `resumen_declarable` si hay gaps materiales.
- Mantener `resumen_diagnostico` para explicabilidad.
- Documentar cobertura real por endpoint Pionex.

### Out of scope

- Binance reliability hardening.
- SaaS mirror.
- Cambios de UX profundos fuera de mostrar estado bloqueado/provisional.
- Eliminacion de CSV fallback.

## Plan

### 1. Diagnosis

- Ejecutar smoke real con credencial Pionex read-only.
- Confirmar cobertura API para:
  - spot fills,
  - bot fills,
  - Dual Investment,
  - balances,
  - deposits/withdrawals,
  - CommissionIn,
  - staking/rebase,
  - futures closed positions.
- Actualizar `phase-0-api-exploration/notes.md` con matriz final: API, CSV
  fallback, manual required.

### 2. Change implementation

- Anadir identidad fiscal normalizada para deduplicar movimientos API/CSV por
  contenido economico, no solo por `source + trade_id`.
- Persistir procedencia por movimiento/evento: `api`, `csv_fallback`,
  `manual_cost_basis`, `derived_reconciliation`.
- Anadir comparacion API/CSV:
  - `matched`,
  - `api_only`,
  - `csv_only`,
  - `conflicting_amount`,
  - `conflicting_timestamp`.
- Anadir soporte para depositos/retiros Pionex como transferencias o gaps de
  coste externo.
- Cambiar FIFO/fiscal report:
  - ventas con `gap_quantity > 0` no contribuyen a `resumen_declarable`,
  - mantener calculo completo en `resumen_diagnostico`,
  - exponer `blocking_gaps`.
- Anadir `reliability` al payload:
  - `status`: `declarable | blocked_missing_cost_basis | blocked_unreconciled_balances | provisional`,
  - `blocking_gaps`,
  - `input_coverage`,
  - `source_comparison`.

### 3. Validation

- Crear tests con fake Pionex API completo.
- Crear tests API parcial + CSV fallback.
- Verificar que una venta USDC procedente de deposito sin base bloquea el
  resumen.
- Verificar que `ManualCostBasis` desbloquea el resumen.
- Verificar que API/CSV duplicados no duplican trades ni income.
- Verificar que conflicts API/CSV quedan en gaps auditables.

## Validation

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend python manage.py showmigrations broker_integrations
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
docker compose -f core/docker-compose.yml exec backend python manage.py test broker_integrations
```

Smoke manual:

1. Crear credencial Pionex read-only.
2. Ejecutar sync Pionex 2025 sin CSV.
3. Importar CSV como fallback auditado.
4. Comparar cobertura API vs CSV.
5. Generar informe fiscal.
6. Confirmar que gaps materiales bloquean resumen declarable.

## Required Documentation Updates

- [ ] `core/docs/architecture/architecture.md` - documentar `reliability`,
      source comparison y politica API-first/CSV fallback.
- [ ] `core/docs/tasks/fiscal-report/phase-0-api-exploration/notes.md` -
      actualizar matriz real de cobertura Pionex.
- [ ] `core/docs/frontend/fiscal-report-ux-notes.md` - documentar estado
      bloqueado/provisional si se toca frontend.
- [ ] `core/docs/project-status.md` - anadir/cerrar Phase 5G.
- [ ] `core/docs/tasks/fiscal-report/phase-5-pionex-v2/README.md` - anadir
      Phase 5G al listado.

## Risks

1. Pionex puede no exponer por API todo el historico que si aparece en CSV.
2. La comparacion API/CSV puede descubrir diferencias por redondeo, timestamp o
   nomenclatura.
3. Bloquear resumen declarable puede hacer que muchos informes existentes pasen
   a "no declarables" hasta resolver bases manuales.
4. Transferencias externas requieren criterio explicito de coste; no se debe
   inferir coste automaticamente sin evidencia.

## Completion Criteria

- [ ] Pionex sync queda documentado y validado como API-first.
- [ ] CSV fallback queda auditado y no duplica datos API.
- [ ] `fiscal-report` expone `reliability`.
- [ ] Gaps materiales bloquean `resumen_declarable`.
- [ ] `resumen_diagnostico` sigue disponible para explicabilidad.
- [ ] USDC depositado/vendido sin base no genera ganancia declarable automatica.
- [ ] Tests y calidad pasan dentro de Docker.
- [ ] Docs requeridos actualizados.
- [ ] Spec movida a `terminados/` al cerrar.
- [ ] Commit: `feat(broker-integrations): add pionex fiscal reliability gates`.
