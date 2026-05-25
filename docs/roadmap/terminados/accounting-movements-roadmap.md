# Roadmap: accounting movements (Core) - plan ejecutable

## Aim
Introduce an accounting layer of daily movements in Core without breaking equity, budget or monthly closing.

## Status of this document
1. Este documento define el plan operativo de la iniciativa.
2. La especificacion funcional canonica vive en `../architecture/accounting-movements-architecture.md`.
3. La UX canonica de frontend vive en `../frontend/accounting-movements-ux-notes.md`.
4. El trabajo debe ejecutarse en PRs pequenas y validarse dentro de Docker.
5. La subiniciativa de separacion entre cuenta contable, categoria/subcategoria y linea anual de presupuesto vive en `accounting-category-budget-separation-roadmap.md`.

## Actual status (2026-03-15)
1. Fase 1: implementada en codigo
   - backend `accounting` con `LedgerAccount`/`LedgerTransaction`/`LedgerEntry`, CRUD API, validacion de balance y resumen mensual base
   - frontend con dominio dedicado, workspace de movimientos, lista cronologica y formulario avanzado
   - cobertura minima en `backend/accounting/tests/test_accounting.py`, `frontend/src/domains/accounting/__tests__/store.spec.ts` y `frontend/src/views/__tests__/AccountingMovementsView.spec.ts`
2. Fase 2: implementada y cerrada
   - backend disponible para `income`, `expense` y `transfer` via `POST /api/accounting/transactions/quick-entry/`
   - frontend con alta rapida operativa sobre `quick-entry`, fallback a asiento balanceado manual y filtros locales para la lista cronologica
   - saldos actuales y agregados por periodo visibles en la vista via `current_balance` y `GET /api/accounting/accounts/balances/`
   - cobertura reforzada en `frontend/src/domains/accounting/__tests__/store.spec.ts` y `frontend/src/views/__tests__/AccountingMovementsView.spec.ts`
3. Fase 3: implementada y cerrada
   - backend: los resumenes mensuales de `budget` ya mezclan ledger publicado y fallback legacy con cobertura parcial estable
- backend: monthly close liquidity is now ledger-aware for `tracking_mode=accounting` positions, respecting `as_of_date`
- frontend: `BudgetDashboardView` already consumes ledger per line for income and expenses when there is a link with budget
   - frontend: el fallback a check-ins legacy sigue explicito cuando no hay cobertura ledger
   - cobertura reforzada en `backend/accounting/tests/test_accounting.py`, `backend/budget/tests/test_api_checkins.py`, `backend/net_worth/tests/test_net_worth.py` y `frontend/src/views/__tests__/BudgetDashboardView.spec.ts`
4. Fase 4: implementada y cerrada
   - backend: `POST /api/accounting/transactions/quick-entry/` soporta `investment_purchase` y `debt_payment` con desglose principal/interes cuando aplica
   - frontend: `AccountingMovementsView` y `NetWorthView` exponen flujos y actividad contable para posiciones `tracking_mode=accounting`
   - cobertura reforzada en `backend/accounting/tests/test_accounting.py`, `backend/net_worth/tests/test_net_worth.py` y `frontend/src/views/__tests__/NetWorthView.spec.ts`
5. Fase 5: implementada y cerrada
   - backend: endpoint `GET /api/accounting/transactions/budget-suggestions/` con series mensuales historicas y sugerencias orientativas anualizadas por categoria/subcategoria
   - frontend: `BudgetDashboardView` muestra lectura de sugerencias ledger para planificacion sin bloquear la edicion manual del presupuesto
   - cobertura base en `backend/accounting/tests/test_accounting.py` y `frontend/src/views/__tests__/BudgetDashboardView.spec.ts`
6. Fase 4b (integracion de existentes): implementada y cerrada
- backend: idempotent auto-bind/auto-create for `Asset`/`Liability` in `tracking_mode=accounting` with explicit state by position (`linked`, `auto_created`, `needs_review`)
   - backend: para posiciones con enlace inseguro/incompatible se preserva fallback legacy y se marca `needs_review` sin forzar enlaces inseguros
- frontend: `NetWorthView` shows the state `needs_review` as an actionable gap and avoids reading ledger activity in that state
   - cobertura base reforzada en `backend/net_worth/tests/test_net_worth.py` y `frontend/src/views/__tests__/NetWorthView.spec.ts`

## Principios de trabajo
1. PRs pequenas y reversibles.
2. Compatibilidad temporal con eventos y check-ins legacy.
3. Validacion en Docker del stack afectado.
4. Primero cobertura minima y contratos, luego extension funcional.
5. No duplicar logica existente entre `budget`, `net_worth` y el nuevo dominio `accounting`.

## Subiniciativa abierta
### Separacion entre cuenta contable, categoria y presupuesto anual
1. Existe un roadmap especifico en `accounting-category-budget-separation-roadmap.md`.
2. Your goal is to decouple:
   - la cuenta contable como capa de impacto,
   - la categoria/subcategoria como clasificacion funcional del movimiento,
   - la linea anual como capa de plan.
3. Esa iniciativa no reabre el roadmap general completo de `accounting`, pero si redefine la forma en que `budget` debe consumir ejecucion ledger.
4. Cualquier PR que toque esa separacion debe seguir primero el roadmap especifico y despues volver a este documento para mantener trazabilidad global.

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
- architecture, UX and tasks by specialty aligned

Criterios de salida:
1. Se pueden crear transacciones balanceadas.
2. Se puede listar actividad y cuentas.
3. El backend y frontend del Core siguen en verde en sus validaciones base.

### Fase 2 - Ledger para liquidez
Entregables:
1. Backend
- support for income, expenses and transfers on liquidity accounts
   - agregados de saldo por cuenta
2. Frontend
   - alta rapida de movimientos
   - lista cronologica filtrable
3. Tests
- income, expenses and internal transfers
4. Documentacion
   - actualizar contratos si cambia algun comportamiento acordado

Current status:
1. Backend listo para la fase.
2. Frontend expone alta rapida para `income`, `expense` y `transfer` en `frontend/src/views/AccountingMovementsView.vue`.
3. La actividad del periodo ya es filtrable por texto, cuenta y tipo de movimiento sin pedir cambios de contrato al backend.
4. La vista muestra saldos derivados del ledger por cuenta de liquidez para el periodo seleccionado.
5. El asiento balanceado manual sigue disponible como modo avanzado para no perder capacidad operativa.
6. The minimum store and view coverage confirms the daily fast flow and the reading of balances, so the phase is closed.

Criterios de salida:
1. Los movimientos simples de liquidez se pueden registrar y consultar.
2. Los saldos derivados son reproducibles desde ledger.
3. La vista principal ofrece filtros operativos y estados basicos suficientes para el uso diario.

### Phase 3 - Integration with monthly closing
Entregables:
1. Backend
   - agregados mensuales de ejecucion desde ledger
   - logica de cobertura parcial
2. Frontend
   - `BudgetDashboardView` consume ledger cuando haya cobertura
   - fallback a check-ins legacy cuando no la haya
3. Tests
- regression on monthly closing and partial coverage cases
4. Documentacion
   - notas de convivencia actualizadas si fuese necesario

Current status:
1. Backend cerrado:
   - `budget` resume ejecucion mensual usando ledger publicado cuando existe enlace y fallback a check-ins legacy en el resto
   - `net_worth/liquidity/monthly-summary` ya reconoce cobertura ledger para liquidez `tracking_mode=accounting`
- the accounting balances used by closing and equity respect `as_of_date`, avoiding reading the outstanding balance in historical closings
2. Frontend en convivencia controlada:
- `BudgetDashboardView` already mixes legacy ledger and fallback for income and expenses
   - las filas cubiertas por ledger se presentan como tal y bloquean la edicion de check-ins legacy para evitar doble fuente operativa
- the liquidity reading can now rely on the stabilized backend contract and the UX of the monthly close explicitly covers `ledger`/`fallback`/`parcial` with visible blocking in accounting rows
3. Validacion ejecutada en Docker el 2026-03-15:
   - backend: `ruff check .`, `mypy .`, `python manage.py test accounting --keepdb`, `python manage.py test budget --keepdb`, `python manage.py test net_worth --keepdb`
   - frontend: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run test:unit -- src/views/__tests__/BudgetDashboardView.spec.ts src/views/__tests__/AccountingMovementsView.spec.ts src/domains/accounting/__tests__/store.spec.ts`
   - incidencia conocida de entorno: `docker compose exec backend ruff format --check .` sigue fallando por archivos preexistentes fuera del alcance de esta fase

Criterios de salida:
1. The monthly close can operate with full or partial ledger coverage.
2. El fallback legacy sigue funcionando.
3. La cobertura ledger por linea deja trazable cuando una fila es contable y cuando sigue en fallback legacy.

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

Current status:
1. Backend cerrado:
   - `POST /api/accounting/transactions/quick-entry/` soporta `investment_purchase` y `debt_payment`
   - `debt_payment` separa principal e interes/fees en apuntes distintos, validando `amount = principal + interest`
   - las compras de inversion y pagos de deuda pueden enlazar `Asset`/`Liability` desde el ledger para trazabilidad en patrimonio
2. Frontend operativo:
   - `AccountingMovementsView` expone alta rapida para compra de inversion y pago de deuda con campos condicionales de breakdown
   - la actividad del periodo permite filtrar estos nuevos tipos y mantiene convivencia con `income`/`expense`/`transfer`
   - `NetWorthView` mantiene actividad contable contextual para posiciones `tracking_mode=accounting` y gap explicito cuando falta cuenta enlazada
3. Integration of existing ones (pending):
   - actualmente el enlace contable para posiciones existentes no es totalmente automatico en todos los casos
   - se requiere subfase 4b para cerrar auto-vinculacion/autocreacion con controles de idempotencia y seguridad

Criterios de salida:
1. Las posiciones `accounting` muestran actividad contextual.
2. Patrimonio no pierde comportamiento legacy durante la convivencia.
3. Subfase 4b (integracion de existentes) cerrada con criterios medibles:
- >= 95% of `tracking_mode=accounting` positions remain with a linked account (`linked` or `auto_created`) in environments with valid data
   - 0 duplicados de cuenta por posicion (`Asset`/`Liability`)
   - todos los casos no auto-integrables quedan marcados como `needs_review` con fallback legacy explicito

#### Subfase 4b - Integracion de existentes (`net_worth` -> `accounting`)
Entregables:
1. Backend
   - auto-vinculacion/autocreacion de `LedgerAccount` para `Asset`/`Liability` existentes en `tracking_mode=accounting`
   - reglas de idempotencia: sin duplicados por posicion y sin violar ownership/moneda/tipo
- integration status marking: `linked`, `auto_created`, `needs_review`
2. Frontend
- visibility of link status by position in `NetWorthView`
- clear signal of fallback legacy when status is `needs_review`
3. Tests
   - regresiones en `accounting`, `net_worth` y `monthly close` cubriendo auto-link, auto-create y needs-review
4. Documentacion
- contracts and precedence rules aligned between architecture, roadmap and QA

Criterios de salida de subfase:
1. No se recrea cuenta cuando existe `accounting_account_id` valido y compatible.
2. Se crea y enlaza cuenta cuando falta y la autocreacion es segura.
3. No se fuerza enlace cuando hay incompatibilidad de ownership/moneda/tipo; se marca `needs_review`.
4. `monthly close` y `net worth` priorizan ledger con enlace valido y usan fallback solo cuando no hay cobertura contable segura.

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

Current status:
1. Backend cerrado:
   - `GET /api/accounting/transactions/budget-suggestions/?year=YYYY&lookback_years=N` expone series historicas mensuales para `income` y `expense` por categoria/subcategoria usando solo transacciones `posted`.
   - la sugerencia anual se calcula como promedio mensual de la ventana historica por 12 meses y se entrega como referencia explicita (`method_note`) no automatica.
2. Frontend operativo:
   - `BudgetDashboardView` consume sugerencias historicas del ledger en modo presupuesto y muestra diferencias `plan vs sugerencia` por subcategoria.
   - la experiencia mantiene el presupuesto anual editable; no hay escritura automatica sobre las lineas del plan.

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
2. La convivencia no debe reinterpretarse como migracion masiva automatica.
3. La subfase 4b si habilita integracion automatica controlada por posicion (`linked`/`auto_created`/`needs_review`).
