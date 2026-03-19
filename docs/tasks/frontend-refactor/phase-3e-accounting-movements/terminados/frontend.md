# Task: Frontend Refactor — Fase 3e: Descomposición de AccountingMovementsView

## Context
`AccountingMovementsView.vue` creció de 998 a 2,263 líneas en Core (2,237 en SaaS) y ya
supera el umbral de vista mediana-grande. Mezcla hero/filtros, catálogo de cuentas, balances,
quick-entry y formulario manual avanzado. Esta fase la descompone en secciones controladas
sin cambiar comportamiento. Es la última de las vistas monolíticas y la de menor riesgo.
**Importante:** Core tiene una sección de unmapped categories (MoneyWiz) que SaaS no tiene.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Extraer composable de página para fetch y estado de movimientos contables.
2. Crear componentes de sección para los bloques principales.
3. Reducir la vista al wiring de secciones (objetivo: < 400 líneas).
4. Tests unitarios para los composables extraídos (≥80% cobertura).

**Out of scope:**
1. Cambios de comportamiento o lógica contable.
2. Modificaciones de contratos con el backend.
3. Rediseño de la interfaz de movimientos.

## Plan

### Diagnosis
1. Leer `AccountingMovementsView.vue` completo. Identificar:
   - Bloques de template separables
   - Lógica de fetch y filtrado
   - Quick-entry vs. formulario manual (son flujos distintos)
   - Sección unmapped categories (solo Core)
2. Revisar `domains/accounting/store.ts` y `composables.ts` para entender qué ya existe.

### Change implementation
1. **Composable de página:** `domains/accounting/composables/useAccountingMovementsPage.ts`
   - fetch de movimientos, cuentas ledger y balances
   - filtros activos (cuenta, período, tipo)
   - estado de modal (quick-entry vs. formulario avanzado)

2. **Secciones como componentes:**
   - `AccountingMovementsHero.vue` — cabecera y filtros principales
   - `AccountingAccountCatalog.vue` — catálogo de cuentas ledger
   - `AccountingBalances.vue` — balances por cuenta
   - `AccountingQuickEntry.vue` — entrada rápida de movimientos
   - `AccountingEntryForm.vue` — formulario manual avanzado
   - `AccountingUnmappedCategories.vue` — unmapped categories MoneyWiz (**solo Core**)

3. **Vista resultante** (`AccountingMovementsView.vue`):
   - Instancia `useAccountingMovementsPage()`
   - Renderiza las secciones
   - En Core: incluye `AccountingUnmappedCategories`
   - En SaaS: no incluye ese componente (diferencia preservada)

4. **Tests:**
   - `domains/accounting/__tests__/useAccountingMovementsPage.spec.ts`

### SaaS Replication
- Aplicar los mismos cambios en `frontend/` SaaS.
- **NO replicar** `AccountingUnmappedCategories.vue` ni su uso en la vista SaaS.
- **NO replicar** el tipo `MoneyWizUnmappedCategory` si se mueve/crea en esta fase.
- Verificar que `AccountingMovementsView.vue` SaaS sigue sin la sección de unmapped categories.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas; AccountingMovementsView <400 líneas

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
```

## Required Documentation Updates
- [ ] `core/docs/roadmap/terminados/frontend-refactor-roadmap.md` — actualizar estado Fase 3e
- [ ] `core/docs/frontend/accounting-movements-ux-notes.md` — si cambia la composición de la vista
- [ ] `core/docs/project-status.md` — marcar Fase 3e como completada

## Risks
- **Riesgo:** quick-entry y formulario avanzado pueden compartir estado reactivo.
  **Mitigación:** mapear el estado compartido antes de separar; usar un composable común si es necesario.
- **Riesgo:** la sección de unmapped categories Core puede tener lógica acoplada al resto de la vista.
  **Mitigación:** aislarla primero como componente dentro de la vista antes de extraerla completamente.

## Completion Criteria
- [ ] `AccountingMovementsView.vue` < 400 líneas (Core y SaaS)
- [ ] Core mantiene sección unmapped categories; SaaS no la tiene
- [ ] Composables extraídos con tests ≥80% cobertura
- [ ] Sin cambios de comportamiento observados en browser
- [ ] `lint`, `typecheck`, `test:coverage` ≥80% en verde — Core y SaaS
- [ ] Documentación requerida actualizada
- [ ] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits)

