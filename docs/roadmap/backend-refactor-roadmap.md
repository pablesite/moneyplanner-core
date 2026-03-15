# Roadmap: refactor profundo del backend (Core) - plan ejecutable

## Objetivo
Dejar el backend del Core mas facil de mantener, probar y extender, sin romper el comportamiento funcional actual.

## Estado de este documento
1. Este documento queda resuelto como plan operativo completo (no solo idea general).
2. Incluye Fase 0 con baseline real del repo (revision hecha el 2026-02-26).
3. Las fases 1-5 quedan desglosadas en pasos de implementacion, entregables y criterios de salida.
4. El trabajo debe ejecutarse en PRs pequenos, con validacion en Docker en cada fase.

## Avance de ejecucion
1. 2026-02-27: `budget/views.py` refactorizado para reducir duplicacion en:
   - parseo de query params enteros (`year`, `month`, ids),
   - logica de `confirmed_at` en checkins de income/expense.
2. 2026-02-27: helpers extraidos a modulos dedicados:
   - `backend/budget/query_params.py`
   - `backend/budget/checkins.py`
3. 2026-02-27: `AnnualEntrySummaryMixin` agregado en `backend/budget/views.py`
   para consolidar `totals` y `monthly-summary` de income/expense.
4. 2026-02-27: deuda de tipado resuelta en `budget`:
   - `mypy budget` en verde tras ajustes minimos en `backend/budget/serializers.py`
     y `backend/budget/services.py`.
5. 2026-02-27: deuda de tipado resuelta en `net_worth/services_liabilities.py`;
   `mypy .` del backend Core vuelve a verde.
6. 2026-02-27: `budget/tests.py` migrado a paquete `backend/budget/tests/`
   separado por dominio (`test_api_entries.py`, `test_api_checkins.py`,
   `test_serializers.py`, `test_services.py`) sin cambios funcionales.
7. 2026-02-27: `UserScopedQuerySetMixin` consolidado en
   `backend/config/view_mixins.py` y reutilizado por `memberships` y `net_worth`.
8. 2026-02-27: `accounts.UserSettingsAPIView.put` alineado a update con
   serializer de instancia, con test API de regresion para mantener el mismo
   registro `UserSettings` en el `PUT`.
9. 2026-02-27: tests API minimos agregados en `backend/core/tests.py` para
   `fx-rates` e `inflation` (permisos, create/list y shape canonico de errores).
10. 2026-02-27: refactor interno en `backend/net_worth/services_liabilities.py`
    para reducir complejidad en `get_generated_liability_expense_profile`
    (helpers privados + mapas de subcategoria reutilizables), sin cambios funcionales.
11. 2026-02-27: `backend/memberships/tests.py` migrado a paquete
    `backend/memberships/tests/` separado en `test_api.py` y `test_services.py`
    sin cambios funcionales.
12. 2026-02-27: `backend/net_worth/tests.py` migrado a paquete
    `backend/net_worth/tests/` (`test_net_worth.py`) manteniendo cobertura y
    discovery de Django sin cambios funcionales.
13. 2026-02-27: `accounts/link-token` deja de usar respuesta manual y pasa por
    excepcion DRF (`feature_disabled`) con handler canonico en
    `backend/config/exceptions.py`.
14. 2026-02-27: orquestacion de `snapshots/import-bulk` extraida desde
    `backend/net_worth/views.py` a `backend/net_worth/services_snapshot_api.py`
    para adelgazar views sin cambios de contrato API.
2. Se mantuvo el contrato API y se validaron tests del modulo `budget`.

## Principios de trabajo (obligatorios)
1. Refactor por fases pequenas.
2. Sin cambios de comportamiento no intencionales.
3. Primero tests/contratos criticos, luego refactor interno.
4. Cada fase deja el repo ejecutable.
5. Validacion dentro de Docker (sin `down -v`).
6. Cambiar lo minimo necesario por PR.

## Alcance
1. `accounts`
2. `budget`
3. `core`
4. `memberships`
5. `net_worth`
6. `config` (solo wiring, auth, errores, settings)

## Fuera de alcance (por ahora)
1. Cambios grandes de producto/UX.
2. Nuevos modulos funcionales.
3. Integraciones externas complejas.
4. Reescritura completa de migraciones historicas.

## Fase 0 - Baseline y mapa del backend (completada en documento)
Objetivo: saber que hay y donde duele, con evidencia.

### 0.1 Inventario por app (estado actual)

| App | Archivos clave | Lineas aprox. | Tests | Lectura de riesgo |
| --- | --- | ---: | --- | --- |
| `accounts` | `views.py`, `auth_views.py`, `services.py`, `tests.py` | `views 99`, `auth_views 30`, `tests 127` | Si (API + services) | Medio |
| `budget` | `views.py`, `serializers.py`, `services.py`, `models.py`, `tests.py` | `views 178`, `serializers 380`, `services 307`, `tests 641` | Si (API + serializers + services) | Medio-Alto |
| `core` | `views.py`, `serializers.py`, `services.py`, `tests.py` | `views 12`, `services 191`, `tests 185` | Si (principalmente services) | Medio |
| `memberships` | `views.py`, `serializers.py`, `services.py`, `models.py` | `views 82`, `serializers 69`, `services 241` | No archivo `tests.py` detectado | Alto |
| `net_worth` | `views.py`, `serializers.py`, `services.py`, `models.py`, `tests.py` | `views 155`, `serializers 283`, `services 853`, `tests 1183` | Si (amplio) | Alto |
| `config` | `exceptions.py`, `urls.py` | `exceptions 50`, `urls 28` | Cobertura indirecta | Medio |

### 0.2 Inventario de superficie publica (endpoints)

#### `accounts`
1. JWT login/refresh (`token`, `refresh`).
2. `mode/` (estado de auth core).
3. `ops/metrics/` (metricas auth).
4. `link-token/` (token de vinculacion SaaS/Core).
5. `settings/` (lectura/escritura de preferencias usuario).

Cobertura actual:
1. Hay tests API y de services.
2. Buen candidato para fijar contratos de error/auth primero.

#### `memberships`
1. `family-members` (CRUD + `ensure-primary`).
2. `ownerships` (CRUD con serializer read/write distinto).
3. `ownership-links` (`list` + `sync`).

Cobertura actual:
1. No se detectaron tests del modulo.
2. Riesgo alto por impacto transversal (ownership/familia) sobre `net_worth` y `budget`.

#### `net_worth`
1. `assets` (CRUD).
2. `liabilities` (CRUD con side effects de budget).
3. `liquidity-checkins` (CRUD).
4. `snapshots` (read/delete + `from-current` + `import-bulk`).
5. `summary/`.
6. `liquidity/monthly-summary/`.

Cobertura actual:
1. Cobertura fuerte en tests (services, serializers, API).
2. Sigue siendo hotspot por volumen de logica en `services.py` y side effects.

#### `budget`
1. `annual-income` (CRUD + `totals` + `monthly-summary`).
2. `annual-expense` (CRUD + `totals` + `monthly-summary`).
3. `annual-income-checkins` (CRUD).
4. `annual-expense-checkins` (CRUD).

Cobertura actual:
1. Cobertura buena (API, serializers y services).
2. Views con parsing repetido de query params y reglas de `confirmed_at` duplicadas.

#### `core`
1. `fx-rates` (CRUD).
2. `inflation` (CRUD).

Cobertura actual:
1. Tests fuertes en `services.py`.
2. Falta explicitar/regresar contratos API basicos (errores, permisos, shape).

### 0.3 Hallazgos de logica mezclada / deuda visible

#### Riesgo alto
1. `core/backend/memberships/tests.py` no existe.
2. `core/backend/net_worth/services.py` (853 lineas) concentra demasiadas responsabilidades:
   - validaciones
   - calculos financieros
   - snapshots
   - summaries
   - sync con `budget`
3. `core/backend/net_worth/views.py` contiene logica de import (`import_bulk`) con loop y `update_or_create` en la view (candidato claro a service).
4. Posible bug de copy/paste en `core/backend/net_worth/views.py`:
   - `LiquidityMonthlyCheckinViewSet.perform_update()` llama `sync_generated_budget_commitments_for_liability(...)`
   - el objeto guardado es un `LiquidityMonthlyCheckin`, no una `Liability`.
   - Debe cubrirse con test antes de corregir/refactorizar.

#### Riesgo medio
1. `core/backend/budget/views.py` repite parsing de query params (`year`, `month`, ids) y manejo manual de errores `400`.
2. `core/backend/budget/views.py` duplica reglas de `confirmed_at` en dos viewsets de checkins.
3. `core/backend/budget/serializers.py` y `core/backend/net_worth/serializers.py` tienen validaciones complejas (bien encaminadas, pero densas).
4. `core/backend/accounts/views.py` mezcla respuestas con shape canonico y respuestas manuales.

#### Riesgo bajo
1. `core/backend/core/views.py` es simple, pero necesita tests API minimos para proteger permisos/shape.
2. `config/exceptions.py` ya define contrato canonico de errores (buena base).

### 0.4 Checklist por app con prioridades (entregable Fase 0)

#### `memberships` (prioridad ALTA)
1. [ ] Crear tests API de regresion para `family-members`, `ownerships`, `ownership-links/sync`.
2. [ ] Cubrir invariantes de ownership en tests de services.
3. [ ] Documentar contratos (ownership individual, split percent, borrado protegido).
4. [ ] Revisar si serializers duplican validacion con services y consolidar.

#### `net_worth` (prioridad ALTA)
1. [ ] Crear tests de regresion para `liquidity-checkins` update (bug copy/paste sospechado).
2. [ ] Extraer `snapshots import/from-current/summary` a services especializados.
3. [ ] Separar `services.py` por subdominios (validations, liabilities, snapshots, summaries, liquidity).
4. [ ] Revisar transacciones en escrituras con side effects hacia `budget`.
5. [ ] Revisar contratos de error en summaries e importaciones.

#### `budget` (prioridad MEDIA)
1. [ ] Extraer parsing de query params a helpers/serializers de filtros.
2. [ ] Unificar logica `confirmed_at` de checkins en helper/service.
3. [ ] Reducir duplicacion entre income/expense viewsets donde sea seguro.
4. [ ] Mantener tests actuales verdes y agregar regresiones en endpoints de filtros invalidados.

#### `core` (prioridad MEDIA)
1. [ ] Agregar tests API minimos de permisos y shape para `fx-rates` e `inflation`.
2. [ ] Verificar contrato de errores via `config.exceptions`.
3. [ ] Mantener `services.py` como fuente de reglas (sin mover logica a views).

#### `accounts` (prioridad MEDIA-BAJA)
1. [ ] Homogeneizar errores manuales (`link-token`) con contrato canonico.
2. [ ] Verificar contratos de auth/token/settings con tests API (ya hay base).
3. [ ] Revisar si `UserSettingsAPIView.put` debe usar serializer de update con instancia.

#### `config` (prioridad BAJA pero transversal)
1. [ ] Confirmar que todos los endpoints usan `custom_exception_handler`.
2. [ ] Documentar shape canonico de error (codigo/mensaje/details).
3. [ ] Definir lista oficial de `error.code` usados por Core.

## Fase 1 - Contratos y errores consistentes
Objetivo: estabilizar la superficie publica antes de mover internals.

### 1.1 Entregables de la fase
1. Contrato de errores documentado y probado.
2. Contratos criticos documentados y con tests de regresion.
3. Lista de endpoints criticos con estado de cobertura.

### 1.2 Paso a paso (PRs recomendados)

#### PR 1.1 - Contrato canonico de errores (transversal)
1. Auditar respuestas manuales `Response({"detail": ...}, status=400)` y respuestas con shape custom en views.
2. Decidir criterio:
   - usar excepciones DRF/Django y dejar que `custom_exception_handler` normalize.
   - reservar respuestas manuales solo si se respeta shape canonico.
3. Agregar tests de contrato en endpoints representativos:
   - `accounts/link-token/` (feature disabled)
   - `budget/*/monthly-summary` (query invalida/faltante)
   - `net_worth/summary` y `snapshots/from-current` (errores de validacion)
4. Publicar tabla `error.code` soportados en docs.

#### PR 1.2 - Contratos criticos de ownership/family (`memberships`)
1. Documentar reglas de ownership individual, splits y borrado protegido.
2. Crear tests API de `memberships` cubriendo:
   - `ensure-primary`
   - create/update ownership con splits validos/invalidos
   - `ownership-links/sync`
   - delete bloqueado cuando hay uso
3. Crear tests unitarios de services para invariantes.

#### PR 1.3 - Contratos criticos `net_worth` y `budget`
1. Congelar contratos de:
   - create/update liabilities (incluye side effects budget)
   - snapshots `from-current`
   - summaries (`net-worth` y `liquidity`)
   - budget `monthly-summary` y checkins
2. Agregar tests de regresion para bug sospechado de `liquidity-checkins` update.
3. Anotar endpoints con cobertura incompleta para Fase 3.

### 1.3 Criterio de salida
1. Cualquier error validado devuelve shape canonico en endpoints activos (o excepcion documentada temporalmente).
2. `memberships` deja de ser modulo sin tests.
3. Endpoints criticos de `net_worth` y `budget` tienen tests de regresion minimos.

## Fase 2 - Separacion de responsabilidades (views -> serializers -> services)
Objetivo: reducir acoplamiento y logica dispersa.

### 2.1 Regla objetivo por capa
1. Views:
   - orquestacion minima
   - permisos/throttling
   - status codes
   - delegar parsing/negocio
2. Serializers:
   - shape + validacion de input/output
   - sin side effects de negocio complejos
3. Services:
   - reglas de negocio
   - operaciones atomicas
   - side effects coordinados

### 2.2 Paso a paso por modulo (orden recomendado)

#### Paso 2.1 - `memberships` (primero)
1. Revisar `views.py` y confirmar que la mayor parte del negocio ya esta en `services.py`.
2. Consolidar validaciones duplicadas serializer/service:
   - mantener serializer como adaptador de input
   - service como autoridad de invariantes de dominio
3. Extraer helpers privados de `services.py` en secciones claras (`members`, `ownership`, `ownership_links`) o modulos separados.
4. Mantener transacciones en services (ya hay varios `@transaction.atomic`).

Resultado esperado:
1. `memberships/views.py` queda muy delgada.
2. Servicios con nombres/agrupacion mas claros.

#### Paso 2.2 - `net_worth` (segundo, por riesgo)
1. Cortar `services.py` por subdominio sin cambiar API publica de services (primero wrappers, luego renombre interno):
   - `services/validation.py`
   - `services/liabilities.py`
   - `services/snapshots.py`
   - `services/summaries.py`
   - `services/liquidity.py`
2. Extraer `import_bulk` desde `views.py` a service dedicado.
3. Extraer parsing y validacion de query params de `summary`/`liquidity` si crece la logica.
4. Corregir bug de `LiquidityMonthlyCheckinViewSet.perform_update()` solo despues de tener test rojo/verde.
5. Revisar side effects de liabilities hacia `budget` en una funcion de orquestacion clara.

Resultado esperado:
1. `net_worth/views.py` sin loops de import ni reglas de negocio.
2. `net_worth/services.py` deja de ser monolito unico.

#### Paso 2.3 - `budget` (tercero)
1. Extraer helper comun para parseo de query params (`year`, `month`, ids) y errores consistentes.
2. Extraer logica de `confirmed_at` de checkins a helper/service reutilizable.
3. Evaluar mixin para `totals`/`monthly-summary` entre income y expense si reduce duplicacion real sin opacar lectura.
4. Mantener reglas de taxonomia en services; serializers solo adaptan y normalizan.

Resultado esperado:
1. Menos duplicacion en views.
2. Misma respuesta API y mismos tests.

#### Paso 2.4 - `core` y `accounts` (cuarto)
1. `core`: mantener views simples; reforzar solo contrato y permisos.
2. `accounts`: mover cualquier shape manual de error a handler canonico (o helper comun de error) sin tocar funcionalidad.

### 2.3 Criterio de salida
1. Apps prioritarias (`memberships`, `net_worth`, `budget`) alineadas al patron de capas.
2. Views sin logica de negocio compleja ni side effects extensos.
3. Refactor respaldado por tests creados en Fase 1.

## Fase 3 - Tests y calidad del dominio
Objetivo: refactorizar mas rapido sin miedo.

### 3.1 Objetivos concretos
1. Tests unitarios de services criticos por modulo.
2. Tests API de flujos clave por modulo.
3. Helpers/fixtures reutilizables.
4. Menos tests fragiles acoplados a detalles internos.

### 3.2 Plan por modulo

#### `memberships`
1. Crear `tests/` package (si sigue con `tests.py`, migrar gradualmente sin romper discovery).
2. Separar:
   - `test_api_family_members.py`
   - `test_api_ownerships.py`
   - `test_api_ownership_links.py`
   - `test_services_ownership.py`
3. Crear factories/helpers minimos para user/member/ownership/splits.

#### `net_worth`
1. Mantener cobertura actual pero reorganizar tests por dominio (si el archivo unico crece mas).
2. Agregar regresiones faltantes detectadas en Fase 1:
   - `liquidity-checkins` update
   - errores de `import_bulk`
   - permisos/scoping en endpoints menos cubiertos
3. Cubrir integracion con `budget` en casos representativos, no exhaustivos duplicados.

#### `budget`
1. Agregar tests para filtros invalidos con shape de error canonico (si se cambia manejo).
2. Agregar tests de helper de `confirmed_at` si se extrae.
3. Mantener tests de serializer como red de seguridad de taxonomias y normalizacion.

#### `core` y `accounts`
1. `core`: tests API minimos de permisos/CRUD basico/error shape.
2. `accounts`: tests de contrato de errores y auth metrics/settings/link-token.

### 3.3 Criterio de salida
1. Cobertura funcional minima en modulos activos con foco en contratos y side effects.
2. `memberships` con cobertura base estable.
3. Casos criticos de `net_worth` y `budget` protegidos contra regresion.

## Fase 4 - Transacciones, integridad y rendimiento basico
Objetivo: evitar bugs de datos y regresiones de rendimiento.

### 4.1 Checklist tecnico
1. Revisar uso de `transaction.atomic` en escrituras complejas.
2. Revisar `select_related/prefetch_related` en listados principales.
3. Revisar constraints/indexes utiles (sin sobre-optimizar).
4. Revisar import/export y sync de ownership.

### 4.2 Paso a paso

#### Paso 4.1 - Transacciones e integridad
1. `memberships/services.py`:
   - verificar fronteras atomicas en create/update/delete ownership y links.
   - asegurar invariantes si hay side effects multiples.
2. `net_worth`:
   - revisar create/update liabilities y sync con `budget`.
   - revisar `snapshots/from-current` y `import_bulk` para atomicidad apropiada (por lote o por fila, decision documentada).
3. `budget`:
   - confirmar que checkins y actualizaciones de `confirmed_at` no dejan estados inconsistentes.

#### Paso 4.2 - Query efficiency basica
1. Revisar listados principales (`ownerships`, `liquidity-checkins`, `snapshots`, `assets`, `liabilities`).
2. Medir queries en tests API de endpoints pesados (assert aproximado o inspeccion manual con debug toolbar en dev local).
3. Aplicar `select_related/prefetch_related` solo donde exista evidencia de N+1.

#### Paso 4.3 - Constraints/indexes (solo si duele)
1. Revisar modelos con filtros frecuentes por `user`, fechas, `fiscal_year`, `month`, foreign keys.
2. Agregar indexes/constraints solo con respaldo de consultas reales y tests/migracion pequena.

### 4.3 Criterio de salida
1. Flujos de escritura criticos seguros y razonablemente eficientes.
2. Sin regressions funcionales en tests API.
3. Decisiones de atomicidad y performance documentadas en PRs.

## Fase 5 - Limpieza tecnica y DX (contribucion comunitaria)
Objetivo: facilitar contribucion comunitaria.

### 5.1 Tareas de limpieza
1. Estandarizar nombres/estructura por app (`tests/`, `services/`, helpers).
2. Eliminar codigo muerto o helpers duplicados identificados en fases previas.
3. Mejorar docs de backend para contributors (estructura por capas, como correr tests, convenciones de errores).
4. Extraer backlog de tareas pequenas publicables.

### 5.2 Entregables
1. Lista `good first issue` basada en hotspots reales (1 etiqueta por modulo minimo).
2. Guia corta de patron backend (views/serializers/services/tests).
3. Checklist de PR para refactors (contrato + tests + validacion Docker).

### 5.3 Criterio de salida
1. Otra persona puede continuar el refactor sin contexto tribal.
2. Hay tareas pequenas y seguras publicables para comunidad.

## Secuencia de ejecucion recomendada (paso a paso, completa)
Esta es la resolucion practica del roadmap completo. Ejecutar en orden.

1. Fase 1.1: contrato canonico de errores (transversal).
2. Fase 1.2: tests y contratos `memberships` (el mayor hueco actual).
3. Fase 1.3: tests de regresion `net_worth`/`budget` (incluye bug sospechado `liquidity-checkins` update).
4. Fase 2.1: refactor `memberships` (capas y claridad de services).
5. Fase 2.2 (parte A): extraer `net_worth` services por subdominio sin cambiar comportamiento.
6. Fase 2.2 (parte B): mover `import_bulk` y corregir bug de update con tests.
7. Fase 2.3: simplificar `budget` views (parsing filtros + `confirmed_at`).
8. Fase 2.4: homogeneizar `accounts`/`core` contratos y errores.
9. Fase 3: consolidar suite de tests por modulo y fixtures/helpers reutilizables.
10. Fase 4: transacciones + integridad + rendimiento basico.
11. Fase 5: limpieza tecnica, docs y backlog comunidad.

## Matriz de validacion por PR (Docker)
Ejecutar dentro de contenedores. No usar `docker compose down -v`.

### Diagnostico estandar (antes de tocar)
1. `docker compose ps`
2. `docker compose logs --tail 100 <service>`
3. Opcional: `docker compose ps -a`

### Calidad minima Core backend (por PR que toque `core/backend/`)
1. `cd core`
2. `docker compose exec backend ruff check .`
3. `docker compose exec backend ruff format --check .`
4. `docker compose exec backend mypy .`

### Tests minimos Core backend (por fase)
1. `cd core`
2. `docker compose exec backend python manage.py test memberships`
3. `docker compose exec backend python manage.py test net_worth`
4. `docker compose exec backend python manage.py test budget`
5. `docker compose exec backend python manage.py test accounts`
6. `docker compose exec backend python manage.py test core`

Nota:
1. Ajustar servicio si el nombre del contenedor en `docker-compose.yml` no es `backend`.
2. En PRs pequenos, correr solo el modulo afectado + tests de integracion relacionados.

## Checklist de PR de refactor (usar en todas las fases)
1. [ ] Hay test de regresion para el comportamiento que se protege/cambia.
2. [ ] No cambia el contrato API (o el cambio esta documentado y aprobado).
3. [ ] La logica de negocio se mueve hacia services, no hacia views.
4. [ ] El diff evita cambios cosmÃ©ticos fuera del alcance.
5. [ ] Validado con calidad/tests dentro de Docker.
6. [ ] Docs actualizadas si cambia contrato/capability/flujo.
7. [ ] Commit con Conventional Commits.

## Riesgos a vigilar durante toda la ejecucion
1. Refactor grande en `net_worth` sin wrapper de compatibilidad interna (riesgo de romper imports/tests).
2. Cambiar shapes de error accidentalmente al tocar views.
3. Duplicar validaciones en serializer y service generando mensajes inconsistentes.
4. Side effects `net_worth` -> `budget` sin transaccion clara.
5. PRs demasiado grandes que mezclen test + refactor + comportamiento.

## Criterio de exito (primer corte)
1. Endpoints Core criticos con tests de regresion.
2. Logica de negocio principal fuera de views.
3. Errores mas consistentes en modulos activos.
4. Documentacion suficiente para que otra persona continue el refactor.
5. `memberships` deja de ser el principal hueco de cobertura.

## Como puede ayudar la comunidad (despues de Fase 3)
1. Reportar hotspots (archivos dificiles de mantener).
2. Abrir PRs pequenos por modulo.
3. Anadir tests antes de refactor.
4. Mejorar docs y ejemplos de uso API.
5. Tomar issues de limpieza/fixtures/errores con contrato ya establecido.
