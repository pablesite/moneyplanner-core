# Core backend — Phase 4: Cross-domain boundary enforcement

## Title
Core backend — enforcement de boundaries cross-domain y atomicidad

## Context
Los tres dominios principales del backend Core (`accounting`, `budget`, `net_worth`)
interactúan en múltiples flujos: `quick-entry` genera entradas contables que afectan
summaries de budget; los activos y pasivos sincronizan compromisos presupuestarios;
los snapshots pueden depender de balances contables. Estos cruces existen pero no están
documentados de forma explícita ni tienen garantías de atomicidad consistentes.
Esta fase cierra la deuda estructural del refactor sin tocar contratos API.

**Prerequisito:** Phase 3 completada.

## Area
`backend`

## Stack
`core`

## Scope

### En scope
1. Auditar y documentar la tabla de responsabilidades de cada dominio.
2. Añadir `transaction.atomic` donde haya side effects cruzados sin protección.
3. Añadir integration tests específicos para cada cruce de dominio que hoy no existan.
4. Actualizar `backend-refactor-roadmap.md` como cierre formal del refactor estructural.

### Fuera de scope
1. Cambios de comportamiento funcional o de contrato API.
2. Refactors dentro de un único dominio (ya cubiertos en fases anteriores).
3. Optimización de rendimiento (solo si hay evidencia de N+1, no como preventivo).

## Plan

### 1. Tabla de responsabilidades (a documentar en el roadmap)

| Dominio | Responsabilidad única | No debe hacer |
|---------|----------------------|---------------|
| `accounting` | Registrar movimientos contables reales. Calcular balances de cuentas. Clasificar entries. | Modificar directamente entradas de budget. Acceder a assets/liabilities. |
| `budget` | Plan anual y seguimiento mensual. Generar compromisos presupuestarios para activos/pasivos. | Escribir en el ledger contable. Calcular balances de cuentas. |
| `net_worth` | Calcular posición patrimonial. Leer balances contables via `accounting.services`. Sincronizar compromisos en budget para activos/pasivos. | Escribir en el ledger directamente. Acceder a budget entries de forma distinta a la sincronización de compromisos. |

### 2. Auditoría de `transaction.atomic`

Revisar los siguientes flujos y añadir `@transaction.atomic` o `with transaction.atomic()` donde falten:

a) **`accounting/services_quick_entry.py` → `create_quick_transaction`**:
   - Crea la transacción + entries en una operación atómica
   - Si el entry lleva clasificación anual (income/expense link), la asignación debe ser parte del mismo atomic block

b) **`net_worth/services_assets_budget.py` → `sync_generated_budget_commitments_for_asset`**:
   - Borrado + recreación de compromisos debe ser atómica

c) **`net_worth/services_liabilities_budget.py` → `sync_generated_budget_commitments_for_liability`**:
   - Ídem para pasivos

d) **`memberships/services.py` → sync de ownership-links**:
   - Actualización de ownership + side effects en budget deben estar en el mismo atomic block

e) **`net_worth/services_snapshots.py` → `import_snapshots_bulk_for_user`**:
   - Import bulk debe ser todo-o-nada

### 3. Integration tests cross-domain

Añadir en `accounting/tests/test_accounting.py` o en un nuevo
`accounting/tests/test_integration.py`:

**accounting ↔ budget:**
```python
# Test: quick-entry con clasificación funcional actualiza summaries de budget
def test_quick_entry_updates_budget_summary(): ...

# Test: entry con annual_expense_entry → summary mensual refleja la entrada
def test_entry_with_annual_expense_link_appears_in_monthly_summary(): ...

# Test: backfill de clasificación no rompe summaries existentes
def test_backfill_classification_preserves_monthly_summaries(): ...
```

**accounting ↔ net_worth:**
```python
# Test: asset con tracking_mode=accounting → balance contable como valor efectivo
def test_asset_tracking_mode_accounting_uses_ledger_balance(): ...

# Test: ensure_net_worth_opening_balance_transaction es idempotente
def test_opening_balance_transaction_idempotent(): ...
```

**net_worth ↔ budget:**
```python
# Test: sync_generated_budget_commitments_for_asset actualiza budget entries
def test_asset_budget_sync_creates_correct_commitments(): ...

# Test: delete_generated_budget_commitments_for_asset limpia correctamente
def test_asset_budget_delete_removes_all_commitments(): ...

# Test: fallo parcial en sync no deja estado inconsistente (atomicidad)
def test_asset_budget_sync_is_atomic(): ...
```

**memberships ↔ net_worth:**
```python
# Test: ownership-links/sync actualiza porcentajes de assets ligados
def test_ownership_sync_updates_asset_percentages(): ...
```

### 4. Actualizar documentación de boundaries

Añadir en `backend-refactor-roadmap.md` una sección **"Boundaries estabilizados"**:
- Tabla de responsabilidades definitiva
- Lista de flujos atómicos garantizados
- Lista de side effects documentados por dominio

### 5. Ejecutar suite completa
```bash
cd core
docker compose exec backend python manage.py test accounting accounts budget memberships net_worth core
docker compose exec backend mypy .
```

## Validation

```bash
cd core
# Suite completa
docker compose exec backend python manage.py test accounting accounts budget memberships net_worth core

# Calidad
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .
docker compose exec backend mypy .
```

Resultados esperados:
- Todos los tests pasan
- Todos los flujos cross-domain tienen `transaction.atomic` donde corresponde
- Tests de integración cross-domain existen y pasan

## Required Documentation Updates

- [ ] `core/docs/roadmap/backend-refactor-roadmap.md` — añadir sección "Boundaries estabilizados"; marcar Phase 4 completada
- [ ] `core/docs/project-status.md` — actualizar estado de la tarea

## Risks

1. **Añadir `transaction.atomic` puede revelar deadlocks** en tests que usan transacciones anidadas: verificar con `ATOMIC_REQUESTS=False` en tests de integración si es necesario.
2. **Los tests de atomicidad con rollback** pueden ser complejos de escribir correctamente en Django TestCase (que ya usa transacciones). Usar `TestCase.assertRaises` + `transaction.on_commit` hooks si es necesario.

## Completion Criteria

- [ ] Tabla de responsabilidades documentada en `backend-refactor-roadmap.md`
- [ ] `transaction.atomic` añadido en los 5 flujos identificados
- [ ] Integration tests cross-domain existen en `accounting/tests/` o `net_worth/tests/test_integration.py`
- [ ] `python manage.py test accounting accounts budget memberships net_worth core` pasa
- [ ] `ruff check .` y `mypy .` limpios
- [ ] Spec movida a `terminados/`
- [ ] Commit: `refactor(core): enforce cross-domain boundaries and atomicity`
