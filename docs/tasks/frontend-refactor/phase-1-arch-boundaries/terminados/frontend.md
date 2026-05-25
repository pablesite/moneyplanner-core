# Task: Frontend Refactor — Fase 1: Fronteras de arquitectura y capas legacy

## Context
Coexisten dos arquitecturas en el frontend: la arquitectura por dominios (destino) y una capa
legacy con wrappers puente en `stores/` y componentes raíz en `components/`. Esta fase elimina
esos wrappers y mueve los componentes a sus dominios correctos, dejando los imports alineados.
Es un prerequisito para Fase 3 (descomposición de vistas) y para la preparación del shared package.

## Area
`frontend`

## Stack
`both`

## Scope
**In scope:**
1. Eliminar wrappers `stores/netWorth.ts` y `stores/people.ts`.
2. Mover `components/BaseModal.vue` → `domains/ui/BaseModal.vue`.
3. Mover `components/AppHeader.vue` → `domains/auth/components/AppHeader.vue`.
4. Actualizar todos los imports afectados.
5. Alinear `index.ts` de cada dominio como frontera pública interna.
6. Verificar que ningún dominio importa de `@/stores/*` ni de `@/components/*` raíz.

**Out of scope:**
1. Cambios de comportamiento o lógica de negocio.
2. Descomposición de vistas (Fase 3).
3. Limpiar `lib/` (Fase 5).

## Plan

### Diagnosis
1. Verificar referencias activas a `@/stores/netWorth`:
   ```bash
   grep -r "stores/netWorth" core/frontend/src --include="*.ts" --include="*.vue"
   ```
2. Verificar referencias a `@/stores/people`:
   ```bash
   grep -r "stores/people" core/frontend/src --include="*.ts" --include="*.vue"
   ```
3. Verificar referencias a `@/components/BaseModal` y `@/components/AppHeader`:
   ```bash
   grep -r "components/BaseModal\|components/AppHeader" core/frontend/src --include="*.ts" --include="*.vue"
   ```
4. Listar el `index.ts` de cada dominio para ver qué exporta hoy.

### Change implementation
1. **Migrar `stores/netWorth.ts`:**
   - Encontrar todos los archivos que importan de `@/stores/netWorth`.
   - Reemplazar cada import con el equivalente desde `@/domains/net-worth` (vía `index.ts`).
   - Verificar que `domains/net-worth/index.ts` exporta todo lo necesario; añadir exports si falta.
   - Borrar `stores/netWorth.ts`.

2. **Migrar `stores/people.ts`:**
   - Mismo proceso: reemplazar imports con `@/domains/people`.
   - Verificar exports en `domains/people/index.ts`.
   - Borrar `stores/people.ts`.

3. **Mover `BaseModal.vue`:**
   - `domains/ui/` ya existe. Añadir `BaseModal.vue` allí.
   - Actualizar `domains/ui/index.ts` para exportarlo.
   - Reemplazar todos los imports de `@/components/BaseModal` por `@/domains/ui`.
   - Borrar `components/BaseModal.vue`.

4. **Mover `AppHeader.vue`:**
   - `domains/auth/components/` ya existe (tiene `AppHeader.vue` propio). Verificar si
     `components/AppHeader.vue` raíz es diferente o redundante.
   - Si es redundante: reemplazar imports por `@/domains/auth/components/AppHeader.vue`.
   - Si tiene diferencias: consolidar en el dominio auth antes de borrar.
   - Borrar `components/AppHeader.vue` raíz.

5. **Alinear `index.ts` de dominios:**
   - Revisar que cada dominio expone en su `index.ts` todo lo que las vistas necesitan.
   - Dominios a revisar: `net-worth`, `people`, `auth`, `aux-data`, `accounting`, `data-input`, `guide`, `ui`.

6. **Verificar aislamiento de dominios:**
   - Ningún archivo en `domains/` debe importar de `@/stores/*` ni de `@/components/*` raíz.

### Core validation
Aplicar los mismos cambios en `frontend/` Core respetando las diferencias conocidas:
- `components/people/` no existe en Core (solo en Core): omitir ese paso.
- Los 3-4 ficheros distintos (api.ts, accounting/models.ts, AccountingMovementsView) no son
  afectados por esta fase.

## Validation
```bash
# Core
docker compose -f core/docker-compose.yml exec frontend npm run lint
docker compose -f core/docker-compose.yml exec frontend npm run typecheck
docker compose -f core/docker-compose.yml exec frontend npm run test:coverage
# → ejecutado durante cierre de fase; baseline global (>=80%) sigue en Fase 0

# Verificar que no quedan imports legacy:
grep -r "stores/netWorth\|stores/people\|components/BaseModal\|components/AppHeader" \
  core/frontend/src --include="*.ts" --include="*.vue"
# → 0 resultados

# Core
docker compose exec frontend npm run lint
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run test:coverage
# → ejecutado durante cierre de fase; baseline global (>=80%) sigue en Fase 0
```

## Required Documentation Updates
- [x] `core/docs/roadmap/terminados/frontend-refactor-roadmap.md` — actualizar estado Fase 1
- [x] `core/docs/project-status.md` — marcar Fase 1 como completada

## Risks
- **Riesgo:** `AppHeader.vue` raíz puede tener lógica diferente a `domains/auth/components/AppHeader.vue`.
  **Mitigación:** comparar los dos ficheros antes de borrar; consolidar diferencias en el dominio auth.
- **Riesgo:** un `index.ts` de dominio incompleto rompe los imports de las vistas.
  **Mitigación:** ejecutar `typecheck` después de cada migración individual, no solo al final.

## Completion Criteria
- [x] 0 imports de `@/stores/netWorth`, `@/stores/people`, `@/components/BaseModal`, `@/components/AppHeader` raíz
- [x] Dominios no dependen de `@/stores/*` ni `@/components/*` raíz
- [x] `lint` y `typecheck` en verde — Core
- [x] `test:coverage` ejecutado en Core durante el cierre de fase
- [x] Documentación requerida actualizada
- [x] Spec movida a `terminados/`
- [ ] Commit creado (Conventional Commits)

## Resultado de cierre

La Fase 1 queda cerrada a nivel estructural:

1. Wrappers puente (`stores/netWorth.ts`, `stores/people.ts`) eliminados en Core.
2. `BaseModal.vue` y `AppHeader.vue` consolidados en sus dominios (`ui` y `auth`).
3. Imports legacy de raíz eliminados en fuentes `*.ts` y `*.vue`.

## Nota

La deuda de baseline global (`test:coverage >=80%` y estabilización de la suite completa) sigue
siendo responsabilidad transversal de la Fase 0.

