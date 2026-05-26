# Core backend — Phase 4: Cross-domain boundary enforcement

## Title
Core backend — enforcement de boundaries cross-domain y atomicidad

## Context
Los tres dominios principales del backend Core (`accounting`, `budget`, `net_worth`)
interact in multiple flows: `quick-entry` generates accounting entries that affect
summaries de budget; los activos y pasivos sincronizan compromisos presupuestarios;
snapshots can depend on accounting balances. These crossings exist but are not
explicitly documented nor do they have consistent atomicity guarantees.
Esta fase cierra la deuda estructural del refactor sin tocar contratos API.

**Prerequisito:** Phase 3 completada.

## Area
`backend`

## Stack
`core`

## Scope

### En scope
1. Auditar y documentar la tabla de responsabilidades de cada dominio.
2. Add `transaction.atomic` where there are unprotected crossed side effects.
3. Add specific integration tests for each domain crossing that do not exist today.
4. Update `backend-refactor-roadmap.md` as a formal closure of the structural refactor.

### Fuera de scope
1. Cambios de comportamiento funcional o de contrato API.
2. Refactors within a single domain (already covered in previous phases).
3. Performance optimization (only if there is evidence of N+1, not as a preventative).

## Plan

### 1. Tabla de responsabilidades (a documentar en el roadmap)

| Domain | Single responsibility | Shouldn't do |
|---------|----------------------|---------------|
| `accounting` | Registrar movimientos contables reales. Calcular balances de cuentas. Clasificar entries. | Modificar directamente entradas de budget. Acceder a assets/liabilities. |
| `budget` | Plan anual y seguimiento mensual. Generar compromisos presupuestarios para activos/pasivos. | Escribir en el ledger contable. Calcular balances de cuentas. |
| `net_worth` | Calculate equity position. Read accounting balances via `accounting.services`. Synchronize commitments in budget for assets/liabilities. | Write to the ledger directly. Access budget entries in a way other than commitment synchronization. |

### 2. `transaction.atomic` audit

Review the following flows and add `@transaction.atomic` or `with transaction.atomic()` where they are missing:

a) **`accounting/services_quick_entry.py` → `create_quick_transaction`**:
- Create the transaction + entries in an atomic operation
- If the entry has an annual classification (income/expense link), the assignment must be part of the same atomic block

b) **`net_worth/services_assets_budget.py` → `sync_generated_budget_commitments_for_asset`**:
- Deletion + recreation of commits must be atomic

c) **`net_worth/services_liabilities_budget.py` → `sync_generated_budget_commitments_for_liability`**:
- Ditto for liabilities

d) **`memberships/services.py` → sync de ownership-links**:
- Ownership update + side effects in budget must be in the same atomic block

e) **`net_worth/services_snapshots.py` → `import_snapshots_bulk_for_user`**:
   - Import bulk debe ser todo-o-nada

### 3. Integration tests cross-domain

Add in `accounting/tests/test_accounting.py` or in a new
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

### 4. Update boundaries documentation

Add a **"Stabilized Boundaries"** section in `backend-refactor-roadmap.md`:
- Tabla de responsabilidades definitiva
- List of guaranteed atomic flows
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
- Cross-domain integration tests exist and pass

## Required Documentation Updates

- [ ] `core/docs/roadmap/backend-refactor-roadmap.md` — add "Stabilized Boundaries" section; mark Phase 4 completed
- [ ] `core/docs/project-status.md` — update task status

## Risks

1. **Adding `transaction.atomic` may reveal deadlocks** in tests that use nested transactions: check with `ATOMIC_REQUESTS=False` in integration tests if necessary.
2. **Los tests de atomicidad con rollback** pueden ser complejos de escribir correctamente en Django TestCase (que ya usa transacciones). Usar `TestCase.assertRaises` + `transaction.on_commit` hooks si es necesario.

## Completion Criteria

- [ ] Tabla de responsabilidades documentada en `backend-refactor-roadmap.md`
- [ ] `transaction.atomic` added in all 5 identified flows
- [ ] Integration tests cross-domain existen en `accounting/tests/` o `net_worth/tests/test_integration.py`
- [ ] `python manage.py test accounting accounts budget memberships net_worth core` pasa
- [ ] `ruff check .` y `mypy .` limpios
- [ ] Spec movida a `terminados/`
- [ ] Commit: `refactor(core): enforce cross-domain boundaries and atomicity`
