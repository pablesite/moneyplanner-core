# Cierre Mensual — Modo Dual (Frontend)

## Context
El backend del cierre mensual dual ya está implementado (ver `terminados/dual-mode-backend.md`). Expone una API unificada que devuelve el estado completo del cierre para un mes dado, incluyendo cobertura detectada, reconciliación, y sugerencias de distribución inteligente para usuarios casuales.

El frontend actualmente hace 6+ llamadas separadas para construir el estado del cierre. Hay que integrarlo con la nueva API, añadir el flujo de distribución inteligente, y el ciclo de vida del cierre (finalizar/reabrir/bloquear).

El refactor de presupuesto/cierre (fase 3a) ya está completado — los 4 section components están limpios y reciben datos como props.

## Area
`frontend`

## Stack
`both` (Core + SaaS mirror)

## Notas sobre la implementación backend (diferencias vs plan original)
- **Status code bloqueo de checkins**: el backend retorna **403 Forbidden** (no 409 Conflict) cuando se intenta editar un checkin con cierre FINALIZED/LOCKED. El frontend debe capturar 403 para mostrar mensaje de "reabre el cierre".
- **Sugerencias de distribución**: NO se persisten en un JSONField del modelo. Se calculan en cada `GET /monthly-close/{year}/{month}/` y vienen en el campo `suggestions` del payload. No hay cache.
- **No hay serializers dedicados**: las views retornan dicts directamente desde el servicio, no pasan por DRF serializers.
- **Aceptar sugerencias**: `PATCH` con `accept_suggestions=true` recalcula la distribución y crea checkins con `status=estimated`. No requiere enviar los importes — el backend los calcula.

## Scope

### In scope
1. Tipos TypeScript para la respuesta del API unificado (`MonthlyCloseResponse`, `DistributionSuggestion`, etc.)
2. Funciones API wrapper para los 5 endpoints del cierre mensual
3. Integración en `BudgetDashboardView.vue`: fetch unificado en modo cierre, computeds desde payload, acciones de ciclo de vida
4. Distribución inteligente: pre-rellenar inputs con sugerencias del backend, permitir ajustes manuales
5. Ciclo de vida UI: badge de status, botones finalizar/reabrir/bloquear, estado locked (inputs deshabilitados)
6. Badge "Estimado" para checkins con status `estimated`
7. Mirror de todos los cambios en `core/frontend/src/` y `frontend/src/`

### Out of scope
- Cambios en backend (ya implementado)
- Cierre anual
- Rediseño visual completo (sistema de diseño unificado es tarea separada)
- Nuevos componentes de sección (los 4 existentes se reutilizan)

## Prerequisitos
- Backend monthly-close API desplegado y funcional:
  - `GET /api/budget/monthly-close/{year}/{month}/`
  - `PATCH /api/budget/monthly-close/{year}/{month}/`
  - `POST /api/budget/monthly-close/{year}/{month}/finalize/`
  - `POST /api/budget/monthly-close/{year}/{month}/reopen/`
  - `POST /api/budget/monthly-close/{year}/{month}/lock/`
- Refactor frontend fase 3a (BudgetDashboardView) completado

## Plan

### 1. Tipos — `domains/budget/types.ts` (NUEVO)
Extraer los tipos inline de `BudgetDashboardView.vue` (~líneas 38-127) a fichero compartido. Añadir tipos para el payload real del backend:

```typescript
type MonthlyCloseStatus = 'draft' | 'finalized' | 'locked';
type CoverageMode = 'ledger' | 'checkin' | 'mixed' | 'none';

// Payload real retornado por GET /api/budget/monthly-close/{year}/{month}/
type MonthlyCloseStateResponse = {
  monthly_close: {
    id: number;
    fiscal_year: number;
    month: number;
    status: MonthlyCloseStatus;
    finalized_at: string | null;
    locked_at: string | null;
    income_total_snapshot: string | null;
    expense_total_snapshot: string | null;
    liquidity_total_snapshot: string | null;
    notes: string;
  };
  income: {
    executed: string;
    planned: string;
    coverage_mode: CoverageMode;
    completion_ratio: number;
  };
  expense: {
    executed: string;
    planned: string;
    coverage_mode: CoverageMode;
    completion_ratio: number;
  };
  liquidity: {
    current_total: string | null;
    previous_total: string | null;
    delta: string | null;
    completion_ratio: number;
    has_checkins: boolean;
  };
  has_gaps: boolean;
  suggestions: {
    income: Record<string, string>;   // { "entry_id": "amount" }
    expense: Record<string, string>;  // { "entry_id": "amount" }
  };
};
```

**Diferencias clave vs el plan original:**
- El payload se estructura como `monthly_close` + secciones (`income`, `expense`, `liquidity`), no como un objeto plano.
- Las sugerencias son `Record<string, string>` (entry_id → amount), no arrays de objetos con metadata.
- No hay campo `reconciliation` separado — el delta y totales están en `liquidity`.
- No hay campo `computed_at`.

Añadir `'estimated'` a los union types de checkin status existentes.

### 2. API — `domains/budget/api.ts` (MODIFICAR)
Añadir 5 funciones wrapper tipadas:
- `getMonthlyClose(year, month)` → GET
- `patchMonthlyClose(year, month, payload)` → PATCH
- `finalizeMonthlyClose(year, month)` → POST finalize
- `reopenMonthlyClose(year, month)` → POST reopen
- `lockMonthlyClose(year, month)` → POST lock

### 3. Index — `domains/budget/index.ts` (MODIFICAR)
Añadir `export * from './types'`.

### 4. Vista — `BudgetDashboardView.vue` (MODIFICAR)
Cambios **aditivos** — el flujo existente se mantiene para modo presupuesto anual.

**4a. Nuevo estado reactivo:**
- `monthlyCloseData: ref<MonthlyCloseStateResponse | null>`
- `monthlyCloseLoading`, `monthlyCloseError`, `monthlyCloseActionBusy`

**4b. Nueva función `refreshMonthlyCloseData()`:**
- Llama a `getMonthlyClose(year, month)`
- Hidrata los refs existentes (`liquidityMonthlySummary`, etc.) desde el payload unificado
- Los section components siguen recibiendo los mismos props — sin cambios en su interfaz de datos
- **Nota:** el endpoint unificado NO retorna los datos a nivel de fila (rows de liquidez, entries de income/expense) — solo retorna totales agregados y coverage. Las llamadas individuales para datos de fila (`liquidity/monthly-summary`, `annual-income/monthly-summary`, etc.) siguen siendo necesarias para la UI detallada de los pasos. El endpoint unificado aporta: status del cierre, `has_gaps`, `suggestions`, y datos de reconciliación (delta, previous_total).

**4c. Modificar watchers:**
- En modo `isMonthlyCloseView`: llamar `refreshMonthlyCloseData()` ADEMÁS de los calls de datos de fila
- Tras cada mutación de checkin en modo cierre: re-fetch unificado para actualizar status y sugerencias

**4d. Computeds desde payload unificado:**
- `closeStatus` ← `monthlyCloseData.monthly_close.status`
- `isCloseLocked` ← status === 'finalized' || 'locked'
- Delta liquidez ← `monthlyCloseData.liquidity.delta`
- Previous liquidity ← `monthlyCloseData.liquidity.previous_total`
- Has gaps ← `monthlyCloseData.has_gaps`

**4e. Distribución inteligente:**
- Si `has_gaps` es true y `suggestions.income`/`suggestions.expense` no están vacíos → popular `incomeAdjustAmounts`/`expenseAdjustAmounts` con los importes sugeridos para las entradas correspondientes (key = entry_id, value = amount)
- Inputs se pre-rellenan pero el usuario puede modificar
- "Aplicar distribución" llama a `PATCH` con `accept_suggestions=true` — el backend crea los checkins con status `estimated`

**4f. Acciones de ciclo de vida:**
- `handleFinalizeClose()`, `handleReopenClose()`, `handleLockClose()`, `handleApplyDistribution()`
- Cada una llama su API, luego `refreshMonthlyCloseData()`
- Capturar **403** (no 409) para mostrar mensaje de bloqueo si el cierre está finalizado/locked

**4g. Checkin status label:**
- Añadir caso `'estimated'` → `'Estimado'`

### 5. Section components (MODIFICAR — cambios menores)

**Todos los sections (Liquidity, Income, Expense):**
- Nueva prop `isCloseLocked: boolean`
- Cuando true: deshabilitar inputs y botones
- Banner sutil: "Este mes está finalizado. Reabre el cierre para editar."
- Rows con status `estimated`: badge "Estimado" + estilo distinto (borde discontinuo, fondo claro)

**BudgetHeroSection.vue:**
- Nueva prop `closeStatus: MonthlyCloseStatus`
- Badge de status junto al indicador de pasos

**BudgetMonthlyCloseResultSection.vue:**
- Props: `closeStatus`, `isCloseLocked`, handlers de acciones, `hasDistributionSuggestion`
- Footer de acciones:
  - Draft: "Finalizar cierre" (primario) + "Aplicar distribución" si hay sugerencia
  - Finalized: "Reabrir cierre" (secundario) + "Bloquear" (danger)
  - Locked: label "Este mes está bloqueado"

### 6. CSS — `domains/budget/styles/dashboard.css` (MODIFICAR)
- `.ui-monthly-close-status-badge` — pill con color por status
- `.ui-budget-checkin-row-estimated` — borde discontinuo, fondo claro
- `.ui-monthly-close-actions` — layout footer de acciones
- `.ui-monthly-close-locked-banner` — banner de estado bloqueado

### 7. Mirror Core ↔ SaaS
Replicar todos los cambios entre `core/frontend/src/` y `frontend/src/`.

## Validation
```bash
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run format:check
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run format:check
docker compose exec saas_frontend npm run typecheck
```

Test manual:
- Abrir `/cierre-mensual`, verificar que carga datos del endpoint unificado
- Probar flujo completo: editar checkins → finalizar → verificar inputs bloqueados → reabrir → editar → finalizar → bloquear
- Probar con usuario sin movimientos: verificar que aparecen sugerencias de distribución
- Probar con usuario con movimientos ledger: verificar que rows ledger están locked

## Required Documentation Updates
- [ ] `core/docs/project-status.md` — actualizar estado cierre mensual frontend
- [ ] `core/docs/roadmap/product-roadmap.md` — marcar frontend como completado
- [ ] `docs/frontend/domain-map.md` — actualizar dominio budget con nuevos ficheros
- [ ] `docs/project-status.md` (SaaS) — actualizar referencia si aplica

## Risks
- **Backend no desplegado**: Si la API 404, `monthlyCloseError` se activa y el flujo existente sigue funcionando como fallback (los refs que hidrataría quedan null y los computeds fallback se activan).
- **403 en checkin edits cuando finalized**: `isCloseLocked` deshabilita inputs client-side. Si un request llega al backend, el **403 Forbidden** se muestra como error vía `toBudgetErrorMessage`. El backend usa `PermissionDenied` (no 409 Conflict).
- **Tamaño de la vista**: Añadir ~100 líneas de lógica a un view de ~2600 líneas no es ideal pero respeta la restricción de "no refactors sin petición explícita".

## Ficheros afectados

Replicar en `core/frontend/src/` y `frontend/src/`:

| Fichero | Acción |
|---------|--------|
| `domains/budget/types.ts` | CREAR — tipos extraídos + nuevos |
| `domains/budget/api.ts` | MODIFICAR — 5 funciones monthly-close |
| `domains/budget/index.ts` | MODIFICAR — re-exportar types |
| `views/BudgetDashboardView.vue` | MODIFICAR — estado, fetch unificado, computeds, acciones |
| `domains/budget/components/BudgetHeroSection.vue` | MODIFICAR — badge status |
| `domains/budget/components/BudgetMonthlyCloseLiquiditySection.vue` | MODIFICAR — prop isCloseLocked |
| `domains/budget/components/BudgetMonthlyCloseIncomeSection.vue` | MODIFICAR — prop isCloseLocked + estimated badge |
| `domains/budget/components/BudgetMonthlyCloseExpenseSection.vue` | MODIFICAR — prop isCloseLocked + estimated badge |
| `domains/budget/components/BudgetMonthlyCloseResultSection.vue` | MODIFICAR — acciones finalize/reopen/lock |
| `domains/budget/styles/dashboard.css` | MODIFICAR — estilos nuevos |

## Completion Criteria
- [ ] types.ts creado con todos los tipos del API unificado
- [ ] 5 funciones API wrapper funcionales y tipadas
- [ ] `refreshMonthlyCloseData()` reemplaza las 6+ llamadas en modo cierre
- [ ] Distribución inteligente pre-rellena inputs para entradas sin cobertura
- [ ] Ciclo de vida completo visible: badge status + finalizar/reabrir/bloquear
- [ ] Inputs deshabilitados cuando cierre FINALIZED/LOCKED
- [ ] Badge "Estimado" en checkins algorítmicos
- [ ] Mirror Core ↔ SaaS completo
- [ ] lint + format:check + typecheck sin errores en ambos stacks
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
