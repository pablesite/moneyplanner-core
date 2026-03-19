# Task: Frontend Refactor — Fase 6: Hardening, limpieza final y shared package doc

## Context
Fase de cierre del refactor. Verifica que no quedan wrappers o imports legacy activos,
resuelve warnings conocidos de tests, completa la cobertura de regresión sobre composables
extraídos y documenta los dominios listos para extracción como shared package.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Verificación final de 0 imports legacy en vistas y dominios.
2. Resolución del warning `onMounted` en `net-worth/__tests__/composables.spec.ts`.
3. Tests de regresión completos sobre composables/componentes extraídos en fases 2-5.
4. Creación de `core/docs/architecture/shared-package-candidates.md`.
5. Actualización de docs frontend canónicas.

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
   - Solución: envolver el composable bajo test en `withSetup()` helper o usar `mount()` de Vue Test Utils.

3. **Tests de regresión:**
   - Para cada composable extraído en fases 2-5 que no tenga tests o los tenga incompletos:
     añadir tests hasta alcanzar ≥80% de cobertura.
   - Prioridad: composables de shell (Fase 2), composables de vistas grandes (Fase 3).

4. **Crear `core/docs/architecture/shared-package-candidates.md`:**
   - Listar dominios exportables: `net-worth`, `people`, `guide`, `aux-data`, `data-input`, `ui`
   - Para cada uno: estado de preparación, bloqueadores resueltos, pasos siguientes
   - Listar lo que NO es compartible y por qué: `auth`, `capabilities`, `lib/api.ts`
   - Estructura propuesta para el futuro shared package (sin implementar)

5. **Actualizar docs frontend canónicas:**
   - `docs/frontend/frontend-visual-guide.md` — si quedan actualizaciones pendientes
   - `docs/frontend/frontend-css-workflow.md` — workflow final post-refactor
   - `docs/frontend/domain-map.md` (SaaS) — si cambió la estructura de dominios
   - `core/docs/roadmap/frontend-refactor-roadmap.md` — marcar todas las fases completadas

### SaaS Replication
Aplicar los mismos pasos en `frontend/` SaaS.
`shared-package-candidates.md` es solo para Core (doc de arquitectura unificada).

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

# SaaS
docker compose exec saas_frontend npm run lint
docker compose exec saas_frontend npm run format:check
docker compose exec saas_frontend npm run typecheck
docker compose exec saas_frontend npm run test:coverage
```

## Required Documentation Updates
- [ ] `core/docs/architecture/shared-package-candidates.md` — **crear**
- [ ] `core/docs/roadmap/frontend-refactor-roadmap.md` — marcar todas las fases completadas
- [ ] `docs/frontend/frontend-visual-guide.md` — si hay actualizaciones pendientes
- [ ] `docs/frontend/frontend-css-workflow.md` — workflow post-refactor
- [ ] `docs/frontend/domain-map.md` — actualizar si cambió estructura de dominios
- [ ] `core/docs/project-status.md` — marcar Fase 6 y refactor frontend como completado
- [ ] `docs/project-status.md` — actualizar estado refactor frontend SaaS

## Risks
- **Riesgo:** warnings residuales en tests de terceros o librería que no se pueden resolver.
  **Mitigación:** documentar explícitamente cuáles warnings son externos y aceptados.
- **Riesgo:** la cobertura de branches puede ser difícil de alcanzar en componentes de UI.
  **Mitigación:** usar `/* v8 ignore */` con comentario justificativo para ramas puramente
  visuales no testeables; documentar qué se ignora en este fichero de spec.

## Completion Criteria
- [ ] 0 imports legacy en vistas y dominios
- [ ] 0 warnings de arquitectura en la suite de tests
- [ ] `test:coverage` ≥80% en todas las métricas — Core y SaaS
- [ ] `core/docs/architecture/shared-package-candidates.md` creado
- [ ] Toda la documentación canónica actualizada
- [ ] Roadmap Core marcado como completado en todas las fases
- [ ] Spec movida a `terminados/`
- [ ] Commit final creado (Conventional Commits)
