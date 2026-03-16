# Roadmap: refactor integral del frontend (Core) - plan ejecutable

## Objetivo
Dejar el frontend del Core mas facil de mantener, probar y extender, sin romper contratos backend ni introducir cambios funcionales no intencionales.

## Estado de este documento
1. Este documento define el plan operativo del refactor del frontend Core.
2. Incluye Fase 0 con baseline real del repo revisada el 2026-03-16.
3. Las fases 1-6 quedan desglosadas en entregables, pasos recomendados y criterios de salida.
4. El trabajo debe ejecutarse en PRs pequenas, reversibles y validadas dentro de Docker.

## Estado real (2026-03-16)
1. Baseline del stack Core:
   - `backend`, `frontend`, `db` y `fx_sync` levantados en Docker.
   - frontend validado dentro del contenedor `frontend`.
2. Validacion actual en Docker:
   - `docker compose exec frontend npm run lint`: verde
   - `docker compose exec frontend npm run typecheck`: verde
   - `docker compose exec frontend npm run test:unit`: verde (`34` suites, `137` tests)
   - `docker compose exec frontend npm run format:check`: falla solo en `frontend/src/styles/app.css`
3. Hotspots de tamano actuales:
   - `frontend/src/views/BudgetDashboardView.vue`: ~4836 lineas
   - `frontend/src/views/NetWorthView.vue`: ~3218 lineas
   - `frontend/src/views/DataInputView.vue`: ~2557 lineas
   - `frontend/src/views/GuidePhaseDetailView.vue`: ~2033 lineas
   - `frontend/src/views/AccountingMovementsView.vue`: ~998 lineas
   - `frontend/src/App.vue`: ~492 lineas
4. Deuda estructural visible:
   - coexistencia de arquitectura por dominios con capas legacy en `frontend/src/lib`, `frontend/src/stores` y `frontend/src/components`
   - wrappers puente todavia activos:
     - `frontend/src/stores/netWorth.ts`
     - `frontend/src/stores/people.ts`
     - `frontend/src/components/BaseModal.vue`
     - `frontend/src/components/AppHeader.vue`
   - varias vistas siguen importando `@/lib/api` y `@/lib/errors` directamente
   - `frontend/src/domains/net-worth/composables.ts` sigue dependiendo de `@/stores/netWorth`
   - varios `<style scoped>` siguen concentrando patrones visuales de pagina y shell
   - archivos aparentemente residuales o placeholder:
     - `frontend/src/components/HelloWorld.vue`
     - `frontend/src/views/SettingsFxView.vue`
     - `frontend/src/views/SettingsIpcView.vue`
     - `frontend/src/style.css`
5. Lectura de riesgo:
   - riesgo alto: `BudgetDashboardView`, `NetWorthView`, `DataInputView`
   - riesgo medio: `GuidePhaseDetailView`, `App.vue`, `styles/app.css`
   - riesgo medio-bajo: wrappers puente, archivos residuales, contratos internos de dominio

## Principios de trabajo (obligatorios)
1. Refactor por fases pequenas.
2. Sin cambios de comportamiento no intencionales.
3. Primero baseline, contratos internos y shell; despues descomposicion de vistas.
4. Cada fase deja el repo ejecutable.
5. Validacion dentro de Docker en cada PR.
6. Cambiar lo minimo necesario por PR.
7. Mantener Core-first: cualquier patron compartido que deje de ser Core-only debe evaluarse para sincronizacion posterior con SaaS.

## Alcance
1. `core/frontend/src/App.vue`
2. `core/frontend/src/router.ts`
3. `core/frontend/src/views/*`
4. `core/frontend/src/domains/*`
5. `core/frontend/src/styles/*`
6. `core/frontend/src/lib/*`
7. `core/frontend/src/stores/*`
8. `core/frontend/src/components/*`
9. `core/docs/roadmap/*` y docs frontend canonicas si cambia el contrato visual compartido

## Fuera de alcance (por ahora)
1. Rediseño funcional del producto.
2. Cambios de contratos backend o payloads publicos.
3. Reescritura total del frontend desde cero.
4. Paridad automatica inmediata con SaaS para todo el refactor interno.
5. Introduccion de nuevas capacidades de negocio fuera del alcance de mantenimiento/refactor.

## Arquitectura objetivo
1. `domains/*` como unica capa de negocio del frontend.
2. `views/*` como ensamblado de pagina:
   - sin acceso directo a HTTP
   - sin reglas de negocio distribuidas
   - sin parsing/error handling transversal repetido
3. `styles/app.css` como fuente principal del contrato visual compartido.
4. Utilidades cross-domain en una capa shared explicita y pequena.
5. `index.ts` de cada dominio como frontera publica interna.

## Fase 0 - Baseline y reglas del refactor
Objetivo: partir de una base limpia y con reglas explicitadas antes de mover estructura.

### 0.1 Entregables
1. Roadmap canonico creado y versionado.
2. Baseline de validacion documentada.
3. Deuda de formato inicial resuelta en `frontend/src/styles/app.css`.

### 0.2 Paso a paso recomendado
1. Crear este documento y enlazarlo desde las tareas de frontend que dependan del refactor.
2. Ejecutar y registrar baseline en Docker:
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - `docker compose exec frontend npm run test:unit`
3. Corregir primero el formateo de `frontend/src/styles/app.css` para partir de verde completo.
4. No mover vistas grandes hasta dejar cerrada esta baseline.

### 0.3 Criterio de salida
1. El frontend Core queda verde en `lint`, `format:check`, `typecheck` y `test:unit`.
2. La baseline y el orden de trabajo quedan documentados.

## Fase 1 - Fronteras de arquitectura y capa legacy
Objetivo: fijar limites claros entre dominios, vistas y utilidades compartidas.

### 1.1 Entregables
1. Convencion unica para utilidades shared.
2. Eliminacion de wrappers puente innecesarios.
3. Imports alineados a dominios/shared en archivos refactorizados.

### 1.2 Paso a paso recomendado
1. Decidir y documentar una sola capa shared para:
   - cliente HTTP
   - auth session
   - format helpers
   - error normalization
2. Mantener `lib` solo si se redefine explicitamente como shared estable; si no, migrar a una ubicacion dedicada y reducirla.
3. Eliminar dependencias nuevas hacia:
   - `frontend/src/stores/*`
   - `frontend/src/components/*`
   - utilidades legacy sin frontera publica definida
4. Migrar wrappers puente:
   - reemplazar imports de `frontend/src/stores/netWorth.ts` por imports directos del dominio `net-worth`
   - reemplazar imports de `frontend/src/stores/people.ts` por imports directos del dominio `people`
   - reemplazar imports de `frontend/src/components/BaseModal.vue` y `frontend/src/components/AppHeader.vue` por sus dominios reales
5. Borrar wrappers solo cuando no tengan referencias activas.
6. Alinear `index.ts` de cada dominio para que resuma su interfaz publica interna.

### 1.3 Riesgos a cubrir
1. Evitar churn de imports sin valor funcional.
2. No mezclar en la misma PR migracion de wrappers y refactor de comportamiento.

### 1.4 Criterio de salida
1. Ninguna vista refactorizada importa desde wrappers legacy.
2. `net-worth`, `people`, `auth`, `aux-data`, `accounting` y `data-input` exponen interfaces internas claras.
3. La capa shared queda pequena y justificada.

## Fase 2 - Shell global, router y composables de pagina
Objetivo: adelgazar `App.vue` y dejar el wiring de navegacion testeable.

### 2.1 Entregables
1. Shell global descompuesta en componentes/composables.
2. `App.vue` reducido a ensamblador fino.
3. Router con definicion mas consistente y facil de leer.

### 2.2 Paso a paso recomendado
1. Extraer desde `frontend/src/App.vue`:
   - navegacion principal
   - menu de cuenta
   - control de sidebar
   - listeners globales
   - bloqueo de scroll
2. Crear componentes/composables especificos de shell, sin mover logica de negocio de dominios a la shell.
3. Revisar `frontend/src/router.ts` para:
   - ordenar imports y definicion de rutas
   - agregar `meta` solo si aporta a shell o navegacion
   - mantener `registerAuthGuard(router)` desacoplado del wiring visual
4. Verificar si `SettingsFxView.vue` y `SettingsIpcView.vue` siguen teniendo razon de existir; si no, retirarlos en una PR de limpieza controlada.
5. Agregar o ajustar tests de shell/router si cambia la composicion.

### 2.3 Criterio de salida
1. `App.vue` deja de concentrar logica de interaccion compleja.
2. Shell y router tienen responsabilidades separadas.
3. La navegacion actual sigue funcionando sin cambios de rutas publicas.

## Fase 3 - Descomposicion de vistas monoliticas
Objetivo: dividir las vistas grandes en composables de pagina, secciones y componentes de dominio.

### 3.1 Orden recomendado
1. `BudgetDashboardView.vue`
2. `NetWorthView.vue`
3. `DataInputView.vue`
4. `GuidePhaseDetailView.vue`
5. `AccountingMovementsView.vue`

### 3.2 Regla de extraccion
1. La vista conserva:
   - composicion de pagina
   - navegacion local
   - wiring de secciones
2. Los composables de pagina reciben:
   - fetch
   - mapping
   - derivadas complejas
   - side effects
   - acciones de usuario
3. Los componentes de seccion reciben:
   - bloques reutilizables
   - fragmentos grandes de template
   - UI repetitiva con props claras

### 3.3 Extracciones minimas esperadas
#### `BudgetDashboardView`
1. Secciones separadas para:
   - modo presupuesto anual
   - modo cierre mensual
   - ledger coverage
   - check-ins de ingresos/gastos/liquidez
   - sugerencias derivadas del ledger
2. Composable de pagina para filtros, fetch y acciones.

#### `NetWorthView`
1. Secciones separadas para:
   - filtros de ownership
   - timeline
   - analitica y ratios
   - detalle de posicion
   - actividad ledger contextual
2. Reubicar calculos que hoy viven en la vista a composables del dominio/pagina.

#### `DataInputView`
1. Secciones separadas para:
   - patrimonio
   - ingresos
   - gastos
   - import/export portable
   - ownership filters
2. Reducir mezcla actual entre patrimonio, presupuestos y portabilidad en un solo archivo.

#### `GuidePhaseDetailView` y `HomeView`
1. Extraer scoring, diagnosticos y formatos compartidos a `domains/guide`.
2. Evitar duplicacion de calculos entre ambas vistas.

#### `AccountingMovementsView`
1. Separar:
   - hero/filtros
   - catalogo de cuentas
   - balances
   - quick-entry
   - formulario manual avanzado
2. Mantener esta vista como caso de extraccion controlada y no como rediseño.

### 3.4 Criterio de salida
1. Ninguna vista principal mantiene miles de lineas mezclando datos, logica y template sin fronteras.
2. Los side effects de pagina viven en composables.
3. La logica derivada compartida deja de duplicarse entre vistas.

## Fase 4 - Refactor de CSS y contrato visual
Objetivo: reforzar el contrato visual compartido y reducir CSS ad hoc por pantalla.

### 4.1 Entregables
1. `frontend/src/styles/app.css` reforzado como fuente principal de patrones compartidos.
2. Reduccion sustancial de `<style scoped>` en shell y vistas grandes.
3. Estados loading/empty/error/success alineados con el contrato visual.

### 4.2 Paso a paso recomendado
1. Consolidar en `app.css` patrones de:
   - page shell
   - section shell
   - action bars
   - state blocks
   - filtros
   - metric cards
   - tablas/listas
   - modales
2. Revisar y reducir `<style scoped>` en:
   - `frontend/src/App.vue`
   - `frontend/src/views/BudgetDashboardView.vue`
   - `frontend/src/views/NetWorthView.vue`
   - `frontend/src/views/GuidePhaseDetailView.vue`
   - `frontend/src/views/AccountingMovementsView.vue`
   - `frontend/src/domains/net-worth/components/ItemForm.vue`
3. Mover a shared styles cualquier patron usado en dos pantallas o mas.
4. Mantener CSS local solo cuando exista una razon clara de aislamiento.
5. Evaluar el destino de:
   - `frontend/src/styles/guide-home.css`
   - `frontend/src/styles/guide-score.css`
   - `frontend/src/styles/data-input.css`
6. Si un patron queda definitivamente compartido, actualizar tambien `docs/frontend/frontend-visual-contract.md`.

### 4.3 Criterio de salida
1. Las vistas principales usan el contrato visual compartido.
2. Disminuye claramente el CSS de pagina ad hoc.
3. Los estados no felices quedan estandarizados.

## Fase 5 - Contratos internos de dominio y APIs de frontend
Objetivo: hacer que las vistas consuman dominios tipados en vez de utilidades sueltas.

### 5.1 Entregables
1. Interfaces de dominio homogeneas.
2. View-model composables para paginas que hoy mezclan fetch y UX.
3. Menos reglas repetidas de parsing y manejo de error.

### 5.2 Paso a paso recomendado
1. Estandarizar por dominio, donde aplique:
   - `api.ts`
   - `store.ts`
   - `composables.ts`
   - `models.ts` o `types.ts`
   - `index.ts`
2. Prohibir acceso directo desde vistas a:
   - `axios`
   - clientes HTTP genericos
   - normalizadores de error transversales sin pasar por el dominio
3. Introducir composables de pagina o view-models donde hoy hay mezcla de:
   - fetch
   - mapping
   - format
   - reglas de UI
4. Alinear dominios que todavia estan a medio migrar:
   - `net-worth`
   - `data-input`
   - `guide`
   - `aux-data`
5. Mantener estables los contratos backend; solo se permiten mejoras internas de tipado o encapsulacion.

### 5.3 Criterio de salida
1. Las vistas consumen APIs internas tipadas de dominio.
2. Desaparece la necesidad de importar `@/lib/api` y `@/lib/errors` desde vistas refactorizadas.
3. Las reglas de parsing/error dejan de repetirse pantalla a pantalla.

## Fase 6 - Limpieza final y endurecimiento
Objetivo: cerrar deuda residual y dejar una estructura comprensible para futuros cambios.

### 6.1 Entregables
1. Eliminacion de archivos residuales y aliases no usados.
2. Warnings de tests revisados y resueltos cuando sean deuda del refactor.
3. Documentacion final alineada.

### 6.2 Paso a paso recomendado
1. Eliminar archivos placeholder o residuales si ya no tienen referencias:
   - `frontend/src/components/HelloWorld.vue`
   - `frontend/src/style.css`
   - vistas de settings residuales si quedaron fuera de uso
2. Revisar warning actual en tests:
   - `frontend/src/domains/net-worth/__tests__/composables.spec.ts` muestra uso de `onMounted` fuera de instancia activa
3. Corregir ese warning dentro de una fase de hardening, no mezclado con cambios funcionales.
4. Completar tests de regresion sobre composables/componentes extraidos en fases 2-5.
5. Actualizar este roadmap con el avance real.
6. Si cambia el contrato visual compartido, actualizar:
   - `docs/frontend/frontend-visual-contract.md`
   - `docs/frontend/frontend-css-workflow.md`
   - cualquier otra doc frontend canonica afectada

### 6.3 Criterio de salida
1. Sin wrappers o placeholders innecesarios.
2. Sin warnings de arquitectura conocidos en la suite relevante.
3. Estructura del frontend legible para un nuevo colaborador.

## Reglas de interfaces y contratos
1. No cambiar rutas publicas ni contratos backend durante el refactor, salvo correcciones internas de tipado.
2. La interfaz publica interna de cada dominio debe quedar resumida en su `index.ts`.
3. Las vistas no deben importar directamente:
   - `@/lib/api`
   - `@/lib/errors`
   - `@/stores/*`
   - wrappers en `@/components/*`
4. Si se mantiene una capa shared, debe documentarse exactamente que puede alojar:
   - HTTP client
   - auth session
   - format helpers
   - error normalization
5. Cualquier patron visual reusable consolidado en `core/frontend/src/styles/app.css` debe evaluarse para sincronizacion con `frontend/` cuando deje de ser Core-only.

## Validacion minima por fase
1. Frontend Core:
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - `docker compose exec frontend npm run test:unit`
2. Si una fase toca shell, router o composables de pagina, agregar/ajustar tests unitarios del area afectada.
3. Si una fase toca patrones visuales compartidos, validar que los estados loading/empty/error/success sigan cubiertos.

## Entregables por PR
1. Un objetivo claro por PR.
2. Validacion Docker adjunta al cierre.
3. Sin mezclar limpieza estructural y cambio funcional no relacionado.
4. Commit final con Conventional Commits.

## Orden recomendado de ejecucion
1. Fase 0
2. Fase 1
3. Fase 2
4. Fase 3 sobre `BudgetDashboardView`
5. Fase 3 sobre `NetWorthView`
6. Fase 3 sobre `DataInputView`
7. Fase 3 sobre `GuidePhaseDetailView` y `HomeView`
8. Fase 3 sobre `AccountingMovementsView`
9. Fase 4
10. Fase 5
11. Fase 6

## Nota de trazabilidad
1. Este roadmap define el refactor del frontend Core, no una iniciativa de nuevas capacidades.
2. Si durante la ejecucion aparece una mejora UX reutilizable que cambie el contrato visual compartido, debe actualizarse primero la documentacion canonica afectada.
3. Si una fase descubre deuda funcional real, esa deuda debe aislarse en una subtarea o PR separado para no desordenar el refactor.
