# Roadmap: refactor integral del frontend (Core) — plan ejecutable

## Objetivo

Dejar el frontend del Core mas facil de mantener, probar y extender, sin romper contratos
backend ni introducir cambios funcionales no intencionales.
El refactor tambien prepara el terreno para un futuro shared package Core/SaaS,
dejando documentada la extraccion futura en la Fase 6.

## Estado de este documento

1. Este documento define el plan operativo del refactor del frontend Core.
2. Baseline actualizada el 2026-03-19.
3. Las fases 0-6 quedan desglosadas en entregables, pasos recomendados y criterios de salida.
4. El trabajo debe ejecutarse en PRs pequenas, reversibles y validadas dentro de Docker.
5. Core-first: cada fase se ejecuta primero en Core y se replica en SaaS al cerrarla.
   Ver `docs/roadmap/frontend-refactor-roadmap.md` (SaaS) para el roadmap espejo.

## Estado real (2026-03-19)

### Baseline del stack Core

- `backend`, `frontend`, `db` y `fx_sync` levantados en Docker.
- frontend validado dentro del contenedor `frontend`.

### Validacion actual en Docker

- `docker compose exec frontend npm run lint`: verde
- `docker compose exec frontend npm run typecheck`: verde
- `docker compose exec frontend npm run test:unit`: verde (37 suites)
- `docker compose exec frontend npm run format:check`: verde
- `docker compose exec frontend npm run test:coverage`: verde con thresholds `>=80%`

### Coverage thresholds actuales (vite.config.ts)

```
statements: 80%, lines: 80%, functions: 80%, branches: 80%
```

**Target acordado: >= 80% en todas las metricas** (Fase 0).

### Coverage real actual (2026-03-19)

Con la suite actual en verde, `test:coverage` reporta:

- `statements: 88.72%`
- `lines: 88.72%`
- `functions: 89.17%`
- `branches: 81.73%`

Fase 0 cerrada: todos los thresholds de coverage (`>=80%`) pasan en Core y SaaS.
La exclusion temporal de superficies monoliticas/legacy se reevalua en fases 2-6.
Fases 4, 5 y 6 cerradas el 2026-03-19: CSS contract, domain contracts y hardening completados,
con `core/docs/architecture/shared-package-candidates.md` creado y las specs archivadas en `terminados/`.

### Hotspots de tamano actuales

| Vista | Lineas | Riesgo |
|-------|--------|--------|
| `BudgetDashboardView.vue` | 5,512 | Alto |
| `NetWorthView.vue` | 542 | Completada Fase 3b el 2026-03-18 |
| `DataInputView.vue` | 16 | Completada Fase 3c el 2026-03-19 |
| `AccountingMovementsView.vue` | 51 | Completada Fase 3e el 2026-03-19 |
| `GuidePhaseDetailView.vue` | 111 | Completada Fase 3d el 2026-03-19 |
| `App.vue` | 13 | Completada Fase 2 el 2026-03-19 |

### Deuda estructural visible

- Wrappers puente y componentes raiz legacy eliminados en Fase 1:
  - `frontend/src/stores/netWorth.ts` (eliminado)
  - `frontend/src/stores/people.ts` (eliminado)
  - `frontend/src/components/BaseModal.vue` -> `domains/ui/components/BaseModal.vue`
  - `frontend/src/components/AppHeader.vue` -> `domains/auth/components/AppHeader.vue`
- Vistas importan directamente `@/lib/api` y `@/lib/errors`
- `lib/` tiene ~8 ficheros que son re-exports vacios de dominios
- `frontend/src/styles/app.css`: 20,633 lineas — el fichero mas grande del frontend
- Fase 2 cerrada: shell extraida a `src/shell/` y residuales retirados (`HelloWorld.vue`, `SettingsFxView.vue`, `SettingsIpcView.vue`, `style.css`)

### Lectura de riesgo (actualizada)

- riesgo alto: `BudgetDashboardView`, `NetWorthView`
- riesgo medio: `AccountingMovementsView` (crecio x2.3), `styles/app.css`
- riesgo bajo: `App.vue` (Fase 2 cerrada), `lib/` re-exports

### Candidatos a shared package Core/SaaS

Documentados en `core/docs/architecture/shared-package-candidates.md`.

Los siguientes dominios son identicos en ambos frontends:
`net-worth`, `people`, `guide`, `aux-data`, `data-input`, `ui`
No compartibles: `auth` (URLs distintas), `capabilities` (planes distintos), `lib/api.ts`
La Fase 5 preparo los dominios para que sean inyectables; la Fase 6 dejo documentada la
extraccion y sus limites.

## Principios de trabajo (obligatorios)

1. Refactor por fases pequenas.
2. Sin cambios de comportamiento no intencionales.
3. Primero baseline y tests; despues estructura; despues descomposicion de vistas.
4. Cada fase deja el repo ejecutable.
5. Validacion dentro de Docker en cada PR.
6. Cambiar lo minimo necesario por PR.
7. Core-first: cada fase termina con SaaS replication (ver spec).

## Alcance

1. `core/frontend/src/App.vue`
2. `core/frontend/src/router.ts`
3. `core/frontend/src/views/*`
4. `core/frontend/src/domains/*`
5. `core/frontend/src/styles/*`
6. `core/frontend/src/lib/*`
7. `core/frontend/src/stores/*`
8. `core/frontend/src/components/*`
9. `core/frontend/vite.config.ts` (thresholds de coverage)
10. `core/docs/roadmap/*` y docs frontend canonicas si cambia el contrato visual compartido

## Fuera de alcance (por ahora)

1. Rediseno funcional del producto.
2. Cambios de contratos backend o payloads publicos.
3. Reescritura total del frontend desde cero.
4. Implementar el shared package (solo preparar el terreno).
5. Introduccion de nuevas capacidades de negocio.

## Arquitectura objetivo

1. `domains/*` como unica capa de negocio del frontend.
2. `views/*` como ensamblado de pagina:
   - sin acceso directo a HTTP
   - sin reglas de negocio distribuidas
   - sin parsing/error handling transversal repetido
3. `styles/app.css` como fuente principal del contrato visual compartido.
4. Utilidades cross-domain en una capa shared explicita y pequena.
5. `index.ts` de cada dominio como frontera publica interna.
6. Dominios autocontenidos sin dependencias de `@/stores/*` ni `@/components/*`
   (requisito previo a extraccion como shared package).

---

## Fase 0 — Baseline limpia y cobertura >= 80%

Objetivo: partir de una base verde completa con red de seguridad real.

### 0.1 Entregables

1. Thresholds de coverage subidos a >= 80% en todas las metricas.
2. Tests nuevos que cierran los gaps identificados.
3. Formato de `app.css` corregido (verde en `format:check`).
4. Baseline documentada en este roadmap.

### 0.2 Paso a paso recomendado

1. Ejecutar y registrar baseline en Docker:
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - `docker compose exec frontend npm run test:unit`
   - `docker compose exec frontend npm run test:coverage`
2. Subir thresholds en `vite.config.ts`: `statements: 80, lines: 80, functions: 80, branches: 80`
3. Ejecutar `test:coverage` y analizar que areas fallan.
4. Escribir tests unitarios por prioridad:
   - Composables de dominio no cubiertos
   - Utilidades sin tests
   - Componentes criticos
5. Corregir el formateo de `app.css`.
6. SaaS Replication: mismos pasos en `frontend/` SaaS.

### 0.3 Criterio de salida

1. `lint`, `format:check`, `typecheck` y `test:unit` en verde.
2. `test:coverage` pasa todos los thresholds >= 80%.
3. Baseline documentada y actualizada en este roadmap.

**Spec:** `core/docs/tasks/frontend-refactor/phase-0-baseline/terminados/frontend.md`

---

## Fase 1 — Fronteras de arquitectura y capa legacy

Objetivo: fijar limites claros entre dominios y eliminar wrappers puente.

### 1.1 Entregables

1. Eliminacion de wrappers puente (`stores/netWorth.ts`, `stores/people.ts`).
2. `BaseModal.vue` movido a `domains/ui/`.
3. `AppHeader.vue` movido a `domains/auth/components/`.
4. Imports alineados a dominios en archivos refactorizados.
5. `index.ts` de cada dominio revisado como frontera publica interna.

### 1.2 Paso a paso recomendado

1. Migrar imports de `@/stores/netWorth` -> `@/domains/net-worth`.
2. Migrar imports de `@/stores/people` -> `@/domains/people`.
3. Mover `components/BaseModal.vue` -> `domains/ui/BaseModal.vue`; actualizar imports.
4. Mover `components/AppHeader.vue` -> `domains/auth/components/AppHeader.vue`; actualizar imports.
5. Borrar wrappers solo cuando no tengan referencias activas.
6. Revisar `index.ts` de cada dominio para que resuma su interfaz publica.
7. Verificar que ningun dominio importa de `@/stores/*` ni `@/components/*` raiz.
8. SaaS Replication.

### 1.3 Riesgos a cubrir

1. Evitar churn de imports sin valor funcional.
2. No mezclar en la misma PR migracion de wrappers y refactor de comportamiento.
3. `AppHeader.vue` raiz puede tener logica diferente a la del dominio auth.

### 1.4 Criterio de salida

1. 0 imports de `@/stores/netWorth`, `@/stores/people`, `@/components/BaseModal`, `@/components/AppHeader` raiz.
2. Dominios no dependen de `@/stores/*` ni `@/components/*` raiz.
3. Suite de tests en verde con cobertura >= 80%.

**Spec:** `core/docs/tasks/frontend-refactor/phase-1-arch-boundaries/terminados/frontend.md`

---

## Fase 2 — Shell global, router y componentes residuales

Objetivo: adelgazar `App.vue` y dejar el wiring de navegacion testeable.

### 2.1 Entregables

1. Shell global descompuesta en componentes/composables.
2. `App.vue` reducido a ensamblador fino (< 150 lineas).
3. Router con definicion mas consistente.
4. Archivos residuales retirados.

### 2.2 Paso a paso recomendado

1. Extraer desde `App.vue`:
   - navegacion principal, menu de cuenta, control de sidebar, listeners globales, bloqueo de scroll
2. Crear composables de shell en `src/shell/` o `domains/shell/`.
3. Limpiar `router.ts`: ordenar imports, meta solo donde aporta.
4. Retirar `SettingsFxView.vue` y `SettingsIpcView.vue` (7 lineas cada una).
5. Retirar `components/HelloWorld.vue` y `style.css`.
6. Anadir/ajustar tests de shell y router.
7. SaaS Replication.

### 2.3 Criterio de salida

1. `App.vue` deja de concentrar logica de interaccion compleja.
2. Shell y router tienen responsabilidades separadas.
3. Sin archivos residuales.
4. Suite de tests en verde con cobertura >= 80%.

**Spec:** `core/docs/tasks/frontend-refactor/phase-2-shell-router/terminados/frontend.md`

---

## Fase 3 — Descomposicion de vistas monoliticas

Objetivo: dividir las vistas grandes en composables de pagina, secciones y componentes de dominio.

### 3.1 Orden recomendado (mayor a menor riesgo)

1. `BudgetDashboardView.vue` (5,512 lineas al inicio, 2,362 tras cierre) — **spec 3a completada**
2. `NetWorthView.vue` (3,608 lineas al inicio, 542 tras cierre) — **spec 3b completada**
3. `DataInputView.vue` (2,742 lineas al inicio, 16 tras cierre) — **spec 3c completada**
4. `GuidePhaseDetailView.vue` (2,207 lineas al inicio, 111 tras cierre) — **spec 3d completada**
5. `AccountingMovementsView.vue` (2,263 lineas al inicio, 51 tras cierre) — **spec 3e completada**

### 3.2 Regla de extraccion

La vista conserva: composicion de pagina, navegacion local, wiring de secciones.
Los composables de pagina reciben: fetch, mapping, derivadas complejas, side effects, acciones.
Los componentes de seccion reciben: bloques reutilizables, fragmentos grandes de template.

### 3.3 Extracciones minimas esperadas

#### `BudgetDashboardView` (5,512 lineas)

1. Secciones: modo anual, modo cierre mensual, ledger coverage, check-ins, sugerencias ledger.
2. Cierre estructural aceptable: vista en rol de orquestacion, bloques grandes extraidos y CSS del dashboard fuera del SFC.

#### `NetWorthView` (3,608 lineas)

1. Secciones: filtros de ownership, timeline, analitica y ratios, detalle, actividad ledger.
2. Reubicar calculos de la vista a composables del dominio/pagina.

#### `DataInputView` (2,742 lineas al inicio, 16 tras cierre)

1. Secciones: patrimonio, ingresos, gastos, portable, ownership filters.
2. Reducir mezcla entre patrimonio, presupuestos y portabilidad.

#### `GuidePhaseDetailView` (2,207 lineas al inicio, 111 tras cierre)

1. Extraer scoring, diagnosticos y formatos compartidos a `domains/guide`.
2. Eliminar duplicacion de calculos con `HomeView.vue`.

#### `AccountingMovementsView` (2,263 lineas)

1. Separar: hero/filtros, catalogo de cuentas, balances, quick-entry, formulario manual avanzado.
2. En Core: seccion unmapped categories (MoneyWiz). En SaaS: omitir.

### 3.4 Criterio de salida

1. Las vistas principales quedan reducidas a wiring de pagina y composicion de secciones.
2. Objetivo practico para vistas grandes en esta fase: ~600-900 lineas tras extraer
   fetch, derivadas complejas y side effects de dominio.
3. Los side effects de pagina viven en composables.
4. La logica derivada compartida deja de duplicarse entre vistas.
5. Cada composable extraido tiene tests con cobertura >= 80%.

**Specs:**
- `core/docs/tasks/frontend-refactor/phase-3a-budget-dashboard/terminados/frontend.md`
- `core/docs/tasks/frontend-refactor/phase-3b-net-worth/terminados/frontend.md`
- `core/docs/tasks/frontend-refactor/phase-3c-data-input/terminados/frontend.md`
- `core/docs/tasks/frontend-refactor/phase-3d-guide-view/terminados/frontend.md`
- `core/docs/tasks/frontend-refactor/phase-3e-accounting-movements/terminados/frontend.md`

---

## Fase 4 — Refactor de CSS y contrato visual

Objetivo: reforzar el contrato visual compartido y reducir CSS ad hoc por pantalla.

### 4.1 Entregables

1. `app.css` (20,633 lineas) con patrones consolidados y organizados.
2. Reduccion sustancial de `<style scoped>` en shell y vistas grandes.
3. Estados loading/empty/error/success estandarizados.
4. Tokens CSS candidatos a `shared/styles/` documentados.

### 4.2 Paso a paso recomendado

1. Consolidar en `app.css` patrones de:
   page shell, section shell, action bars, state blocks, filtros, metric cards, tablas, modales.
2. Revisar y reducir `<style scoped>` en:
   `App.vue`, `BudgetDashboardView`, `NetWorthView`, `GuidePhaseDetailView`, `AccountingMovementsView`,
   `domains/net-worth/components/ItemForm.vue`.
3. Mover a shared styles cualquier patron usado en >= 2 pantallas.
4. Evaluar destino de: `guide-home.css`, `guide-score.css`, `data-input.css`.
5. Actualizar `docs/frontend/frontend-visual-guide.md` y `docs/frontend/frontend-css-workflow.md`.
6. SaaS Replication.

### 4.3 Criterio de salida

1. Las vistas principales usan el contrato visual compartido.
2. CSS de pagina ad hoc disminuye claramente.
3. Los estados no felices quedan estandarizados.

**Spec:** `core/docs/tasks/frontend-refactor/phase-4-css-contract/terminados/frontend.md`

---

## Fase 5 — Contratos internos de dominio

Objetivo: vistas consumen APIs tipadas de dominio; 0 imports directos a `@/lib/api`.

### 5.1 Entregables

1. Interfaces de dominio homogeneas (`api.ts`, `store.ts`, `composables.ts`, `models.ts`, `index.ts`).
2. Composables de pagina donde hoy hay mezcla fetch/mapping/format/UI.
3. 0 imports de `@/lib/api` ni `@/lib/errors` desde vistas refactorizadas.
4. Dominios con HTTP client configurable (requisito para shared package).

### 5.2 Paso a paso recomendado

1. Estandarizar estructura por dominio donde aplique.
2. Prohibir acceso directo a `axios` o clientes HTTP genericos desde vistas.
3. Introducir composables de pagina donde hoy hay mezcla de fetch/mapping/format/UI.
4. Alinear dominios a medio migrar: `net-worth`, `data-input`, `guide`, `aux-data`.
5. Limpiar `lib/` de re-exports vacios; mantener solo `api.ts`, `errors.ts`, `format.ts`.
6. Documentar dominios exportables (para futuro shared package).
7. SaaS Replication.

### 5.3 Criterio de salida

1. Las vistas consumen APIs internas tipadas de dominio.
2. 0 imports de `@/lib/api` y `@/lib/errors` desde vistas refactorizadas.
3. Las reglas de parsing/error dejan de repetirse pantalla a pantalla.

**Spec:** `core/docs/tasks/frontend-refactor/phase-5-domain-contracts/terminados/frontend.md`

---

## Fase 6 — Limpieza final, hardening y documentacion de shared package

Objetivo: cerrar deuda residual, 0 warnings conocidos, estructura comprensible y documentada.

### 6.1 Entregables

1. 0 wrappers o placeholders innecesarios.
2. 0 warnings de arquitectura en la suite relevante.
3. `core/docs/architecture/shared-package-candidates.md` creado.
4. Documentacion frontend canonica actualizada.

### 6.2 Paso a paso recomendado

1. Verificar que no quedan imports a `@/lib/api`, `@/lib/errors`, `@/stores/*` en vistas.
2. Resolver warning de `onMounted` fuera de instancia activa en `net-worth/__tests__/composables.spec.ts`.
3. Completar tests de regresion sobre composables/componentes extraidos en fases 2-5.
4. Redactar `core/docs/architecture/shared-package-candidates.md`:
   - Dominios ready: `net-worth`, `people`, `guide`, `aux-data`, `data-input`, `ui`
   - No compartibles y por que: `auth`, `capabilities`, `lib/api.ts`
   - Pasos siguientes para la extraccion (fuera del scope de este roadmap)
5. Actualizar docs frontend canonicas.
6. SaaS Replication.

### 6.3 Criterio de salida

1. Sin wrappers o placeholders innecesarios.
2. Sin warnings de arquitectura conocidos.
3. Estructura del frontend legible para un nuevo colaborador.
4. `shared-package-candidates.md` creado y enlazado.

**Spec:** `core/docs/tasks/frontend-refactor/phase-6-hardening/terminados/frontend.md`

---

## Reglas de interfaces y contratos

1. No cambiar rutas publicas ni contratos backend durante el refactor.
2. La interfaz publica interna de cada dominio debe quedar resumida en su `index.ts`.
3. Las vistas no deben importar directamente:
   - `@/lib/api`, `@/lib/errors`, `@/stores/*`, wrappers en `@/components/*` raiz
4. La capa shared puede alojar: HTTP client, auth session, format helpers, error normalization.
5. Cualquier patron visual consolidado en `app.css` debe evaluarse para sincronizacion con SaaS.

## Validacion minima por fase

```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run format:check
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# -> statements >=80%, lines >=80%, functions >=80%, branches >=80%

# SaaS (al replicar)
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run format:check
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
# -> mismos thresholds
```

## Orden recomendado de ejecucion

1. Fase 0 (baseline + tests)
2. Fase 1 (arch boundaries)
3. Fase 2 (shell + router)
4. Fase 3a (BudgetDashboardView)
5. Fase 3b (NetWorthView)
6. Fase 3c (DataInputView)
7. Fase 3d (GuidePhaseDetailView)
8. Fase 3e (AccountingMovementsView)
9. Fase 4 (CSS)
10. Fase 5 (domain contracts)
11. Fase 6 (hardening + shared package doc)

## Entregables por PR

1. Un objetivo claro por PR.
2. Validacion Docker adjunta al cierre.
3. Sin mezclar limpieza estructural y cambio funcional no relacionado.
4. Commit final con Conventional Commits.

## Nota de trazabilidad

1. Este roadmap define el refactor del frontend Core.
2. Para SaaS: ver `docs/roadmap/frontend-refactor-roadmap.md`.
3. Si durante la ejecucion aparece una mejora UX reutilizable, actualizar primero la documentacion canonica.
4. Si una fase descubre deuda funcional real, aislarla en una subtarea o PR separado.


