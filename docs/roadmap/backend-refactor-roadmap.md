# Roadmap: backend refactor (Core) - continuidad sobre el estado real

## Objetivo
Dejar el backend del Core mas facil de mantener, probar y extender, sin romper el comportamiento funcional actual ni reabrir trabajo ya estabilizado.

## Actualización 2026-03-18 — Refactor reactivo con cobertura profesional

### Plan de ejecución (fases activas)

| Fase | Título | Spec | Estado |
|------|--------|------|--------|
| 1 | Test coverage baseline (≥80% por app) | `core/docs/tasks/backend-refactor/terminados/phase-1-test-coverage-baseline/backend.md` | ✅ |
| 2 | Particion `accounting/services.py` | `core/docs/tasks/backend-refactor/terminados/phase-2-accounting-services-partition/backend.md` | Completada |
| 3 | net_worth domain cleanup | `core/docs/tasks/backend-refactor/terminados/phase-3-net-worth-domain-cleanup/backend.md` | Completada |
| 4 | Boundary enforcement cross-domain | `core/docs/tasks/backend-refactor/phase-4-boundary-enforcement/backend.md` | ⚪ |
| 5 | DX docs y guía de contribución | `core/docs/tasks/backend-refactor/phase-5-dx-docs/backend.md` | ⚪ |

### Hotspots reales (2026-03-18)

| Archivo | Líneas | Riesgo | Acción |
|---------|--------|--------|--------|
| `accounting/services_*.py` + `services.py` facade | 920 aprox. (5 m�dulos + facade) | Medio | Fase 2 completada: partici�n aplicada y facade de compatibilidad mantenida |
| `net_worth/services_assets_core.py` + `services_assets_budget.py` | 1082 aprox. | Medio | Fase 3 completada: particion por subdominio aplicada |
| `net_worth/services_liabilities_core.py` + `services_liabilities_budget.py` | 935 aprox. | Medio | Fase 3 completada: particion por subdominio aplicada |
| `net_worth/services.py` (facade) | 63 | Bajo | Fase 3 completada: facade residual y minima |
| `net_worth/tests/test_*.py` (7 ficheros) | 4,509 | Medio | Fase 1 completada: suite dividida por dominio |
| `budget/test_services.py` | 43 | Alto | Fase 1: expandir a ≥300 líneas |
| `core/tests.py` | 715 | Medio | Fase 1: añadir unit tests portable_data/market_data |

### Definición de cobertura profesional
- ≥80% statement coverage por app
- 100% de endpoints con: happy path + auth failure + validation error
- Integration tests para todos los flujos cross-domain
- Unit tests para todas las funciones de negocio en services

### Ejecución real de Fase 1 (2026-03-18)
1. `backend/net_worth/tests/test_net_worth.py` se reemplazó por 7 ficheros (`test_assets.py`, `test_liabilities.py`, `test_snapshots.py`, `test_summaries.py`, `test_liquidity.py`, `test_timelines.py`, `test_integration.py`).
2. `backend/budget/tests/test_services.py` se expandió de 43 a 426 líneas con cobertura ledger/fallback, edge-cases y resúmenes mensuales.
3. Se reforzó cobertura de `accounting`, `accounts`, `core` y `memberships` en tests de servicios/API y casos de error.
4. Validación ejecutada en Docker:
   - `python manage.py test accounting accounts budget memberships net_worth core` (310 tests, OK)
   - `ruff check .` (OK)
   - `ruff format --check .` (OK)
   - `mypy .` (OK)
5. Nota: la métrica porcentual por app (coverage.py / pytest-cov) sigue pendiente porque `pytest` no está instalado en el contenedor backend actual.

---

## Estado real (2026-03-16)
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
2. La separacion entre cuenta contable, categoria/subcategoria y linea anual de presupuesto vive en `terminados/accounting-category-budget-separation-roadmap.md` (completado).
3. Este documento no reemplaza esos roadmaps: define la continuidad del refactor de mantenibilidad del backend completo.
4. Cuando cambien los boundaries entre `accounting`, `budget` y `net_worth`, este documento debe actualizarse en paralelo para mantener trazabilidad.

## Fase 0 - Baseline y mapa del backend actual
Objetivo: dejar una foto realista del backend Core de hoy y de sus hotspots vigentes.

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
1. `backend/net_worth/services_liabilities.py` sigue siendo el hotspot mas fuerte del modulo por volumen, side effects y reglas financieras.
2. El split de `net_worth/tests` ya está aplicado; el riesgo pasa a ser mantener límites de dominio claros entre los 7 ficheros para evitar volver al monolito.
3. Los boundaries entre `accounting`, `budget` y `net_worth` siguen siendo una deuda activa:
   - ejecucion ledger
   - plan anual
   - cobertura parcial/fallback
   - posiciones `tracking_mode=accounting`
4. `backend/net_worth/services.py` como facade de compatibilidad reduce riesgo de ruptura hoy, pero mantiene acoplamientos temporales que conviene seguir desarmando con cuidado.

#### Riesgo medio-alto
1. `backend/accounting/services.py` crecio mucho y ya concentra logica de balances, quick-entry, summaries y suggestions.
2. `accounting` cruza cada vez mas con taxonomias y contratos de `budget`, por lo que el riesgo ya no es solo interno del modulo.

#### Riesgo medio
1. `budget` ya simplifico views, pero sigue teniendo deuda de convivencia ledger/fallback y contratos que dependen de boundaries aun en evolucion.
2. `core` crecio con `market_data` y `portable_data`; ya no conviene tratarlo como modulo casi trivial.
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
4. [x] Reorganización de `net_worth` aplicada sin pérdida de discovery (suite partida en 7 ficheros).

#### `budget` (prioridad MEDIA-ALTA)
1. [ ] Congelar boundaries de convivencia ledger/fallback.
2. [ ] Reforzar regresiones sobre summaries mensuales y check-ins con `confirmed_at`.
3. [ ] Evitar drift entre taxonomia anual y clasificacion funcional ledger.

#### `core` (prioridad MEDIA)
1. [ ] Mantener contratos estables para `fx`, `inflation`, `market-data` y `portable-data`.
2. [ ] Reorganizar tests solo si el crecimiento del modulo ya lo justifica.

#### `memberships` (prioridad MEDIA)
1. [ ] Mantener coberturas de `ensure-primary`, ownerships y ownership-links.
2. [ ] Revisar si `services.py` necesita fragmentacion; hoy no es prioridad alta.
3. [ ] Vigilar side effects de sync sobre `budget` y `net_worth`.

#### `accounts` y `config` (prioridad MEDIA-BAJA)
1. [ ] Sostener el contrato canonico de errores y auth.
2. [ ] Evitar volver a respuestas manuales con shape ad hoc.

## Fase 1 - Baseline y contratos vigentes
Objetivo: documentar con precision que contratos del backend ya quedaron estabilizados y cuales siguen fragiles o incompletos.

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
Objetivo: evitar duplicacion, drift funcional y mezclar capas de ejecucion, plan y patrimonio.

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
Objetivo: atacar los puntos del backend que mas frenan cambios pequenos y seguros.

### Prioridad alta
1. `backend/accounting/services.py` como siguiente candidato claro a particion interna.
2. `backend/net_worth/services_liabilities.py` como hotspot principal del modulo `net_worth`.
3. `backend/net_worth/services.py` como facade temporal a adelgazar gradualmente, sin romper imports internos de golpe.

### Prioridad media
1. Evaluar reorganizacion de `backend/core/tests.py` si el modulo sigue creciendo en `portable_data` y `market_data`.
2. Vigilar crecimiento de `backend/net_worth/tests/test_*.py` para mantener separación por dominio y evitar re-monolitización.
3. Revisar `backend/memberships/services.py`; hoy la deuda existe, pero no justifica prioridad alta salvo que aparezcan nuevos side effects o duplicacion real.

### Criterio de salida
1. Los hotspots principales quedan identificados por evidencia, no por percepcion historica.
2. El roadmap prioriza los monolitos reales de hoy, no los de febrero.

## Fase 4 - Tests, atomicidad y regresion cruzada
Objetivo: aumentar seguridad de cambio en los flujos donde ya hay integracion entre dominios.

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
Objetivo: facilitar que otra persona continue el refactor sin contexto tribal.

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
4. [ ] El diff evita refactors cosméticos fuera de alcance.
5. [ ] Validado con calidad y tests dentro de Docker.
6. [ ] Docs actualizadas si cambia contrato, boundary o flujo operativo.
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



