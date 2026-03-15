# Roadmap: accounting movements (Core) - plan ejecutable

## Objetivo
Introducir una capa contable de movimientos diarios en Core sin romper patrimonio, presupuesto ni cierre mensual.

## Estado de este documento
1. Este documento define el plan operativo de la iniciativa.
2. La especificacion funcional canonica vive en `../architecture/accounting-movements-architecture.md`.
3. La UX canonica de frontend vive en `../frontend/accounting-movements-ux-notes.md`.
4. El trabajo debe ejecutarse en PRs pequenas y validarse dentro de Docker.

## Estado real (2026-03-15)
1. Fase 1: implementada en codigo
   - backend `accounting` con `LedgerAccount`/`LedgerTransaction`/`LedgerEntry`, CRUD API, validacion de balance y resumen mensual base
   - frontend con dominio dedicado, workspace de movimientos, lista cronologica y formulario avanzado
   - cobertura minima en `backend/accounting/tests/test_accounting.py`, `frontend/src/domains/accounting/__tests__/store.spec.ts` y `frontend/src/views/__tests__/AccountingMovementsView.spec.ts`
2. Fase 2: implementada y cerrada
   - backend disponible para `income`, `expense` y `transfer` via `POST /api/accounting/transactions/quick-entry/`
   - frontend con alta rapida operativa sobre `quick-entry`, fallback a asiento balanceado manual y filtros locales para la lista cronologica
   - saldos actuales y agregados por periodo visibles en la vista via `current_balance` y `GET /api/accounting/accounts/balances/`
   - cobertura reforzada en `frontend/src/domains/accounting/__tests__/store.spec.ts` y `frontend/src/views/__tests__/AccountingMovementsView.spec.ts`
3. Fase 3: backend cerrado, frontend en convivencia controlada
   - backend: los resúmenes mensuales de `budget` ya mezclan ledger publicado y fallback legacy con cobertura parcial estable
   - backend: la liquidez del cierre mensual ya es ledger-aware para posiciones `tracking_mode=accounting`, respetando `as_of_date`
   - frontend: `BudgetDashboardView` ya consume ledger por linea para ingresos y gastos cuando existe enlace con presupuesto
   - frontend: el fallback a check-ins legacy sigue explicito cuando no hay cobertura ledger
   - cobertura reforzada en `backend/accounting/tests/test_accounting.py`, `backend/budget/tests/test_api_checkins.py`, `backend/net_worth/tests/test_net_worth.py` y `frontend/src/views/__tests__/BudgetDashboardView.spec.ts`
4. Fases posteriores pendientes
   - actividad contable contextual mas profunda en patrimonio
   - compras de inversion y pagos de deuda con breakdown especializado
   - sugerencias historicas derivadas del ledger

## Principios de trabajo
1. PRs pequenas y reversibles.
2. Compatibilidad temporal con eventos y check-ins legacy.
3. Validacion en Docker del stack afectado.
4. Primero cobertura minima y contratos, luego extension funcional.
5. No duplicar logica existente entre `budget`, `net_worth` y el nuevo dominio `accounting`.

## Fases
### Fase 1 - Dominio base `accounting`
Entregables:
1. Backend
   - app `accounting`
   - modelos `LedgerTransaction`, `LedgerEntry`, `LedgerAccount`
   - serializers y endpoints iniciales
2. Frontend
   - dominio `frontend/src/domains/accounting/*`
   - store y modelos cliente base
3. Tests
   - pruebas de balance, CRUD inicial y validaciones
4. Documentacion
   - arquitectura, UX y tareas por especialidad alineadas

Criterios de salida:
1. Se pueden crear transacciones balanceadas.
2. Se puede listar actividad y cuentas.
3. El backend y frontend del Core siguen en verde en sus validaciones base.

### Fase 2 - Ledger para liquidez
Entregables:
1. Backend
   - soporte para ingresos, gastos y transferencias sobre cuentas de liquidez
   - agregados de saldo por cuenta
2. Frontend
   - alta rapida de movimientos
   - lista cronologica filtrable
3. Tests
   - ingresos, gastos y transferencias internas
4. Documentacion
   - actualizar contratos si cambia algun comportamiento acordado

Estado actual:
1. Backend listo para la fase.
2. Frontend expone alta rapida para `income`, `expense` y `transfer` en `frontend/src/views/AccountingMovementsView.vue`.
3. La actividad del periodo ya es filtrable por texto, cuenta y tipo de movimiento sin pedir cambios de contrato al backend.
4. La vista muestra saldos derivados del ledger por cuenta de liquidez para el periodo seleccionado.
5. El asiento balanceado manual sigue disponible como modo avanzado para no perder capacidad operativa.
6. La cobertura minima de store y vista confirma el flujo rapido diario y la lectura de balances, por lo que la fase queda cerrada.

Criterios de salida:
1. Los movimientos simples de liquidez se pueden registrar y consultar.
2. Los saldos derivados son reproducibles desde ledger.
3. La vista principal ofrece filtros operativos y estados basicos suficientes para el uso diario.

### Fase 3 - Integracion con cierre mensual
Entregables:
1. Backend
   - agregados mensuales de ejecucion desde ledger
   - logica de cobertura parcial
2. Frontend
   - `BudgetDashboardView` consume ledger cuando haya cobertura
   - fallback a check-ins legacy cuando no la haya
3. Tests
   - regresion sobre cierre mensual y casos de cobertura parcial
4. Documentacion
   - notas de convivencia actualizadas si fuese necesario

Estado actual:
1. Backend cerrado:
   - `budget` resume ejecucion mensual usando ledger publicado cuando existe enlace y fallback a check-ins legacy en el resto
   - `net_worth/liquidity/monthly-summary` ya reconoce cobertura ledger para liquidez `tracking_mode=accounting`
   - los saldos contables usados por cierre y patrimonio respetan `as_of_date`, evitando leer saldo vivo en cierres historicos
2. Frontend en convivencia controlada:
   - `BudgetDashboardView` ya mezcla ledger y fallback legacy para ingresos y gastos
   - la lectura de liquidez ya puede apoyarse en el contrato backend estabilizado, aunque la UX todavia puede refinar la presentacion de cobertura

Criterios de salida:
1. El cierre mensual puede operar con cobertura ledger completa o parcial.
2. El fallback legacy sigue funcionando.

### Fase 4 - Integracion con patrimonio
Entregables:
1. Backend
   - relacion entre `LedgerAccount` y posiciones `Asset`/`Liability`
   - soporte inicial para compras de inversion y pagos de deuda
2. Frontend
   - `NetWorthView` muestra actividad contable en posiciones `accounting`
3. Tests
   - regresion sobre timeline y detalle de posicion
4. Documentacion
   - actualizar notas UX si la integracion cambia el workspace

Criterios de salida:
1. Las posiciones `accounting` muestran actividad contextual.
2. Patrimonio no pierde comportamiento legacy durante la convivencia.

### Fase 5 - Sugerencias de presupuesto derivado
Entregables:
1. Backend
   - agregados historicos mensuales por categoria
   - endpoint de sugerencias
2. Frontend
   - lectura de series historicas y sugerencias para planificacion
3. Tests
   - contratos de agregacion y consistencia temporal
4. Documentacion
   - reflejar alcance exacto de la sugerencia sin vender automatismos no implementados

Criterios de salida:
1. El historico ledger puede informar presupuesto futuro.
2. El presupuesto anual sigue siendo editable y sigue siendo la capa de plan.

## Riesgos principales
1. Doble fuente de verdad entre ledger y modelos legacy.
2. UX demasiado compleja para tareas simples.
3. Drift funcional entre `budget`, `net_worth` y `accounting`.

## Validacion minima por stack
1. Backend Core (`core/backend/`)
   - `docker compose exec backend ruff check .`
   - `docker compose exec backend ruff format --check .`
   - `docker compose exec backend mypy .`
   - tests del dominio afectado
2. Frontend Core (`core/frontend/`)
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`

## Nota de convivencia
1. Los eventos legacy siguen activos hasta que una fase posterior marque su sustitucion explicita.
2. La convivencia no debe reinterpretarse como migracion automatica.
