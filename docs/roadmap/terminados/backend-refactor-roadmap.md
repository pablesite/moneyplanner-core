# Roadmap: backend refactor (Core) - continuity over real state

## Aim
Dejar el backend del Core mas facil de mantener, probar y extender, sin romper el comportamiento funcional actual ni reabrir trabajo ya estabilizado.

## Update 2026-03-18 — Reactive refactor with professional coverage

### Execution plan (active phases)

| Phase | Title | Spec | State |
|------|--------|------|--------|
| 1 | Test coverage baseline (≥80% por app) | `core/docs/tasks/backend-refactor/terminados/phase-1-test-coverage-baseline/backend.md` | ✅ |
| 2 | Particion `accounting/services.py` | `core/docs/tasks/backend-refactor/terminados/phase-2-accounting-services-partition/backend.md` | Completada |
| 3 | net_worth domain cleanup | `core/docs/tasks/backend-refactor/terminados/phase-3-net-worth-domain-cleanup/backend.md` | Completada |
| 4 | Boundary enforcement cross-domain | `core/docs/tasks/backend-refactor/terminados/phase-4-boundary-enforcement/backend.md` | Completada |
| 5 | DX docs y guia de contribucion | `core/docs/tasks/backend-refactor/terminados/phase-5-dx-docs/backend.md` | Completada |

### Boundaries estabilizados (Phase 4)

#### Tabla de responsabilidades definitiva

| Dominio | Responsabilidad unica | No debe hacer |
|---------|------------------------|---------------|
| `accounting` | Registrar movimientos reales del ledger, balances de cuentas y clasificacion funcional de entries. | No modificar entradas de `budget` directamente ni operar `assets`/`liabilities` fuera de contratos publicos. |
| `budget` | Gestionar plan anual y seguimiento mensual (incluyendo convivencia ledger/fallback). | No escribir directamente en el ledger contable ni recalcular balances de cuentas. |
| `net_worth` | Calcular posicion patrimonial y sincronizar compromisos presupuestarios ligados a activos/pasivos. | No escribir en el ledger directamente ni duplicar reglas de clasificacion anual. |
| `memberships` | Manage ownership and synchronization of ownership-links per user. | Do not persist partial side effects outside of a transactional block in sync cross-domain. |

#### Flujos atomicos garantizados

1. `accounting.services_quick_entry.create_quick_transaction` (ya atomico): creacion de transaccion + entries + links anuales en una sola transaccion.
2. `net_worth.services_assets_budget.sync_generated_budget_commitments_for_asset`: borrado/recreacion de compromisos con rollback total ante fallo.
3. `net_worth.services_liabilities_budget.sync_generated_budget_commitments_for_liability`: sync de compromisos de pasivos con rollback total.
4. `memberships.services.sync_ownership_link`: actualizacion de ownership-link y sincronizacion de commitments en un unico bloque atomico.
5. `net_worth.services_snapshots.import_snapshots_bulk_for_user` (ya atomico): importacion bulk todo-o-nada.

#### Side effects cross-domain documentados

1. `accounting -> budget`: el monthly summary consume clasificacion funcional y links anuales de entries del ledger.
2. `net_worth -> budget`: assets/liabilities generan y sincronizan compromisos presupuestarios de sistema.
3. `memberships -> net_worth/budget`: `ownership-links/sync` actualiza ownership efectivo y dispara resync de compromisos dependientes.
4. `accounting -> net_worth`: posiciones `tracking_mode=accounting` leen balance efectivo desde cuentas contables vinculadas.

### Hotspots reales (2026-03-18)

| Archive | Lines | Risk | Action |
|---------|--------|--------|--------|
| `accounting/services_*.py` + `services.py` facade | 920 aprox. (5 m�dulos + facade) | Medio | Fase 2 completada: partici�n aplicada y facade de compatibilidad mantenida |
| `net_worth/services_assets_core.py` + `services_assets_budget.py` | 1082 aprox. | Medio | Fase 3 completada: particion por subdominio aplicada |
| `net_worth/services_liabilities_core.py` + `services_liabilities_budget.py` | 935 aprox. | Medio | Fase 3 completada: particion por subdominio aplicada |
| `net_worth/services.py` (facade) | 63 | Bajo | Fase 3 completada: facade residual y minima |
| `net_worth/tests/test_*.py` (7 ficheros) | 4,509 | Medio | Fase 1 completada: suite dividida por dominio |
| `budget/test_services.py` | 43 | High | Phase 1: Expand to ≥300 lines |
| `core/tests.py` | 715 | Medium | Phase 1: add unit tests portable_data/market_data |

### Definition of professional coverage
- ≥80% statement coverage por app
- 100% de endpoints con: happy path + auth failure + validation error
- Integration tests para todos los flujos cross-domain
- Unit tests para todas las funciones de negocio en services

### Actual execution of Phase 1 (2026-03-18)
1. `backend/net_worth/tests/test_net_worth.py` was replaced by 7 files (`test_assets.py`, `test_liabilities.py`, `test_snapshots.py`, `test_summaries.py`, `test_liquidity.py`, `test_timelines.py`, `test_integration.py`).
2. `backend/budget/tests/test_services.py` expanded from 43 to 426 lines with ledger/fallback coverage, edge-cases and monthly summaries.
3. Coverage of `accounting`, `accounts`, `core` and `memberships` was reinforced in service/API tests and error cases.
4. Validation executed in Docker:
   - `python manage.py test accounting accounts budget memberships net_worth core` (310 tests, OK)
   - `ruff check .` (OK)
   - `ruff format --check .` (OK)
   - `mypy .` (OK)
5. Note: The per-app percentage metric (coverage.py / pytest-cov) is still pending because `pytest` is not installed in the current backend container.

---

## Actual status (2026-03-16)
1. El backend Core ya no es un stack pre-`accounting`: hoy incluye `accounts`, `budget`, `core`, `memberships`, `net_worth`, `accounting` y `config`.
2. 2026-02-27: `budget/views.py` se simplifico para reducir duplicacion en parseo de query params y logica de `confirmed_at`.
3. 2026-02-27: helpers de `budget` extraidos a:
   - `backend/budget/query_params.py`
   - `backend/budget/checkins.py`
4. 2026-02-27: `AnnualEntrySummaryMixin` consolidado en `backend/budget/views.py` para `totals` y `monthly-summary`.
5. 2026-02-27: deuda de tipado resuelta en `budget`; `mypy budget` quedo en verde con ajustes acotados en serializers y services.
6. 2026-02-27: deuda de tipado resuelta en `backend/net_worth/services_liabilities.py`; `mypy .` del backend Core vuelve a verde.
7. 2026-02-27: `budget/tests.py` migrado a `backend/budget/tests/` por dominio:
   - `test_api_entries.py`
   - `test_api_checkins.py`
   - `test_serializers.py`
   - `test_services.py`
8. 2026-02-27: `UserScopedQuerySetMixin` consolidado en `backend/config/view_mixins.py` y reutilizado por `memberships` y `net_worth`.
9. 2026-02-27: `accounts.UserSettingsAPIView.put` alineado a update sobre instancia, con test API de regresion.
10. 2026-02-27: `backend/core/tests.py` gano cobertura API minima para `fx-rates` e `inflation`; hoy tambien cubre `market-data` y `portable-data`.
11. 2026-02-27: refactor interno en `backend/net_worth/services_liabilities.py` para bajar complejidad en generacion de perfiles de gasto, sin cambios funcionales.
12. 2026-02-27: `backend/memberships/tests.py` migrado a paquete `backend/memberships/tests/` con `test_api.py` y `test_services.py`.
13. 2026-02-27: `backend/net_worth/tests.py` migrado a `backend/net_worth/tests/test_net_worth.py`.
14. 2026-02-27: `accounts/link-token` paso a usar excepcion DRF (`feature_disabled`) con handler canonico.
15. 2026-02-27: la orquestacion de `snapshots/import-bulk` salio de `backend/net_worth/views.py` hacia `backend/net_worth/services_snapshot_api.py`.
16. `net_worth` ya no depende de un unico `services.py` monolitico: hoy existe una separacion parcial en:
   - `services_assets.py`
   - `services_liabilities.py`
   - `services_liquidity.py`
   - `services_snapshots.py`
   - `services_snapshot_api.py`
   - `services_summaries.py`
   - `services_timelines.py`
17. `backend/net_worth/services.py` sigue existiendo como facade de compatibilidad interna; esa compatibilidad temporal es una decision explicita y tambien una deuda a vigilar.
18. El bug sospechado historicamente en `LiquidityMonthlyCheckinViewSet.perform_update()` ya no aplica: la view actual hace `serializer.save()` sin sync erroneo hacia liabilities.
19. `accounting` ya es parte activa del backend Core y hoy expone CRUD y agregados para cuentas, transacciones y entries, ademas de `quick-entry`, `monthly-summary`, `budget-suggestions` y `accounts/balances`.

## Principios de trabajo
1. PRs pequenas, reversibles y con alcance claro.
2. Sin cambios de comportamiento no intencionales.
3. Primero contratos y regresiones criticas; luego refactor interno.
4. Cada fase deja el repo ejecutable.
5. Validacion dentro de Docker, sin `down -v`.
6. No duplicar logica entre `accounting`, `budget`, `net_worth` y `memberships`.
7. Este roadmap es de mantenibilidad, no un changelog ni un roadmap funcional alternativo de `accounting`.

## Alcance
1. `accounts`
2. `budget`
3. `core`
4. `memberships`
5. `net_worth`
6. `accounting`
7. `config` solo para wiring, auth, errores, mixins y settings transversales

## Fuera de alcance
1. Cambios grandes de producto o UX.
2. Reapertura de fases funcionales ya cerradas en `accounting`.
3. Integraciones externas complejas sin evidencia de deuda concreta.
4. Reescritura masiva de migraciones historicas.

## Referencias cruzadas obligatorias
1. El roadmap funcional cerrado de `accounting` vive en `terminados/accounting-movements-roadmap.md`.
2. The separation between accounting account, category/subcategory and annual budget line lives in `terminados/accounting-category-budget-separation-roadmap.md` (completed).
3. Este documento no reemplaza esos roadmaps: define la continuidad del refactor de mantenibilidad del backend completo.
4. Cuando cambien los boundaries entre `accounting`, `budget` y `net_worth`, este documento debe actualizarse en paralelo para mantener trazabilidad.

## Fase 0 - Baseline y mapa del backend actual
Objective: leave a realistic photo of today's Core backend and its current hotspots.

### 0.1 Inventario por app

| App | Superficie principal | Tests actuales | Lectura de riesgo |
| --- | --- | --- | --- |
| `accounts` | auth, mode, ops metrics, link-token, settings | Si | Medio-Bajo |
| `budget` | annual entries, monthly summaries, check-ins, convivencia ledger/fallback | Si | Medio |
| `core` | fx, inflation, market-data status, portable-data | Si | Medio |
| `memberships` | family members, ownerships, ownership-links | Si (`test_api.py`, `test_services.py`) | Medio |
| `net_worth` | assets, liabilities, liquidity-checkins, snapshots, summaries, timelines | Si (`test_assets.py`, `test_liabilities.py`, `test_snapshots.py`, `test_summaries.py`, `test_liquidity.py`, `test_timelines.py`, `test_integration.py`) | Alto |
| `accounting` | ledger accounts, transactions, entries, quick-entry, summaries y suggestions | Si (`test_accounting.py`) | Medio-Alto |
| `config` | exception handler, urls, mixins transversales | Cobertura indirecta | Medio |

### 0.2 Superficie publica vigente

#### `accounts`
1. JWT login/refresh.
2. `mode/`.
3. `ops/metrics/`.
4. `link-token/`.
5. `settings/`.

#### `budget`
1. `annual-income` y `annual-expense` con CRUD, `totals` y `monthly-summary`.
2. `annual-income-checkins` y `annual-expense-checkins`.
3. Resumenes mensuales ya convivientes con ledger y fallback legacy.

#### `core`
1. `fx-rates`.
2. `inflation`.
3. `market-data/status`.
4. `portable-data/meta`.
5. `portable-data/import`.

#### `memberships`
1. `family-members` con `ensure-primary`.
2. `ownerships`.
3. `ownership-links` con `list` y `sync`.

#### `net_worth`
1. `assets`.
2. `liabilities`.
3. `liquidity-checkins`.
4. `snapshots` con `from-current` e `import-bulk`.
5. `summary/`.
6. `liquidity/monthly-summary/`.
7. endpoints de timeline.

#### `accounting`
1. `accounts`.
2. `transactions`.
3. `entries`.
4. `transactions/monthly-summary/`.
5. `transactions/budget-suggestions/`.
6. `transactions/quick-entry/`.
7. `accounts/balances/`.

### 0.3 Riesgos y hotspots reales

#### Riesgo alto
1. `backend/net_worth/services_liabilities.py` remains the strongest hotspot in the module due to volume, side effects and financial rules.
2. The `net_worth/tests` split is already applied; The risk becomes maintaining clear domain boundaries between the 7 files to avoid returning to the monolith.
3. Los boundaries entre `accounting`, `budget` y `net_worth` siguen siendo una deuda activa:
   - ejecucion ledger
   - plan anual
   - cobertura parcial/fallback
   - posiciones `tracking_mode=accounting`
4. `backend/net_worth/services.py` como facade de compatibilidad reduce riesgo de ruptura hoy, pero mantiene acoplamientos temporales que conviene seguir desarmando con cuidado.

#### Riesgo medio-alto
1. `backend/accounting/services.py` crecio mucho y ya concentra logica de balances, quick-entry, summaries y suggestions.
2. `accounting` increasingly crosses with taxonomies and contracts from `budget`, so the risk is no longer just internal to the module.

#### Riesgo medio
1. `budget` ya simplifico views, pero sigue teniendo deuda de convivencia ledger/fallback y contratos que dependen de boundaries aun en evolucion.
2. `core` grew with `market_data` and `portable_data`; It is no longer convenient to treat it as an almost trivial module.
3. `memberships` ya no es el gran hueco de cobertura, pero sigue siendo un punto sensible por side effects sobre `budget` y `net_worth`.
4. `config` sigue siendo transversal: cualquier drift en `custom_exception_handler` o mixins pega en todos los modulos.

### 0.4 Checklist actualizado por app

#### `accounting` (prioridad ALTA)
1. [ ] Documentar que contratos ya quedaron estabilizados y cuales siguen en convivencia.
2. [ ] Revisar si `services.py` necesita particion por subdominios sin romper contrato interno.
3. [ ] Vigilar duplicacion de clasificacion funcional con `budget`.
4. [ ] Asegurar regresiones de `quick-entry`, `monthly-summary`, `budget-suggestions` y `accounts/balances`.

#### `net_worth` (prioridad ALTA)
1. [ ] Seguir desarmando hotspots reales de liabilities, snapshots y compatibilidad interna.
2. [ ] Mantener `views.py` delgado y sin recaer en logica de negocio.
3. [ ] Revisar transacciones y side effects hacia `budget` y `accounting`.
4. [x] Reorganization of `net_worth` applied without loss of discovery (suite split into 7 files).

#### `budget` (prioridad MEDIA-ALTA)
1. [ ] Congelar boundaries de convivencia ledger/fallback.
2. [ ] Reforzar regresiones sobre summaries mensuales y check-ins con `confirmed_at`.
3. [ ] Evitar drift entre taxonomia anual y clasificacion funcional ledger.

#### `core` (prioridad MEDIA)
1. [ ] Mantener contratos estables para `fx`, `inflation`, `market-data` y `portable-data`.
2. [ ] Reorganize tests only if the growth of the module already justifies it.

#### `memberships` (prioridad MEDIA)
1. [ ] Mantener coberturas de `ensure-primary`, ownerships y ownership-links.
2. [ ] Revisar si `services.py` necesita fragmentacion; hoy no es prioridad alta.
3. [ ] Vigilar side effects de sync sobre `budget` y `net_worth`.

#### `accounts` y `config` (prioridad MEDIA-BAJA)
1. [ ] Sostener el contrato canonico de errores y auth.
2. [ ] Evitar volver a respuestas manuales con shape ad hoc.

## Fase 1 - Baseline y contratos vigentes
Objective: document precisely which backend contracts have been stabilized and which remain fragile or incomplete.

### Entregables
1. Inventario de endpoints activos por app, actualizado al backend real.
2. Lista de contratos ya cubiertos por tests de regresion.
3. Lista explicita de contratos fragiles, temporales o todavia incompletos.

### Cobertura a reconocer como ya existente
1. `accounts`: auth, `link-token`, `settings`.
2. `core`: `fx-rates`, `inflation`, `market-data/status`, `portable-data/*`.
3. `memberships`: `ensure-primary`, ownerships y ownership-links.
4. `budget`: entries, summaries mensuales y check-ins.
5. `net_worth`: snapshots, summaries, liquidity y timeline.
6. `accounting`: CRUD base, `quick-entry`, `monthly-summary`, `budget-suggestions`, `accounts/balances`.

### Contratos a marcar como fragiles o en convivencia
1. La frontera exacta entre clasificacion funcional ledger y taxonomia anual.
2. La precedencia entre ledger y fallback legacy en `budget`.
3. La relacion entre posiciones `tracking_mode=accounting` y lectura contable en `net_worth`.
4. La compatibilidad interna que hoy preserva `net_worth.services` como facade.

### Criterio de salida
1. El documento deja de prometer trabajo ya hecho.
2. Queda claro que contratos estan estables y cuales siguen en transicion controlada.

## Fase 2 - Boundaries entre accounting, budget y net_worth
Objective: avoid duplication, functional drift and mix execution, plan and heritage layers.

### Prioridades
1. Definir con claridad que pertenece a `accounting` como capa de ejecucion.
2. Definir que sigue perteneciendo a `budget` como plan anual.
3. Definir como `net_worth` consume actividad, balances y enlaces contables sin duplicar reglas.
4. Mantener alineado este roadmap con:
   - `terminados/accounting-movements-roadmap.md`
   - `accounting-category-budget-separation-roadmap.md`

### Trabajo esperado
1. Auditar duplicacion de reglas entre serializers/services de `accounting` y services de `budget`.
2. Congelar criterios de cobertura ledger, fallback y cobertura parcial.
3. Revisar los side effects `accounting <-> budget` y `net_worth <-> accounting`.
4. Documentar cualquier decision de precedencia antes de seguir fragmentando codigo.

### Criterio de salida
1. Los tres dominios comparten boundaries explicitados y no solo implicitos en codigo.
2. Las siguientes fases de refactor ya no dependen de adivinar donde vive cada regla.

## Fase 3 - Hotspots de mantenibilidad restantes
Objective: attack the points of the backend that most slow down small and safe changes.

### Prioridad alta
1. `backend/accounting/services.py` como siguiente candidato claro a particion interna.
2. `backend/net_worth/services_liabilities.py` as the main hotspot of the `net_worth` module.
3. `backend/net_worth/services.py` como facade temporal a adelgazar gradualmente, sin romper imports internos de golpe.

### Prioridad media
1. Evaluate reorganization of `backend/core/tests.py` if the module continues to grow in `portable_data` and `market_data`.
2. Monitor growth of `backend/net_worth/tests/test_*.py` to maintain separation by domain and avoid re-monolithization.
3. Revisar `backend/memberships/services.py`; hoy la deuda existe, pero no justifica prioridad alta salvo que aparezcan nuevos side effects o duplicacion real.

### Criterio de salida
1. Los hotspots principales quedan identificados por evidencia, no por percepcion historica.
2. El roadmap prioriza los monolitos reales de hoy, no los de febrero.

## Fase 4 - Tests, atomicidad y regresion cruzada
Objective: increase change security in flows where there is already integration between domains.

### Escenarios prioritarios
1. `accounting <-> budget`:
   - `quick-entry`
   - `monthly-summary`
   - `budget-suggestions`
   - consumo de taxonomia anual
2. `accounting <-> net_worth`:
   - posiciones `tracking_mode=accounting`
   - cuentas ligadas
   - actividad contextual y balances
3. `memberships <-> net_worth`:
   - ownership-links
   - side effects sobre compromisos o sync relacionado
4. `budget`:
   - summaries mensuales con cobertura ledger y fallback legacy
   - check-ins y `confirmed_at`
5. `net_worth`:
   - snapshots `from-current` e `import-bulk`
   - summaries y timelines
6. `core`:
   - auth/permisos y shape canonico de `fx-rates`, `inflation`, `market-data/status` y `portable-data/*`

### Trabajo tecnico
1. Revisar fronteras `transaction.atomic` donde hay side effects cruzados.
2. Asegurar que las suites actuales cubren integracion real, no solo unit tests aislados.
3. Medir performance solo donde haya evidencia de N+1 o queries excesivas.

### Criterio de salida
1. Los cruces entre dominios quedan protegidos por regresiones especificas.
2. Las decisiones de atomicidad y side effects quedan explicitadas en PRs o docs asociadas.

## Fase 5 - DX y contribucion
Objective: make it easier for someone else to continue the refactor without tribal context.

### Entregables
1. Checklist de PR de refactor reutilizable.
2. Guia corta del patron backend vigente:
   - views finas
   - serializers como adaptadores y validacion de shape
   - services como reglas y orquestacion
   - tests por contrato y por integracion
3. Backlog pequeno de tareas publicables por hotspot real.

### Criterio de salida
1. El roadmap se puede usar como handoff operativo.
2. Hay tareas pequenas, trazables y seguras para siguientes PRs.

### Backlog de contribucion (post-refactor)
1. Exponer `GET /api/accounting/accounts/{id}/balance-history/` con filtros por rango.
2. Anadir paginacion y orden explicito a `GET /api/accounting/transactions/`.
3. Anadir filtro por fecha de referencia en `GET /api/net_worth/assets/`.
4. Crear tests de rendimiento para `build_monthly_accounting_summary` con volumen alto de entries.
5. Medir y documentar baseline de latencia para endpoints criticos de `accounting`, `budget` y `net_worth`.
6. Revisar oportunidades de particion adicional en hotspots que superen umbral de complejidad acordado.

### Formal closure of the structural refactoring
Closing date: 2026-03-18
Version Core de referencia: 0.23.1

Summary by phase:
1. Fase 1: baseline de cobertura y reorganizacion de suites por dominio.
2. Fase 2: particion de `accounting/services.py` con facade de compatibilidad.
3. Fase 3: limpieza de dominio `net_worth` y separacion por submodulos.
4. Fase 4: boundaries cross-domain estabilizados y atomicidad reforzada.
5. Fase 5: documentacion DX (checklist PR, patrones backend y backlog publicable).

Final state:
1. Backend structural refactor completed.
2. Continuidad definida mediante backlog acotado y documentacion de handoff.
## Secuencia de ejecucion recomendada
1. Actualizar y mantener el baseline documental del backend real.
2. Endurecer boundaries `accounting` / `budget` / `net_worth`.
3. Atacar hotspots `accounting/services.py` y `net_worth/services_liabilities.py`.
4. Reorganizar suites grandes de tests solo si ya hay evidencia de que bloquean cambios.
5. Revisar atomicidad y rendimiento con evidencia.
6. Cerrar DX, docs y backlog de contribucion.

## Matriz de validacion por PR (Docker)
Ejecutar dentro de contenedores. No usar `docker compose down -v`.

### Diagnostico estandar
1. `docker compose ps`
2. `docker compose logs --tail 100 <service>`
3. Opcional: `docker compose ps -a`

### Calidad minima Core backend
1. `cd core`
2. `docker compose exec backend ruff check .`
3. `docker compose exec backend ruff format --check .`
4. `docker compose exec backend mypy .`

### Tests minimos Core backend
1. `cd core`
2. `docker compose exec backend python manage.py test accounting`
3. `docker compose exec backend python manage.py test accounts`
4. `docker compose exec backend python manage.py test budget`
5. `docker compose exec backend python manage.py test memberships`
6. `docker compose exec backend python manage.py test net_worth`
7. `docker compose exec backend python manage.py test core`

### Nota de integracion ledger
1. Si un PR toca integracion ledger o boundaries entre dominios, correr al menos:
   - `docker compose exec backend python manage.py test accounting`
   - `docker compose exec backend python manage.py test budget`
   - `docker compose exec backend python manage.py test net_worth`

## Checklist de PR de refactor
1. [ ] Hay test de regresion para el comportamiento que se protege o mueve.
2. [ ] No cambia el contrato API sin documentarlo.
3. [ ] La logica de negocio se mueve hacia services, no hacia views.
4. [ ] The diff prevents out-of-scope cosmetic refactors.
5. [ ] Validado con calidad y tests dentro de Docker.
6. [ ] Docs updated if contract, boundary or operational flow changes.
7. [ ] Commit con Conventional Commits.

## Riesgos a vigilar durante toda la ejecucion
1. Reintroducir duplicacion entre `accounting`, `budget` y `net_worth`.
2. Cambiar shapes de error accidentalmente al tocar views o serializers.
3. Mantener demasiado tiempo la facade `net_worth.services` sin plan de salida.
4. Side effects cruzados sin transaccion clara.
5. PRs demasiado grandes que mezclen contrato, refactor y cambio funcional.

## Criterio de exito
1. El roadmap refleja el backend Core real del 2026-03-16.
2. El refactor se centra en deuda viva y no en trabajo ya cerrado.
3. Los boundaries entre ejecucion, plan y patrimonio quedan mas claros.
4. Los hotspots reales quedan protegidos con tests y decisiones trazables.
5. Otra persona puede continuar el trabajo sin depender de contexto oral.




