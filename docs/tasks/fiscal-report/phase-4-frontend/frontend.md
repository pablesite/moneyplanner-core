# Phase 4 — Informe fiscal: frontend Core

## Context

Interfaz para gestionar credenciales de exchange, lanzar sync de datos, importar CSVs
y visualizar el informe fiscal anual completo.

UX objetivo: tablas limpias estilo TradeRepublic — agrupadas por activo/fuente,
columna Casilla visible, totales por sección, resumen de casillas listo para copiar
en el formulario de Hacienda.

Prerequisito: Phase 3 completada (`GET /api/v1/broker/fiscal-report/?year=2025` operativo).

## Area
`frontend`

## Stack
`core`

## Scope

### In scope
- Nuevo dominio `core/frontend/src/domains/fiscal-report/`
- Rutas: `/informe-fiscal` (landing) y `/informe-fiscal/informe` (informe)
- Componentes listados abajo
- Skill `frontend-system` antes de empezar

### Out of scope
- Core verification (diferido, no parte del MVP)
- Exportación a PDF

## Plan

### 1. Diagnosis
1. Ejecutar skill `frontend-system`
2. Leer `core/docs/frontend/` para convenciones de componentes, CSS y diseño
3. Verificar que `GET /api/v1/broker/fiscal-report/?year=2025` devuelve JSON con datos reales

### 2. Change implementation

**Estructura del dominio**
```
core/frontend/src/domains/fiscal-report/
  api.ts           # llamadas REST: credentials CRUD, sync, csv-import, fiscal-report
  store.ts         # Pinia: credentials[], syncStatus, report data, selectedYear
  composables.ts   # useFiscalReport(year), useBrokerSync(credentialId)
  components/
    FiscalAccountList.vue
    FiscalCredentialForm.vue
    FiscalCsvImport.vue
    FiscalReportView.vue
    FiscalCapitalMobiliarioTable.vue
    FiscalBotResultsTable.vue
    FiscalFuturesTable.vue
    FiscalGananciasPerdidaTable.vue
    FiscalReportSummary.vue
    FiscalAvisos.vue
    FiscalDataSourcesBadge.vue
  views/
    FiscalLandingView.vue
    FiscalInformeView.vue
```

**Componentes**

`FiscalAccountList.vue`
- Lista de credenciales con: broker badge, label, estado API (connected/error), timestamp último sync
- Botón "Sync" por credencial → llama `POST /api/v1/broker/sync/{id}/`
- Botón "Eliminar" → `DELETE /api/v1/broker/credentials/{id}/`

`FiscalCredentialForm.vue`
- Formulario: broker (dropdown Pionex/Binance), label, api_key, api_secret
- `api_secret` field tipo password
- Submit → `POST /api/v1/broker/credentials/`

`FiscalCsvImport.vue`
- Upload multi-archivo con selector de tipo:
  - Broker: Pionex / Binance
  - Tipo de fichero (depende del broker seleccionado): trading, staking, others, position_futures, dust / transacciones, convert, recurring
- Submit → `POST /api/v1/broker/csv-import/`
- Mostrar resultado: N registros importados

`FiscalReportView.vue`
- Selector de año (2024, 2025, ...)
- Botón "Generar informe" → `GET /api/v1/broker/fiscal-report/?year=YYYY`
- Contenedor con todas las secciones + `FiscalAvisos` + `FiscalDataSourcesBadge`

`FiscalCapitalMobiliarioTable.vue`
- Columnas: Fuente | Activo | Importe EUR | Casilla
- Fila de total: Total Casilla 029
- Sección I del informe

`FiscalBotResultsTable.vue`
- Columnas: Bot | Tipo | Período | Ganancia neta EUR | Casilla | ⚠
- Badge de aviso en columna ⚠ → tooltip "Simplificación: ver nota fiscal"

`FiscalFuturesTable.vue`
- Columnas: Símbolo | Dirección | Apertura | Cierre | PNL EUR | Casilla | ⚠
- Badge ⚠ → tooltip "Derivados perpetuos: tratamiento fiscal puede diferir"

`FiscalGananciasPerdidaTable.vue`
- Agrupado por denominación (BTC, ETH)
- Columnas: Denominación | V. Adquisición EUR | V. Transmisión EUR | Ganancia | Pérdida | Casilla
- Expandible por lote (buy_date, sell_date, exchange_buy, exchange_sell, qty)
- Totales por sección

`FiscalReportSummary.vue`
- Tarjeta de resumen tipo "lista para copiar":
  ```
  Casilla 029 (Capital mobiliario): X,XX €
  Casilla 332 (Ganancias/pérdidas): X,XX €
  ```
- Botón "Copiar" por casilla

`FiscalAvisos.vue`
- Lista de avisos del campo `avisos[]` del informe
- Estilo: warning banner suave, no bloqueante

`FiscalDataSourcesBadge.vue`
- Badge compacto: "Datos: API ✓ | CSV fallback: staking, others"
- Basado en campo `data_sources` del informe

**Rutas en `router.ts`**
```typescript
{ path: '/informe-fiscal', component: FiscalLandingView, name: 'fiscal-landing' },
{ path: '/informe-fiscal/informe', component: FiscalInformeView, name: 'fiscal-informe' },
```

### 3. Validation

```bash
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run format:check
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
```

Test manual E2E:
1. `/informe-fiscal` → añadir credencial Pionex → verificar aparece en lista
2. Botón Sync → ver stats (N trades, N income events)
3. Upload `staking.csv` → ver contador de IncomeEvent subir en sync status
4. `/informe-fiscal/informe` selector año 2025 → "Generar informe"
5. Verificar todas las secciones renderizadas con datos reales (no ceros)
6. `FiscalReportSummary`: verificar que los totales coinciden con suma manual de secciones
7. Botón "Copiar" de una casilla → verificar clipboard

## Required Documentation Updates
- [ ] `core/docs/frontend/fiscal-report-ux-notes.md` — crear con notas de UX del módulo
- [ ] `core/docs/project-status.md` — marcar Phase 4 completada
- [ ] Verificar si el cambio debe replicarse en `frontend/` Core (regla espejado Core→Core) — documentar explícitamente si no aplica en este MVP

## Risks
1. Formateo de decimales para cantidades crypto muy pequeñas (e.g. 0.00000013 ETH) → usar utilidad de formateo ya existente en Core, no inventar nueva
2. Aviso de futuros/bots puede alarmar innecesariamente → diseñar como badge informativo con tooltip, no como error bloqueante

## Completion Criteria
- [ ] Todas las rutas accesibles sin errores de consola
- [ ] Informe 2025 muestra datos reales con totales numéricos correctos
- [ ] `FiscalReportSummary` muestra casillas copiables con valores correctos
- [ ] Todos los comandos de validación pasan
- [ ] Documentation updates done
- [ ] Spec movida a `terminados/`
- [ ] Commit: `feat(fiscal-report): add broker integrations UI`
