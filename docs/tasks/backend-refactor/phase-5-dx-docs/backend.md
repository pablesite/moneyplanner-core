# Core backend — Phase 5: DX docs y guía de contribución

## Title
Core backend — checklist de PR, guía de patrones y backlog de contribución

## Context
Con el refactor estructural completado (fases 1-4), el objetivo de esta última fase es
dejar el backend en un estado donde otra persona pueda continuar el trabajo sin contexto
tribal. Incluye un checklist de PR reutilizable, una guía corta del patrón backend
vigente, y un backlog de tareas pequeñas publicables para contribución externa —
relevante para cuando el repo Core se abra como Open Source.

**Prerequisito:** Phase 4 completada.

## Area
`backend`

## Stack
`core`

## Scope

### En scope
1. Checklist de PR de refactor en `core/docs/standards/backend-pr-checklist.md`.
2. Guía corta de patrones backend vigentes en `core/docs/architecture/backend-patterns.md`.
3. Sección de "backlog de contribución" en `backend-refactor-roadmap.md`.
4. Actualización final del roadmap como documento de cierre.

### Fuera de scope
1. Cualquier cambio de código de producción.
2. Guía de contribución general del repo (eso es tarea del OpenSource roadmap).
3. Documentación de frontend.

## Plan

### 1. `core/docs/standards/backend-pr-checklist.md`

Crear checklist reutilizable para cualquier PR de backend Core:

```markdown
# Backend PR Checklist

## Antes de abrir el PR
- [ ] Los tests pasan: `python manage.py test <app>`
- [ ] `ruff check .` limpio
- [ ] `ruff format --check .` limpio
- [ ] `mypy .` limpio
- [ ] No hay cambios de comportamiento no intencionales
- [ ] Si cambia el contrato API: actualizado `core/docs/architecture/architecture.md`
- [ ] Si cambia un modelo: migración generada y aplicada
- [ ] Si hay side effects cross-domain: cubiertos con integration tests

## Reglas de capa
- [ ] Lógica de negocio en `services*.py`, no en `views.py`
- [ ] `views.py` solo valida input, llama al service, y retorna la respuesta
- [ ] `serializers.py` solo adapta shape y valida tipos; no ejecuta reglas de negocio
- [ ] Si el service cruza dominios: usa `transaction.atomic`

## Tests
- [ ] Nuevo comportamiento tiene al menos un test de API (happy path)
- [ ] Nuevo comportamiento tiene test de error path (auth failure, validation error)
- [ ] Lógica de negocio nueva tiene unit test en el service correspondiente

## Commits
- [ ] Conventional Commits: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- [ ] Commit atómico: un PR = un tipo de cambio (no mezclar refactor + feature)
```

### 2. `core/docs/architecture/backend-patterns.md`

Guía de patrones vigentes (≤ 2 páginas):

```markdown
# Backend patterns — Core

## Stack por capa

### Views (`views.py`)
- Thin adapters: reciben la request, llaman al service, retornan la response.
- No contienen reglas de negocio ni queries directas al ORM.
- Heredan de `UserScopedQuerySetMixin` para filtrar por usuario automáticamente.
- Retornan errores via DRF exceptions o `feature_disabled` del exception handler canónico.

### Serializers (`serializers.py`)
- Adaptan el shape de entrada/salida y validan tipos.
- No ejecutan lógica de negocio (eso va en el service).
- Pueden referenciar otros serializers para respuestas anidadas.

### Services (`services*.py`)
- Contienen las reglas de negocio y la orquestación.
- Funciones, no clases (salvo dataclasses de resultado).
- Si cruzan dominios: usan `transaction.atomic`.
- Si son grandes (> 400 líneas): partir en submódulos por subdominio.
- Convención de partición: `services_<subdominio>.py`

### Tests (`tests/`)
- Estructura por dominio: `test_api_<recurso>.py` para API tests, `test_services.py` para unit tests de service.
- API tests: usan `APITestCase` con usuario autenticado; cubren happy path + auth failure + validation error.
- Service tests: usan `TestCase`; no dependen de request/response.
- Integration tests: en `test_integration.py`; cubren flujos cross-domain.

## Exception handling
- `config/exceptions.py` define el handler canónico: `{code, message, details}`.
- Nunca retornar dicts ad-hoc con shape de error distinto.
- Para features desactivadas: `raise feature_disabled()` (no `return Response({...}, 403)`).

## UserScopedQuerySetMixin
- Heredar en cualquier ViewSet que filtre por `request.user`.
- El mixin provee `get_queryset()` con `filter(user=self.request.user)` automático.

## Módulo `config/`
- Solo para wiring (urls, settings), auth, exception handler y mixins transversales.
- No añadir lógica de dominio aquí.
```

### 3. Backlog de contribución en `backend-refactor-roadmap.md`

Añadir sección final con tareas pequeñas publicables:
- Añadir endpoint `GET /api/accounting/accounts/{id}/balance-history/`
- Añadir paginación a `GET /api/accounting/transactions/`
- Añadir filtro por fecha a `GET /api/net_worth/assets/`
- Tests de rendimiento para `build_monthly_accounting_summary` con > 100 entries
- Medir y documentar tiempos de respuesta baseline para los endpoints más lentos

### 4. Actualización final del roadmap

Marcar el roadmap como "Refactor estructural completado" con fecha, versión y resumen
de lo que se cambió en cada fase.

## Validation

```bash
# Solo calidad (no hay código de producción cambiado)
cd core
docker compose exec backend ruff check .
docker compose exec backend python manage.py test accounting accounts budget memberships net_worth core
```

Verificación manual:
- Los dos documentos nuevos existen y son legibles
- El backlog tiene ≥ 5 tareas concretas y publicables
- El roadmap tiene la sección de cierre

## Required Documentation Updates

- [ ] `core/docs/roadmap/backend-refactor-roadmap.md` — sección de cierre + backlog
- [ ] `core/docs/project-status.md` — mover backend refactor de ⏸ a ✅
- [ ] `core/docs/architecture/backend-patterns.md` — creado
- [ ] `core/docs/standards/backend-pr-checklist.md` — creado

## Risks

1. **Documentación que se desactualiza**: el patrón backend vigente puede cambiar. Añadir nota en el fichero indicando que debe actualizarse cuando cambie la arquitectura.

## Completion Criteria

- [ ] `core/docs/standards/backend-pr-checklist.md` existe y tiene los 4 bloques
- [ ] `core/docs/architecture/backend-patterns.md` existe con las 4 capas documentadas
- [ ] `backend-refactor-roadmap.md` tiene sección de backlog y cierre formal
- [ ] `core/docs/project-status.md` actualizado: "Backend refactor" → ✅
- [ ] `python manage.py test ...` pasa
- [ ] Spec movida a `terminados/`
- [ ] Commit: `docs(core): add backend patterns guide and PR checklist`
