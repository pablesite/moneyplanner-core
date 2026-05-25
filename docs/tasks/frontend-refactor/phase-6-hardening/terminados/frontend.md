# Task: Frontend Refactor — Fase 6: Hardening, limpieza final y shared package doc

## Context
Refactor closure phase. Verify that there are no active legacy wrappers or imports left,
resolves known test warnings, completes regression coverage on composables
extracted and documents the extraction-ready domains as a shared package.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Final verification of 0 imports legacy in views and domains.
2. Resolution of the warning `onMounted` in `net-worth/__tests__/composables.spec.ts`.
3. Complete regression tests on extracted composables/components in phases 2-5.
4. Creation of `core/docs/architecture/shared-package-candidates.md`.
5. Update canonical frontend docs.

**Out of scope:**
1. Nuevas funcionalidades.
2. Cambios de comportamiento.
3. Implementar el shared package.

## Plan

### Diagnosis
1. Ejecutar audit final de imports legacy:
   ```bash
   grep -r "@/lib/api\|@/lib/errors\|@/stores/\|@/components/BaseModal\|@/components/AppHeader" \
     core/frontend/src --include="*.ts" --include="*.vue"
   # → 0 resultados en vistas; solo permitido en lib/ propio
   ```
2. Ejecutar suite completa y registrar warnings:
   ```bash
   docker compose -f core/docker-compose.yml exec frontend npm run test:unit 2>&1 | grep -i warn
   ```
3. Revisar el coverage report para detectar gaps residuales.

### Change implementation
1. **Resolver imports legacy residuales:**
   - Por cada resultado del grep: trazar el import, migrarlo al dominio correcto.

2. **Resolver warning `onMounted`:**
   - `core/frontend/src/domains/net-worth/__tests__/composables.spec.ts`
   - El warning indica que se usa `onMounted` fuera de una instancia Vue activa.
- Solution: wrap the composable under test in `withSetup()` helper or use `mount()` from Vue Test Utils.

3. **Regression tests:**
- For each composable extracted in phases 2-5 that does not have tests or has incomplete ones:
add tests until you reach ≥80% coverage.
   - Prioridad: composables de shell (Fase 2), composables de vistas grandes (Fase 3).

4. **Crear `core/docs/architecture/shared-package-candidates.md`:**
   - Listar dominios exportables: `net-worth`, `people`, `guide`, `aux-data`, `data-input`, `ui`
- For each: preparation status, blockers resolved, next steps
- List what is NOT shareable and why: `auth`, `capabilities`, `lib/api.ts`
   - Estructura propuesta para el futuro shared package (sin implementar)

5. **Update canonical frontend docs:**
   - `docs/frontend/frontend-visual-guide.md` — si quedan actualizaciones pendientes
   - `docs/frontend/frontend-css-workflow.md` — workflow final post-refactor
- `docs/frontend/domain-map.md` (Core) — if the domain structure changed
   - `core/docs/roadmap/terminados/frontend-refactor-roadmap.md` — marcar todas las fases completadas

### Core validation
Aplicar los mismos pasos en `frontend/` Core.
`shared-package-candidates.md` is only for Core (unified architecture doc).

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run format:check
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:unit 2>&1 | grep -i warn
# → 0 warnings de arquitectura
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ≥80% todas las métricas

# Verificar estructura final:
grep -r "@/lib/api\|@/lib/errors\|@/stores/" core/frontend/src/views --include="*.vue"
# → 0 resultados
grep -r "@/stores/" core/frontend/src/domains --include="*.ts" --include="*.vue"
# → 0 resultados

# Core
docker compose exec frontend npm run lint
docker compose exec frontend npm run format:check
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run test:coverage
```

## Required Documentation Updates
- [x] `core/docs/architecture/shared-package-candidates.md` — **crear**
- [x] `core/docs/roadmap/terminados/frontend-refactor-roadmap.md` — marcar todas las fases completadas
- [x] `docs/frontend/frontend-visual-guide.md` — si hay actualizaciones pendientes
- [x] `docs/frontend/frontend-css-workflow.md` — workflow post-refactor
- [x] `docs/frontend/domain-map.md` — update if domain structure changed
- [x] `core/docs/project-status.md` — mark Phase 6 and frontend refactor as completed
- [x] `docs/project-status.md` — update Core frontend refactor state

## Risks
- **Risk:** residual warnings in third-party tests or libraries that cannot be resolved.
**Mitigation:** Explicitly document which warnings are external and accepted.
- **Risk:** Branch coverage may be difficult to achieve in UI components.
**Mitigation:** use `/* v8 ignore */` with supporting comment for purely branches
non-testable visuals; document what is ignored in this spec file.

## Completion Criteria
- [x] 0 imports legacy en vistas y dominios
- [x] 0 architecture warnings in the test suite
- [x] `test:coverage` ≥80% on all metrics — Core
- [x] `core/docs/architecture/shared-package-candidates.md` creado
- [x] All canonical documentation updated
- [x] Roadmap Core marked as completed in all phases
- [x] Spec movida a `terminados/`
- [x] Commit final creado (Conventional Commits)

