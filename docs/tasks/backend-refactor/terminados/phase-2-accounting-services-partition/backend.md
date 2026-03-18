# Core backend — Phase 2: Partition accounting/services.py

## Title
Core backend — partición de `accounting/services.py` en submódulos cohesivos

## Context
`accounting/services.py` tiene 1,009 líneas y concentra 34 funciones de al menos 5
subdominios distintos: operaciones base del ledger, validación de transacciones,
resúmenes mensuales, pipeline de quick-entry y lógica de budget-suggestions. Este
monolito frena la navegación, hace los cambios pequeños más arriesgados y dificulta la
asignación de responsabilidades cuando hay cruces con `budget` o `net_worth`.

**Prerequisito:** Phase 1 completada (cobertura ≥80% garantiza que el refactor no rompe comportamiento).

## Area
`backend`

## Stack
`core`

## Scope

### En scope
1. Partir `accounting/services.py` en 5 módulos de < 300 líneas cada uno.
2. Mantener `accounting/services.py` como facade de compatibilidad temporal.
3. Actualizar todos los imports del codebase que apuntan a `accounting.services`.
4. Actualizar los tests para que importen directamente desde los nuevos módulos donde corresponda.
5. Verificar que mypy pasa sin errores en todos los módulos nuevos.

### Fuera de scope
1. Cambios de comportamiento funcional.
2. Cambios de contrato API.
3. Tocar `budget`, `net_worth` o cualquier otro app (solo actualizar imports si es necesario).
4. Eliminar la facade `accounting/services.py` (eso ocurre al final de Phase 4).

## Plan

### 1. Diagnóstico previo
Revisar todos los archivos que importan desde `accounting.services`:
```bash
cd core
grep -r "from accounting.services import\|from accounting import services\|accounting\.services\." \
  backend/ --include="*.py" -l
```

### 2. Layout de módulos

**Partición propuesta:**

```
backend/accounting/
  services.py                  ← facade de compatibilidad (re-exports)
  services_ledger.py           ← operaciones base del ledger
  services_transactions.py     ← validación de transacciones y entries
  services_summaries.py        ← monthly-summary y balance-summary
  services_quick_entry.py      ← pipeline de quick-entry
  services_budget.py           ← budget-suggestions y clasificación funcional
```

**Asignación de funciones:**

`services_ledger.py`:
- `LedgerBalanceTotals` (dataclass)
- `normalize_currency_code`
- `serialize_decimal`
- `get_user_ledger_account`
- `get_account_entries`
- `has_account_entries`
- `get_account_balance`
- `compute_account_balance_from_totals`
- `compute_entry_balance_totals`
- `get_or_create_system_account`
- `get_or_create_system_equity_account`
- `validate_liquidity_account`
- `validate_counterparty_account_type`
- `_group_balance_totals_by_account`

`services_transactions.py`:
- `validate_transaction_entries`
- `validate_booking_and_value_dates`
- `validate_balance_summary_filters`

`services_summaries.py`:
- `build_monthly_accounting_summary`
- `build_account_balances_summary`
- `validate_budget_suggestion_filters`
- `_build_period_keys`
- `_serialize_series`

`services_quick_entry.py`:
- `create_quick_transaction`
- `_build_quick_entry_payload`
- `_resolve_entry_classification`
- `build_net_worth_opening_balance_note`
- `ensure_net_worth_opening_balance_transaction`

`services_budget.py`:
- `LedgerClassificationBackfillResult` (dataclass)
- `build_budget_derived_suggestions`
- `backfill_ledger_entry_classification`
- `_build_budget_suggestion_section`
- `_serialize_categorized_suggestions`
- `_resolve_budget_classification`
- `_resolve_backfill_classification`

### 3. Crear los módulos nuevos
Crear cada fichero con sus funciones extraídas directamente del `services.py` original.
Mantener docstrings e imports existentes. Añadir imports de dependencias cruzadas entre
módulos (p.ej. `services_quick_entry.py` importa desde `services_ledger.py`).

### 4. Actualizar `services.py` como facade
```python
# accounting/services.py — facade de compatibilidad
# Re-exports para no romper imports externos durante la transición.
from .services_ledger import (
    LedgerBalanceTotals,
    normalize_currency_code,
    serialize_decimal,
    get_user_ledger_account,
    # ... resto
)
from .services_transactions import (
    validate_transaction_entries,
    # ...
)
# ... etc.
```

### 5. Actualizar imports en el codebase
Buscar todos los imports de `accounting.services` en:
- `accounting/views.py`
- `accounting/tests/test_accounting.py`
- `budget/services.py` (si importa de accounting)
- `net_worth/services*.py` (si importan de accounting)

Actualizar cada import para apuntar directamente al módulo nuevo (no a la facade).

### 6. Verificar que mypy y tests pasan
```bash
cd core
docker compose exec backend mypy accounting/
docker compose exec backend python manage.py test accounting
```

## Validation

```bash
# 1. Tests pasan
cd core
docker compose exec backend python manage.py test accounting accounts budget memberships net_worth core

# 2. Calidad
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .
docker compose exec backend mypy .

# 3. No hay imports rotos
docker compose exec backend python -c "
import accounting.services as s
import accounting.services_ledger as sl
import accounting.services_transactions as st
import accounting.services_summaries as ss
import accounting.services_quick_entry as sqe
import accounting.services_budget as sb
print('All imports OK')
"
```

Resultados esperados:
- Todos los tests pasan sin cambios de comportamiento
- Ningún módulo nuevo > 300 líneas
- `ruff` y `mypy` en verde

## Required Documentation Updates

- [ ] `core/docs/roadmap/backend-refactor-roadmap.md` — marcar Phase 2 completada, actualizar checklist de `accounting`
- [ ] `core/docs/project-status.md` — actualizar estado de la tarea

## Risks

1. **Imports circulares**: los módulos nuevos pueden tener dependencias cruzadas. Resolver usando imports dentro de funciones si es necesario; preferir `services_ledger` como módulo base sin dependencias de otros módulos del mismo app.
2. **Funciones privadas con `_` prefix compartidas entre módulos**: moverlas al módulo más bajo en la jerarquía o duplicar si son helpers genéricos pequeños.
3. **mypy puede detectar nuevos errores de tipo** al tener módulos más pequeños y explícitos — corregirlos en esta fase.

## Completion Criteria

- [ ] `python manage.py test accounting accounts budget memberships net_worth core` pasa sin errores
- [ ] `ruff check .` limpio
- [ ] `mypy .` limpio
- [ ] `accounting/services.py` no contiene lógica de negocio — solo re-exports
- [ ] Todos los módulos nuevos < 300 líneas
- [ ] Todos los imports en el codebase apuntan a los módulos directos, no a la facade
- [ ] Spec movida a `terminados/`
- [ ] Commit: `refactor(accounting): partition services.py into domain modules`
