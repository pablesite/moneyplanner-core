# Task: Frontend Refactor — Fase 5: Contratos internos de dominio

## Context
Después de la descomposición de vistas (Fase 3), quedan dominios a medio migrar con interfaces
heterogéneas: falta estandarización de `api.ts / store.ts / composables.ts / models.ts / index.ts`.
Algunas vistas aún importan `@/lib/api` directamente. Esta fase cierra ese gap, estandariza
los contratos internos de dominio y prepara los dominios para ser extracción-ready (shared package).

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Estandarizar la estructura de ficheros por dominio.
2. Eliminar imports directos de `@/lib/api` y `@/lib/errors` desde vistas.
3. Asegurar que el HTTP client es configurable (no hardcodeado) en cada dominio.
4. Documentar qué dominios son exportables sin modificación.
5. Alinear dominios a medio migrar: `net-worth`, `data-input`, `guide`, `aux-data`.

**Out of scope:**
1. Cambios de comportamiento.
2. Modificaciones de contratos con el backend.
3. Implementar el shared package (solo preparar y documentar).

## Plan

### Diagnosis
1. Auditar la estructura actual de cada dominio:
   ```bash
   find core/frontend/src/domains -name "*.ts" | sort
   ```
2. Listar imports directos de `@/lib/api` en vistas y dominios:
   ```bash
   grep -r "@/lib/api\|@/lib/errors" core/frontend/src --include="*.ts" --include="*.vue"
   ```
3. Identificar dominios que hardcodean el cliente HTTP (axios directo).

### Change implementation
1. **Estandarizar estructura por dominio** (donde aplique):
   - `api.ts` — llamadas HTTP, recibe cliente inyectado o usa el shared api
   - `store.ts` — estado Pinia, importa de `api.ts` no de axios
   - `composables.ts` — lógica Vue reutilizable, importa de `store.ts` y `api.ts`
   - `models.ts` o `types.ts` — tipos e interfaces
   - `index.ts` — re-exporta la interfaz pública del dominio

2. **Eliminar imports directos desde vistas:**
   - Por cada import de `@/lib/api` o `@/lib/errors` en una vista: reemplazar por el
     método equivalente expuesto en el `index.ts` del dominio correspondiente.
   - Verificar que el dominio tiene el método necesario; añadirlo si falta.

3. **HTTP client configurable (shared package prep):**
   - Los `api.ts` de dominio deben usar el shared HTTP client de `@/lib/api.ts`
     importándolo como dependencia, no instanciando axios directamente.
   - Esto permite que en un futuro shared package, el cliente sea inyectado.
   - Documentar en `core/docs/architecture/shared-package-candidates.md` (se crea en Fase 6)
     cuáles dominios cumplen este requisito.

4. **Alinear dominios a medio migrar:**
   - `net-worth`: verificar que `composables.ts` ya no depende de `@/stores/netWorth`
     (resuelto en Fase 1); completar `models.ts` si falta.
   - `data-input`: verificar que `annualEntryUtils.ts`, `portableBundle.ts`, etc. tienen
     su punto de entrada correcto en `index.ts`.
   - `guide`: verificar que `phaseDiagnostics.ts` y `scoreVisuals.ts` están exportados.
   - `aux-data`: verificar que `types.ts` y `api.ts` están alineados con `index.ts`.

5. **Limpiar `lib/` de re-exports vacíos:**
   - Ficheros como `lib/netWorthApi.ts`, `lib/netWorthCharts.ts`, `lib/authApi.ts`, etc.
     que son re-exports vacíos: borrarlos o consolidarlos.
   - Mantener en `lib/` solo: `api.ts` (cliente HTTP), `errors.ts` (normalización),
     `format.ts` (helpers de formato).

### SaaS Replication
Aplicar los mismos cambios en `frontend/` SaaS respetando:
- `lib/api.ts` SaaS tiene baseURL diferente → mantener.
- `domains/accounting/models.ts` SaaS no tiene `MoneyWizUnmappedCategory` → no añadir.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas

# Verificar 0 imports directos de @/lib/api desde vistas:
grep -r "@/lib/api\|@/lib/errors" core/frontend/src/views --include="*.vue"
# → 0 resultados

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
```

## Required Documentation Updates
- [x] `core/docs/roadmap/frontend-refactor-roadmap.md` — actualizar estado Fase 5
- [x] `docs/frontend/domain-map.md` — si cambia la estructura pública de los dominios
- [x] `core/docs/project-status.md` — marcar Fase 5 como completada

## Risks
- **Riesgo:** borrar re-exports de `lib/` puede romper imports no detectados.
  **Mitigación:** grep exhaustivo antes de borrar; ejecutar typecheck después de cada borrado.
- **Riesgo:** alinear `index.ts` de dominios puede exponer una API que no existía antes,
  haciendo que las vistas importen más de lo esperado. **Mitigación:** solo exponer lo que
  las vistas ya usan; no ampliar la API pública sin necesidad.

## Completion Criteria
- [x] 0 imports de `@/lib/api` o `@/lib/errors` desde vistas
- [x] Todos los dominios tienen la estructura estandarizada
- [x] `lib/` contiene solo `api.ts`, `errors.ts` y `format.ts` (más sus tests)
- [x] Dominios documentados como exportables o con bloqueadores identificados
- [x] `lint`, `typecheck`, `test:coverage` ≥80% en verde — Core y SaaS
- [x] Documentación requerida actualizada
- [x] Spec movida a `terminados/`
- [x] Commit creado (Conventional Commits)
