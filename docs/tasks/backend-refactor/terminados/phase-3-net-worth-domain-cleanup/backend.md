# Core backend — Phase 3: net_worth domain cleanup

## Title
Core backend — `net_worth` hotspot partitioning and facade thinning

## Context
`net_worth` has two hotspots that remain large even after separation
initial: `services_assets.py` (1,232 lines, 35 functions) and `services_liabilities.py`
(1,053 lines). Both mix pure domain logic (valuation, events,
payment) with synchronization logic with `budget` (generation and deletion of commitments
generated budgets). Additionally, `services.py` is a support facade for
double imports which adds an unnecessary layer of indirection once the modules
directos son estables.

**Prerequisito:** Phase 2 completada.

## Area
`backend`

## Stack
`core`

## Scope

### En scope
1. Partir `services_assets.py` en `services_assets_core.py` + `services_assets_budget.py`.
2. Partir `services_liabilities.py` en `services_liabilities_core.py` + `services_liabilities_budget.py`.
3. Migrate imports in `services.py` to point directly to the new submodules.
4. Reduce `services.py` to only functions without natural domain in submodules:
   - `calculate_totals`
   - `get_base_currency_for_user`
   - `get_inflation_region_for_user`
   - `get_inflation_base_period`
   - `get_financed_asset_queryset_for_user`
   - `get_liquidity_asset_queryset_for_user`
   - `NetWorthTotals` (dataclass)
   - `_serialize_money`
5. Update `views.py` to import directly from the modules, not from the facade.
6. Actualizar tests para reflejar la nueva estructura de imports.

### Fuera de scope
1. Eliminate `services.py` completely (residual technical debt to be evaluated in Phase 4).
2. Cambios de comportamiento funcional.
3. Cambios de contrato API.

## Plan

### 1. Diagnosis
Listar todos los importadores de `net_worth.services`:
```bash
cd core
grep -r "from net_worth.services import\|from net_worth import services\|net_worth\.services\." \
  backend/ --include="*.py" -l
```

### 2. Partition of `services_assets.py`

**`services_assets_core.py`** — valuation, events, calculation helpers:
- `AccountingIntegrationState`
- `_get_accounting_asset_account`
- `ensure_asset_accounting_account`
- `_validate_accounting_asset_account_link`
- `_validate_periodic_investment_payload`
- `_validate_market_value_override_payload`
- `validate_asset_payload`
- `create_asset_for_user`
- `validate_asset_improvement_payload`
- `_whole_months_elapsed`, `_month_start`
- `_get_inflation_index_or_none`, `_get_inflation_growth_factor_or_one`
- `get_default_amortization_term_years`
- `_get_degressive_remaining_ratio`
- `_get_effective_accounting_asset_amount_or_none`
- `get_effective_asset_amount`
- `_get_effective_investment_asset_amount`
- `_get_effective_cash_asset_amount`
- `_get_latest_asset_manual_value`
- `validate_investment_asset_event_payload`
- `validate_liquidity_asset_event_payload`
- `get_investment_asset_events_delta`
- `get_liquidity_asset_events_delta`
- `_get_periodic_investment_delta_since_anchor`
- `_get_latest_liquidity_checkin`
- `_get_liquidity_checkin_effective_date`
- `get_effective_asset_improvement_amount`
- `get_amount_base_value`

**`services_assets_budget.py`** — sync with budget:
- `_format_ownership_percent`
- `_get_generated_asset_owner_name`
- `_get_generated_asset_expense_profile`
- `_last_day_of_month`
- `_add_months_preserve_day`
- `_build_investment_contribution_schedule`
- `sync_generated_budget_commitments_for_asset`
- `delete_generated_budget_commitments_for_asset`

### 3. Partition of `services_liabilities.py`

**`services_liabilities_core.py`** — creation, valuation, payment schedule:
- `_last_day_of_month`
- `validate_liability_payload`
- `create_liability_for_user`
- `validate_liability_event_payload`
- `get_effective_liability_amount`
- `get_liability_events_delta`
- `estimate_liability_monthly_payment_simple`
- `estimate_liability_outstanding_amount_simple`
- `build_liability_installment_schedule_simple`
- `get_liability_first_payment_date`
- `infer_liability_is_asset_backed`

**`services_liabilities_budget.py`** — sync with budget:
- `get_generated_liability_expense_profile`
- `sync_generated_budget_commitments_for_liability`
- `delete_generated_budget_commitments_for_liability`

### 4. Actualizar `services.py` (facade residual)
Keep only the functions without natural module (listed in scope) and update the
re-exports to target the new submodules:
```python
from .services_assets_core import (
    validate_asset_payload,
    create_asset_for_user,
    # ...
)
from .services_assets_budget import (
    sync_generated_budget_commitments_for_asset,
    delete_generated_budget_commitments_for_asset,
)
# ...
```

### 5. Actualizar `views.py` y tests
- `views.py`: import from direct modules where possible
- `tests/test_assets.py`: importar desde `services_assets_core` / `services_assets_budget`
- `tests/test_liabilities.py`: importar desde `services_liabilities_core` / `services_liabilities_budget`

### 6. Verificar
```bash
cd core
docker compose exec backend mypy net_worth/
docker compose exec backend python manage.py test net_worth
```

## Validation

```bash
cd core
# Tests completos
docker compose exec backend python manage.py test accounting accounts budget memberships net_worth core

# Calidad
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .
docker compose exec backend mypy .

# Verificar que services.py solo tiene funciones sin dominio natural
# (manual: abrir el fichero y confirmar que no tiene lógica de negocio de assets/liabilities)
```

Resultados esperados:
- Todos los tests pasan
- No new module > 400 lines
- `services.py` ≤ 80 lines (only re-exports + base functions)
- `ruff` y `mypy` en verde

## Required Documentation Updates

- [ ] `core/docs/roadmap/backend-refactor-roadmap.md` — update Phase 3 status, mark net_worth hotspots as served
- [ ] `core/docs/project-status.md` — update task status

## Risks

1. **`_last_day_of_month` duplicated** in assets and liabilities: consolidate into a single utility module or into `services_liabilities_core.py` and import from assets if needed.
2. **circular imports** between `services_assets_budget.py` and `budget.services`: verify that the import direction is assets → budget (not budget → assets).
3. **facade `services.py` with nested re-exports**: mypy may have difficulties with chained re-exports. Make sure the `__all__` are defined in the leaf modules.

## Completion Criteria

- [ ] `python manage.py test net_worth` pasa sin errores
- [ ] `python manage.py test accounting accounts budget memberships net_worth core` pasa
- [ ] `ruff check .` limpio
- [ ] `mypy .` limpio
- [ ] `services_assets.py` eliminado; reemplazado por `services_assets_core.py` + `services_assets_budget.py`
- [ ] `services_liabilities.py` eliminado; reemplazado por `services_liabilities_core.py` + `services_liabilities_budget.py`
- [ ] `services.py` ≤ 80 lines
- [ ] Spec movida a `terminados/`
- [ ] Commit: `refactor(net_worth): split services_assets and services_liabilities by subdomain`
