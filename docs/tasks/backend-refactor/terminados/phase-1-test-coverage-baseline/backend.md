# Core backend — Phase 1: Test coverage baseline

## Title
Core backend — test coverage baseline (prerequisito de refactor)

## Context
Antes de mover una sola línea de código de producción, necesitamos una red de seguridad
de tests que cubra ≥80% de cada app del backend Core. El estado actual tiene huecos
importantes: `budget/test_services.py` tiene solo 43 líneas para un módulo de 619 líneas,
`net_worth/tests/test_net_worth.py` es un monolito de 4,275 líneas sin separación por
dominio, y no existen tests de integración cross-domain que protejan los boundaries entre
`accounting`, `budget` y `net_worth`. Esta fase no cambia comportamiento funcional.

## Area
`backend`

## Stack
`core`

## Scope

### En scope
1. Añadir tests que faltan en todos los apps del backend Core.
2. Reorganizar `net_worth/tests/test_net_worth.py` en ficheros de dominio separados.
3. Añadir integration tests para flujos cross-domain: `accounting↔budget`, `accounting↔net_worth`, `memberships↔net_worth`.
4. Expandir `budget/test_services.py` (43 → ≥300 líneas) cubriendo lógica de services.
5. Añadir tests de error paths en todos los apps (auth failure, validation error, 404).
6. Medir cobertura con `coverage.py` y llegar a ≥80% por app.

### Fuera de scope
1. Cualquier cambio de código de producción (models, views, services, serializers).
2. Cambios de contrato API.
3. Refactor de la estructura de ficheros de producción.

## Plan

### 1. Diagnóstico de cobertura actual
```bash
# Ejecutar dentro del contenedor Core
docker compose -f core/docker-compose.yml exec backend \
  python -m pytest --cov=. --cov-report=term-missing --no-header -q \
  2>/dev/null || \
  python manage.py test accounting accounts budget memberships net_worth core
```
Anotar cobertura actual por app antes de empezar.

### 2. `accounting` — ampliar cobertura

Fichero objetivo: `backend/accounting/tests/test_accounting.py` (actual: 1,622 líneas)

Añadir tests para:
- `build_budget_derived_suggestions` con todas las combinaciones de filtros
- `build_account_balances_summary` — multi-cuenta, moneda distinta a base
- `create_quick_transaction` — paths de error: cuenta inválida, counterparty inválido
- `backfill_ledger_entry_classification` — sin clasificación previa, con clasificación previa
- `ensure_net_worth_opening_balance_transaction` — primera creación y idempotencia
- Integration test `accounting↔budget`: entry con `annual_income_entry` / `annual_expense_entry`
- Integration test `accounting↔net_worth`: asset con `tracking_mode=accounting`, balances ligados

### 3. `budget` — ampliar `test_services.py`

Fichero objetivo: `backend/budget/tests/test_services.py` (actual: 43 líneas → ≥300 líneas)

Añadir tests para:
- `build_monthly_budget_summary` con ledger activo vs. fallback legacy
- `build_monthly_budget_summary` con `confirmed_at` presente y ausente
- Check-ins con `confirmed_at` parcial y completo
- Cobertura ledger = 0%, 50%, 100%
- Convivencia income + expense en el mismo mes
- Edge cases: usuario sin entries del año, entries sin check-ins

### 4. `net_worth` — reorganizar suite monolítica

**Fichero a dividir:** `backend/net_worth/tests/test_net_worth.py` (4,275 líneas)

**Nuevo layout:**
```
backend/net_worth/tests/
  __init__.py
  test_assets.py          ← tests de creación, valuación y eventos de activos
  test_liabilities.py     ← tests de creación, calendario de pagos y eventos de pasivos
  test_snapshots.py       ← tests de snapshots (from-current, import-bulk)
  test_summaries.py       ← tests de summary endpoint
  test_liquidity.py       ← tests de liquidity check-ins y monthly summary
  test_timelines.py       ← tests de timeline endpoints
  test_integration.py     ← tests cross-domain: accounting↔net_worth, memberships↔net_worth
```

Reglas de migración:
- Mover sin alterar los tests existentes (no reescribir, solo reubicar)
- Añadir tests nuevos en los ficheros correspondientes donde haya huecos
- `test_integration.py` es nuevo — solo tests cross-domain que no existen hoy

### 5. `accounts` — añadir error paths

Fichero objetivo: `backend/accounts/tests.py` (actual: 187 líneas)

Añadir:
- Login con credenciales inválidas → 401 con shape `{code, message}`
- `UserSettings` creado on-demand si no existe
- `ops/metrics/` solo accesible con `is_staff=True`
- `link-token` con feature flag desactivado → `feature_disabled`

### 6. `core` — añadir unit tests para portable_data y market_data

Fichero objetivo: `backend/core/tests.py` (actual: 715 líneas)

Añadir:
- `portable_data.py`: export genera estructura versionada, import idempotente
- `market_data.py`: FX rate lookup, IPC lookup, market-data/status cuando no hay datos
- Tests de error: importación con formato inválido, moneda desconocida

### 7. `memberships` — reforzar side effects de sync

Fichero objetivo: `backend/memberships/tests/test_services.py` (actual: 114 líneas)

Añadir:
- `ownership-links/sync` — efecto sobre budget entries del miembro
- `ensure-primary` con FamilyMember ya existente (idempotencia)
- Side effect: eliminar FamilyMember no debe dejar budget entries huérfanas

### 8. Medir cobertura final
```bash
docker compose -f core/docker-compose.yml exec backend \
  python -m pytest --cov=accounting --cov=accounts --cov=budget \
    --cov=memberships --cov=net_worth --cov=core \
    --cov-report=term-missing --cov-fail-under=80
```
Criterio: ≥80% de statement coverage por app.

## Validation

```bash
# 1. Suite completa pasa
cd core
docker compose exec backend python manage.py test accounting accounts budget memberships net_worth core

# 2. Calidad
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .
docker compose exec backend mypy .

# 3. Cobertura (si pytest-cov disponible)
docker compose exec backend python -m pytest --cov=. --cov-report=term-missing
```

Resultados esperados:
- `manage.py test ...` → 0 errores, 0 fallos
- `ruff check` → sin errores
- `mypy` → sin errores
- Cobertura ≥80% en todos los apps

## Required Documentation Updates

- [ ] `core/docs/roadmap/backend-refactor-roadmap.md` — marcar Fase 0/1 completada, actualizar checklist de cobertura por app
- [ ] `core/docs/project-status.md` — mover esta tarea a "completada"

## Risks

1. **Monolito net_worth dividido puede romper test discovery**: verificar que `__init__.py` está presente y los imports de fixtures funcionan entre ficheros.
2. **Tests nuevos pueden revelar bugs reales**: no corregirlos en esta fase; abrir issue separado.
3. **coverage.py puede no estar instalado en el contenedor**: usar `manage.py test` con conteo manual si es necesario; instalar `pytest-cov` en dev dependencies si no está.

## Completion Criteria

- [ ] `python manage.py test accounting accounts budget memberships net_worth core` pasa sin errores
- [ ] `ruff check .` limpio
- [ ] `mypy .` limpio
- [ ] `net_worth/tests/test_net_worth.py` eliminado; reemplazado por 7 ficheros de dominio
- [ ] `budget/test_services.py` ≥300 líneas con lógica ledger/fallback cubierta
- [ ] Tests de integration cross-domain existen en `accounting/tests/` y `net_worth/tests/test_integration.py`
- [ ] Cobertura documentada por app en `backend-refactor-roadmap.md`
- [ ] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits): `test(core): expand coverage baseline for backend refactor`
