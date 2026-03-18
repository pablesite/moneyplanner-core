# Core backend — Phase 3: net_worth domain cleanup

## Title
Core backend — partición de hotspots `net_worth` y adelgazamiento de la facade

## Context
`net_worth` tiene dos hotspots que siguen siendo grandes incluso tras la separación
inicial: `services_assets.py` (1,232 líneas, 35 funciones) y `services_liabilities.py`
(1,053 líneas). Ambos mezclan lógica de dominio puro (valuación, eventos, calendarios de
pago) con lógica de sincronización con `budget` (generación y borrado de compromisos
presupuestarios generados). Además, `services.py` es una facade de compatibilidad con
imports dobles que añade una capa innecesaria de indirección una vez que los módulos
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
3. Migrar imports en `services.py` para apuntar directamente a los nuevos submódulos.
4. Reducir `services.py` a únicamente las funciones sin dominio natural en submódulos:
   - `calculate_totals`
   - `get_base_currency_for_user`
   - `get_inflation_region_for_user`
   - `get_inflation_base_period`
   - `get_financed_asset_queryset_for_user`
   - `get_liquidity_asset_queryset_for_user`
   - `NetWorthTotals` (dataclass)
   - `_serialize_money`
5. Actualizar `views.py` para importar directamente desde los módulos, no desde la facade.
6. Actualizar tests para reflejar la nueva estructura de imports.

### Fuera de scope
1. Eliminar `services.py` completamente (deuda técnica residual a evaluar en Phase 4).
2. Cambios de comportamiento funcional.
3. Cambios de contrato API.

## Plan

### 1. Diagnóstico
Listar todos los importadores de `net_worth.services`:
```bash
cd core
grep -r "from net_worth.services import\|from net_worth import services\|net_worth\.services\." \
  backend/ --include="*.py" -l
```

### 2. Partición de `services_assets.py`

**`services_assets_core.py`** — valuación, eventos, helpers de cálculo:
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

**`services_assets_budget.py`** — sincronización con budget:
- `_format_ownership_percent`
- `_get_generated_asset_owner_name`
- `_get_generated_asset_expense_profile`
- `_last_day_of_month`
- `_add_months_preserve_day`
- `_build_investment_contribution_schedule`
- `sync_generated_budget_commitments_for_asset`
- `delete_generated_budget_commitments_for_asset`

### 3. Partición de `services_liabilities.py`

**`services_liabilities_core.py`** — creación, valuación, calendario de pagos:
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

**`services_liabilities_budget.py`** — sincronización con budget:
- `get_generated_liability_expense_profile`
- `sync_generated_budget_commitments_for_liability`
- `delete_generated_budget_commitments_for_liability`

### 4. Actualizar `services.py` (facade residual)
Mantener solo las funciones sin módulo natural (listadas en scope) y actualizar los
re-exports para apuntar a los nuevos submódulos:
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
- `views.py`: importar desde módulos directos donde sea posible
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
- Ningún módulo nuevo > 400 líneas
- `services.py` ≤ 80 líneas (solo re-exports + funciones base)
- `ruff` y `mypy` en verde

## Required Documentation Updates

- [ ] `core/docs/roadmap/backend-refactor-roadmap.md` — actualizar estado de Fase 3, marcar net_worth hotspots como atendidos
- [ ] `core/docs/project-status.md` — actualizar estado de la tarea

## Risks

1. **`_last_day_of_month` duplicada** en assets y liabilities: consolidar en un único módulo utilitario o en `services_liabilities_core.py` e importar desde assets si necesita.
2. **imports circulares** entre `services_assets_budget.py` y `budget.services`: verificar que la dirección del import es assets → budget (no budget → assets).
3. **facade `services.py` con re-exports anidados**: mypy puede tener dificultades con re-exports en cadena. Asegurarse de que los `__all__` están definidos en los módulos hoja.

## Completion Criteria

- [ ] `python manage.py test net_worth` pasa sin errores
- [ ] `python manage.py test accounting accounts budget memberships net_worth core` pasa
- [ ] `ruff check .` limpio
- [ ] `mypy .` limpio
- [ ] `services_assets.py` eliminado; reemplazado por `services_assets_core.py` + `services_assets_budget.py`
- [ ] `services_liabilities.py` eliminado; reemplazado por `services_liabilities_core.py` + `services_liabilities_budget.py`
- [ ] `services.py` ≤ 80 líneas
- [ ] Spec movida a `terminados/`
- [ ] Commit: `refactor(net_worth): split services_assets and services_liabilities by subdomain`
