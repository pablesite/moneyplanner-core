# Roadmap: separacion entre cuenta contable, categoria y presupuesto anual

## Document status
1. Roadmap terminado.
2. Alcance Core con espejo Core frontend cuando aplique.
3. Este documento conserva el handoff historico de la separacion entre:
   - cuenta contable (donde impacta),
   - categoria/subcategoria (por que ocurre),
   - linea anual de presupuesto (que plan cubre).

## Final status (2026-05-16)
1. `LedgerEntry` conserva solo la clasificacion funcional (`flow_family`, `category_key`, `subcategory_key`) y enlaces a patrimonio (`Asset`/`Liability`) cuando aplican.
2. Los enlaces operativos `annual_income_entry_id` y `annual_expense_entry_id` fueron eliminados de modelo, API, quick-entry, portable data y frontend.
3. Presupuesto calcula ejecutado desde movimientos publicados por taxonomia + mes; los check-ins manuales siguen siendo fallback del plan, pero ya no existe fallback ledger por FK a linea anual.
4. La trazabilidad de movimientos importados se conserva mediante `origin`, `import_source` e `import_fingerprint`.

## Progress status (2026-03-16)
1. Fase 1 implementada en `core/backend/accounting`:
   - `LedgerEntry` ya persiste `flow_family`, `category_key` y `subcategory_key`.
   - La API de `transactions` y `entries` ya devuelve la nueva clasificacion.
   - Se mantiene compatibilidad con `annual_income_entry_id` y `annual_expense_entry_id`.
2. Fase 2 implementada en `core/backend` y `core/frontend`:
   - `quick-entry` acepta categoria/subcategoria como contrato primario en `income`/`expense` y coste de `debt_payment` cuando aplica.
   - `AccountingMovementsView` ya pide `Categoria` + `Subcategoria` y deja la linea anual como opcional secundaria.
   - La UX reduce protagonismo de cuentas `income`/`expense` como cuentas operativas visibles.
3. Fase 3 implementada en `core/backend`, `core/frontend` y tests:
   - `budget` ya agrega ejecucion mensual por taxonomia `category_key`/`subcategory_key` del ledger como fuente primaria.
   - `budget` mantiene fallback legacy de lectura por `annual_*` cuando faltan clasificaciones nuevas en historico.
   - `accounting` ya genera resumen mensual y sugerencias de presupuesto consumiendo clasificacion propia del ledger con fallback legacy.
- `BudgetDashboardView` distinguishes `Ledger categorizado`, `Fallback legacy` and `Pending clasificar` when automatic alignment is not safe.
4. Fase 4 implementada en `core/backend` y tests:
   - el backfill historico desde `annual_*` a `flow_family` + `category_key` + `subcategory_key` ya se completo y el comando operativo temporal fue retirado.
   - la compatibilidad de lectura `annual_*` queda solo como fallback para historicos no migrados.
- ambiguous or partially classified cases are not forced: they remain without new classification and are displayed as `Pending clasificar`.
5. Fase 5 implementada en `core/frontend`, `core/backend` residual y tests:
   - la creacion manual de cuentas oculta `income` y `expense` como tipos operativos visibles.
   - las cuentas legacy quedan relegadas a `Contrapartidas tecnicas del sistema` en la UX.
   - `quick-entry` deja la vinculacion `annual_*` en un bloque secundario opcional y ya no envia ids legacy vacios cuando no hay alineacion explicita con el plan.

## Aim
Separar de forma explicita y reversible las tres capas funcionales que hoy se mezclan parcialmente en `accounting` y `budget`, de modo que:
1. `accounting` sea la fuente de verdad de la ejecucion diaria y del impacto patrimonial.
2. La categoria/subcategoria sea una clasificacion funcional propia del movimiento y no una consecuencia obligatoria de una linea anual.
3. `budget` siga siendo la capa de plan anual y consuma ejecucion categorizada sin convertirse en la fuente de clasificacion del ledger.

## Problema funcional a resolver
Today the product already supports daily movements, monthly closing, budget suggestions and contextual activity in assets. However, the conceptual separation between layers remains incomplete:
1. `LedgerAccount.account_type` todavia incluye `income` y `expense`, lo que empuja a tratar ingreso/gasto como cuentas operativas en vez de como categorias mentales del usuario.
2. `LedgerEntry` clasifica ejecucion principalmente mediante `annual_income_entry` / `annual_expense_entry`.
3. `budget` resume ejecucion ledger por FK directa a linea anual, no por una capa propia de categoria/subcategoria en `accounting`.
4. `AccountingMovementsView` pide una "categoria anual opcional", no una categoria funcional autonoma del movimiento.
5. `net_worth` esta mejor alineado: depende de cuentas y saldos, no del plan.

The target use case is to log, for example, an entry like `Ayuda por Madre Trabajadora` in:
1. cuenta de impacto: `Kutxa / EUR`,
2. categoria/subcategoria: `Prestaciones y ayudas -> Subsidio/Ayuda publica`,
3. linea anual de presupuesto: una fila del plan alineada con esa misma categoria/subcategoria.

## Current actual status
1. Modelo `accounting`
   - `LedgerAccount` mantiene `asset`, `liability`, `equity`, `income`, `expense`.
   - `LedgerEntry` puede enlazar `AnnualIncomeEntry` y `AnnualExpenseEntry`.
   - `QuickLedgerTransactionSerializer` crea o reutiliza cuentas de sistema `income` / `expense` cuando no se informa contrapartida explicita.
2. API `accounting`
   - `POST /api/accounting/transactions/quick-entry/` soporta `income`, `expense`, `transfer`, `investment_purchase`, `debt_payment`.
- `GET /api/accounting/transactions/monthly-summary/` summarizes income/expenses based on the `annual_*` links.
   - `GET /api/accounting/transactions/budget-suggestions/` agrega historico por categoria/subcategoria derivadas de `AnnualIncomeEntry` / `AnnualExpenseEntry`.
3. `budget`
   - `build_income_monthly_plan_vs_executed_summary` y `build_expense_monthly_plan_vs_executed_summary` mezclan ledger y check-ins legacy con cobertura parcial.
   - La cobertura ledger se resuelve por `(annual_entry_id, month)`.
4. Frontend `accounting`
   - `AccountingMovementsView` usa tipo de movimiento y selector de "categoria anual opcional".
   - El catalogo de cuentas sigue mostrando `Ingreso` y `Gasto` como tipos de cuenta.
5. Frontend `budget`
   - `BudgetDashboardView` consume ejecucion ledger por linea cuando existe enlace a presupuesto.
   - El fallback a check-ins legacy sigue operativo y visible.
6. `net_worth`
   - Sigue centrado en cuentas `asset` / `liability`.
   - La actividad contable contextual para posiciones `tracking_mode=accounting` no depende del plan anual.

## Design decisions already made
1. Taxonomia unica compartida
   - La clasificacion funcional del ledger reutilizara la taxonomia canonica de `budget`.
   - No se abrira una taxonomia paralela en `accounting` en esta iniciativa.
2. Estrategia `category-first`
   - El movimiento guardara categoria/subcategoria como capa primaria de clasificacion.
   - El enlace a linea anual sera opcional y secundario.
3. Corte de nuevas escrituras legacy con compatibilidad breve de lectura
   - Las nuevas escrituras deben converger al contrato nuevo.
   - Durante una ventana corta de transicion, `budget` podra seguir leyendo los links legacy cuando falte la nueva clasificacion.
4. `net_worth` fuera de alcance funcional salvo integraciones ya existentes
   - No se reabre el modelo patrimonial.
   - Solo se protege que patrimonio siga leyendo cuenta/saldo/actividad sin regresiones.

## Modelo target
### Separacion funcional
1. Cuenta contable
   - Responde a `donde impacta`.
   - Vive en `LedgerAccount` + `LedgerEntry`.
   - Debe seguir siendo la fuente de saldo y de integracion patrimonial.
2. Categoria/subcategoria
   - Responde a `por que ocurre`.
   - Debe vivir en `accounting` como clasificacion funcional propia del movimiento.
   - No debe depender de una linea anual concreta para existir.
3. Linea anual de presupuesto
   - Responde a `que plan cubre`.
   - Sigue viviendo en `AnnualIncomeEntry` / `AnnualExpenseEntry`.
   - Se alinea con la ejecucion por taxonomia compartida y, opcionalmente, por referencia explicita a la linea.

### Fuente de verdad por dominio
1. `accounting`
   - Fuente primaria de ejecucion diaria.
   - Fuente primaria de clasificacion funcional del movimiento.
   - Fuente primaria de saldo para cuentas operativas y posiciones `tracking_mode=accounting`.
2. `budget`
   - Fuente primaria del plan anual.
   - Consumidor de ejecucion categorizada desde `accounting`.
3. `net_worth`
   - Consumidor de cuentas y actividad ledger para activos/pasivos enlazados.
   - No propietario de la clasificacion presupuestaria.

### Regla de precedencia
1. Para clasificar ejecucion, la clasificacion funcional propia del ledger sera la fuente primaria.
2. El enlace a linea anual sera opcional y secundario.
3. Durante la ventana de compatibilidad, si una transaccion legacy no tiene clasificacion funcional nueva, `budget` podra caer temporalmente al link `annual_*`.

### Taxonomia recomendada
1. Mantener las claves canonicamente ya definidas en:
   - `docs/architecture/annual-income-taxonomy.md`
   - `docs/architecture/annual-expense-taxonomy.md`
2. No introducir ahora una segunda taxonomia para `accounting`.
3. Los labels UX pueden seguir en espanol, pero API y storage deben mantener claves estables `snake_case`.

## Impacto por dominio
### `accounting`
1. Introducir una capa de clasificacion funcional propia del movimiento.
2. Reducir el rol visible de `income` / `expense` como tipos de cuenta gestionables por usuario.
3. Reorientar `quick-entry` para pedir categoria/subcategoria antes que link a linea anual.

### `budget`
1. Rehacer el consumo de ejecucion ledger para agregar por categoria/subcategoria propia del ledger.
2. Mantener una ventana puente de lectura legacy para no romper cierres ni historicos durante la migracion.
3. Mantener `AnnualIncomeEntry` / `AnnualExpenseEntry` como capa de plan, no de clasificacion primaria de movimientos.

### `net_worth`
1. Mantener saldo y actividad contextual basados en cuenta y ledger.
2. No introducir dependencias nuevas sobre lineas de presupuesto.
3. Verificar que compras de inversion y pagos de deuda sigan interpretandose igual en patrimonio.

### `frontend data entry`
1. `AccountingMovementsView`
   - cambiar "categoria anual opcional" por categoria/subcategoria funcionales;
   - exponer linea anual solo como opcion secundaria cuando aporte valor.
2. `BudgetDashboardView`
   - pasar de "ledger por linea enlazada" a "ledger categorizado + posible alineacion a linea".
3. `DataInputView`
   - seguir siendo la pantalla del plan anual, no de movimientos diarios.

## Plan por fases
### Fase 0 - Documentacion y contrato
Aim:
1. Cerrar el contrato funcional y la estrategia de transicion antes de tocar codigo.

Cambios:
1. Documentar el target y las decisiones cerradas.
2. Link this roadmap from architecture and general operational roadmap.

Riesgos:
1. Dejar ambiguedades en precedencia o ownership del dato.

Validacion Docker:
1. No aplica validacion funcional obligatoria si solo hay cambios documentales.

Criterio de salida:
1. Otro agente puede implementar sin decidir taxonomia, precedencia ni boundaries.

### Fase 1 - Clasificacion funcional en ledger
Aim:
1. Introducir en `accounting` una clasificacion funcional propia del movimiento.

Cambios:
1. Extender el modelo/serializers del ledger para guardar:
- flow family (`income` / `expense`),
   - `category_key`,
   - `subcategory_key`.
2. Mantener temporalmente `annual_income_entry_id` / `annual_expense_entry_id`.
3. Add API reading of the new classification.

Riesgos:
1. Doble fuente temporal entre clasificacion nueva y links legacy.

Validacion Docker:
1. `docker compose exec backend ruff check .`
2. `docker compose exec backend ruff format --check .`
3. `docker compose exec backend mypy .`
4. `docker compose exec backend python manage.py test accounting --keepdb`

Criterio de salida:
1. El ledger puede persistir y devolver categoria/subcategoria sin romper los movimientos actuales.

### Fase 2 - `quick-entry` y UX de `accounting`
Aim:
1. Cambiar la captura operativa a un modelo `category-first`.

Cambios:
1. `POST /api/accounting/transactions/quick-entry/` acepta categoria/subcategoria como contrato principal.
2. `AccountingMovementsView` muestra:
   - cuenta de liquidez / cuenta impactada,
   - categoria,
   - subcategoria,
   - linea anual opcional.
3. Las cuentas `income` / `expense` dejan de ser protagonistas en la UX.

Riesgos:
1. Regresion en la alta diaria.
2. Microcopy confuso durante la convivencia.

Validacion Docker:
1. Backend: `python manage.py test accounting --keepdb`
2. Frontend:
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - `docker compose exec frontend npm run test:unit -- src/domains/accounting/__tests__/store.spec.ts src/views/__tests__/AccountingMovementsView.spec.ts`

Criterio de salida:
1. Un ingreso/gasto nuevo se registra con categoria/subcategoria sin necesitar `annual_*_entry_id`.

### Fase 3 - Consumo de `budget`
Aim:
1. Hacer que `budget` consuma ejecucion desde la clasificacion nueva del ledger.

Cambios:
1. Rehacer agregacion mensual y sugerencias para usar categoria/subcategoria del ledger.
2. Mantener fallback de lectura legacy cuando falte clasificacion nueva.
3. Ajustar `BudgetDashboardView` para etiquetar la fuente como:
   - `Ledger categorizado`,
   - `Fallback legacy`,
- `Pending clasificar`.

Riesgos:
1. Descuadres de ejecucion frente al plan.
2. Casos con varias lineas bajo la misma subcategoria.

Validacion Docker:
1. `docker compose exec backend python manage.py test budget --keepdb`
2. `docker compose exec backend python manage.py test accounting --keepdb`
3. `docker compose exec frontend npm run test:unit -- src/views/__tests__/BudgetDashboardView.spec.ts`

Criterio de salida:
1. The dashboard and the monthly closing stop depending on new writes `annual_*` to read ledger execution.

### Phase 4 - Backfill and data migration
Aim:
1. Migrar historico legacy a la nueva clasificacion funcional.

Cambios:
1. Backfill desde `annual_income_entry_id` / `annual_expense_entry_id` a categoria/subcategoria en ledger.
2. Mark cases without secure mapping as `pendiente clasificar`.
3. Mantener lectura legacy solo como red de seguridad temporal.

Riesgos:
1. Ambiguous or incomplete data.
2. Duplicidad funcional si conviven ambos criterios demasiado tiempo.

Validacion Docker:
1. `docker compose exec backend python manage.py test accounting --keepdb`
2. `docker compose exec backend python manage.py test budget --keepdb`
3. `docker compose exec backend python manage.py test net_worth --keepdb`

Criterio de salida:
1. La gran mayoria del historico ligado a presupuesto queda clasificada en el contrato nuevo.
2. Los casos ambiguos quedan trazables y no ocultos.

### Fase 5 - Retirada controlada de semantica legacy
Aim:
1. Quitar dependencia operativa de `income` / `expense` como cuentas visibles y de nuevas escrituras `annual_*`.

Cambios:
1. Ocultar en UX los tipos de cuenta legacy como piezas mentales del usuario.
2. Leave `annual_*_entry_id` as residual compatibility or final deprecation depending on the status of the backfill.
3. Limpiar contratos y docs para reflejar el modelo final.

Riesgos:
1. Regresiones en historico o vistas auxiliares.

Validacion Docker:
1. Validacion completa del stack Core afectado.
2. Replica equivalente en `frontend/` si hubo cambios UX compartidos.

Criterio de salida:
1. Nuevas operaciones no dependen de cuentas `income` / `expense` ni de escrituras `annual_*` para clasificar la ejecucion.

## Contratos y compatibilidad
### Cambios esperados en backend/API
1. `accounting`
   - exponer clasificacion funcional propia del movimiento;
   - aceptar categoria/subcategoria en `quick-entry`;
   - mantener compatibilidad temporal con `annual_income_entry_id` / `annual_expense_entry_id`.
2. `budget`
   - leer ejecucion por clasificacion ledger nueva;
   - caer a legacy solo cuando falte la nueva clasificacion.
3. `frontend`
   - consumir categoria/subcategoria como contrato primario de ejecucion.

### Payloads objetivo
1. Nuevas escrituras de movimientos `income` / `expense` deberan informar:
   - tipo de movimiento,
   - cuenta impactada,
   - importe,
   - categoria,
   - subcategoria,
   - linea anual opcional.
2. `transfer` no debera exigir categoria.
3. `debt_payment` solo categorizara la parte de coste/interes cuando aplique.

### Compatibilidad temporal
1. Los campos `annual_income_entry_id` y `annual_expense_entry_id` no se eliminan en la primera iteracion.
2. Se tratan como compatibilidad legacy y no como contrato funcional primario.

### Deprecaciones
1. `income` / `expense` as accounts visible to the end user go to a deprecated state in UX.
2. Las nuevas escrituras no deben depender de `annual_*_entry_id` una vez cerrada la Fase 2.

## UX/UI
1. Etiquetas a cambiar
   - `Categoria anual opcional` -> `Categoria`
   - nuevo selector dependiente `Subcategoria`
   - `Linea anual` o `Linea de presupuesto` solo como campo opcional secundario
2. Comportamiento esperado
   - `income`: pedir categoria/subcategoria de ingreso
   - `expense`: pedir categoria/subcategoria de gasto
   - `transfer`: sin categoria
   - `investment_purchase`: sin categoria de gasto salvo costes asociados
   - `debt_payment`: principal separado de interes; solo el interes se alinea como gasto cuando aplique
3. Defaults
   - recordar ultima categoria/subcategoria usada por tipo o cuenta cuando sea seguro
   - si existe linea anual opcional, filtrarla por ejercicio y taxonomia compatible
4. Statuss visibles
- `Pending clasificar`
   - `Ledger categorizado`
   - `Fallback legacy`
5. Replica Core
   - cualquier cambio UX compartido implementado en `core/frontend/` debera replicarse en `frontend/`.

## Migration of data
1. Fuente principal de backfill
   - `annual_income_entry_id`
   - `annual_expense_entry_id`
2. Estrategia
   - derivar `flow_family`, `category_key` y `subcategory_key` desde la linea anual enlazada
   - persistir la clasificacion nueva sin cambiar el saldo ni la logica patrimonial
3. Fallback temporal
   - si una fila aun no esta migrada, `budget` puede seguir leyendo el link legacy durante la ventana puente
4. Casos ambiguos
   - sin link `annual_*`
   - link inconsistente con el tipo de movimiento
- incomplete legacy data
5. Politica para ambiguos
   - no inventar categoria
- mark the case as `pendiente clasificar`
   - mantener trazabilidad para correccion posterior

## Riesgos y mitigaciones
1. Doble fuente de verdad
   - mitigacion: precedencia explicita `clasificacion nueva > legacy`, con ventana puente corta
2. Regresiones en `budget`
   - mitigacion: migrar primero backend de agregacion y luego UX
3. Acoplamiento excesivo entre plan y ejecucion
   - mitigacion: link a linea anual opcional y secundario
4. Drift entre Core frontend
   - mitigacion: replicar en `frontend/` cualquier patron compartido afectado
5. Casos historicos no clasificables
- mitigation: visible state `pendiente clasificar`, without hiding the problem

## Testing y validacion en Docker
1. Backend Core (`core/backend/`)
   - `docker compose exec backend ruff check .`
   - `docker compose exec backend ruff format --check .`
   - `docker compose exec backend mypy .`
   - `docker compose exec backend python manage.py test accounting --keepdb`
   - `docker compose exec backend python manage.py test budget --keepdb`
   - `docker compose exec backend python manage.py test net_worth --keepdb`
2. Frontend Core (`core/frontend/`)
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - `docker compose exec frontend npm run test:unit -- src/domains/accounting/__tests__/store.spec.ts src/views/__tests__/AccountingMovementsView.spec.ts src/views/__tests__/BudgetDashboardView.spec.ts src/views/__tests__/NetWorthView.spec.ts`
3. Si toca UI compartida en Core frontend
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - ejecutar los tests unitarios espejados que correspondan en `frontend/`

## Fuera de alcance
1. Reconciliacion bancaria.
2. Importadores o exportadores bancarios.
3. Multimoneda avanzada y conversion FX.
4. Refactors amplios de `net_worth`.
5. Refactor estructural amplio de `budget`.
6. Unificacion de `AnnualIncomeEntry` y `AnnualExpenseEntry`.
7. Eliminacion inmediata de check-ins legacy.

## Checklist de handoff para otro agente
1. Leer `core/docs/architecture/accounting-movements-architecture.md`.
2. Leer `core/docs/roadmap/accounting-movements-roadmap.md`.
3. Confirmar contratos reales antes de cambiar codigo en:
   - `core/backend/accounting/models.py`
   - `core/backend/accounting/serializers.py`
   - `core/backend/budget/services.py`
   - `core/frontend/src/views/AccountingMovementsView.vue`
   - `core/frontend/src/views/BudgetDashboardView.vue`
4. Implementar en PRs pequenas y reversibles.
5. Replicar en `frontend/` cualquier cambio UX compartido de `core/frontend/`.
6. Validar dentro de Docker segun el stack afectado.
7. No eliminar compatibilidad legacy hasta cerrar backfill y tests de presupuesto.

## Criterios de listo para otro agente
1. Existe un roadmap especifico, separado del roadmap general.
2. El roadmap contiene decisiones cerradas, no solo ideas.
3. Las fases tienen salida medible.
4. Los cambios de contrato estan descritos con precision suficiente para implementar.
5. La estrategia de migracion y compatibilidad esta definida.
6. El agente implementador no necesita decidir taxonomia, ownership del dato ni precedencia entre ledger y `budget`.
