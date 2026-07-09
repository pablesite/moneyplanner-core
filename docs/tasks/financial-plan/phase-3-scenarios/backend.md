# Financial Plan — Fase 3: Laboratorio de escenarios (Core backend)

## Title
Modelos y servicios de escenarios: simulación no contaminante, comparación e incorporación al plan.

## Context
Tercera fase del módulo `financial-plan` (ver `../README.md` y `../spec.md` §6.7). Requiere Fase 1 terminada (motor y snapshots). Un escenario aplica deltas hipotéticos sobre los inputs del plan y se compara con el plan vigente; solo al aceptarse crea un `PlanEvent` y recalcula el plan (PP-006).

## Area
`backend`

## Stack
`core`

## Scope

### In scope
1. Modelos en app `plan` (migraciones aditivas):
   - `Scenario`: `plan`, `name`, `template_type` (`housing|vehicle|studies|renovation|sabbatical|reduced_hours|business|debt_payoff|generic`), `status` (`draft|accepted|discarded`), `created_at`, `accepted_at`.
   - `ScenarioEvent`: `scenario`, `start_date`, `end_date`, `initial_outflow`, `monthly_expense_delta`, `monthly_income_delta`, `monthly_contribution_delta`, `new_asset_value`, `new_asset_type`, `new_debt_principal`, `new_debt_interest_rate`, `new_debt_term_months`, `metadata_json`.
   - `PlanEvent`: `plan`, `source_scenario` (nullable), `name`, `event_type`, `planned_date`, `actual_date`, `status` (`planned|occurred|cancelled`), `planned_impact_json`, `actual_impact_json`.
   - Convertir `ProjectionSnapshot.scenario` en FK real si quedó diferido en Fase 1.
2. `plan/services_scenarios.py` — `ScenarioService`:
   - Crear escenario + eventos (las plantillas solo preconfiguran campos; motor común — FR-SCEN-002).
   - Comparación (FR-SCEN-003): ejecutar `ProjectionService` con inputs del plan + deltas del escenario; devolver plan vigente vs simulado con: fecha proyectada, capital productivo y patrimonio neto en fecha objetivo, patrimonio final, fondo de emergencia, deuda, aportación necesaria. Snapshots de escenario con `is_official=False` (FR-SCEN-005: cero contaminación de plan, presupuesto, patrimonio o snapshots oficiales).
   - Aceptar (FR-SCEN-004): transacción que crea `PlanEvent`, vincula escenario, recalcula plan, genera snapshot oficial y marca `accepted`.
   - Descartar: marca `discarded`, sin efectos.
3. Los `PlanEvent` activos entran como inputs del motor en recálculos posteriores (acontecimientos futuros del plan) y se exponen en la proyección para marcadores (FR-PATR-003: el frontend pinta marcadores; el backend expone eventos con fecha, tipo e impactos previsto/real para tooltips FR-PATR-004).
4. API (ownership validado):
   - `GET/POST /api/plan/scenarios/`, `GET/PATCH /api/plan/scenarios/{id}/`
   - `GET /api/plan/scenarios/{id}/comparison/?scenario=expected|prudent|favorable`
   - `POST /api/plan/scenarios/{id}/accept/` · `POST /api/plan/scenarios/{id}/discard/`
   - `GET /api/plan/events/` (+ `PATCH /api/plan/events/{id}/` para registrar `actual_date`/impacto real)
5. Tests: no contaminación (AC-E04-002), comparación de compra de vehículo (AC-E04-001/003), aceptación transaccional (AC-E04-004), evento en trayectoria (AC-E04-005), aislamiento entre usuarios.

### Out of scope
- UI (spec frontend de esta fase). Findings/recommendations (Fase 4).
- Creación automática de `Asset`/`Liability` reales al aceptar un escenario (el evento es del plan; el alta patrimonial real la hace el usuario cuando ocurre).

## Plan
1. **Diagnosis** — Revisar motor de Fase 1 y contrato de snapshot; leer `../spec.md` §6.7 y §12 E-04.
2. **Change implementation** — Modelos → servicio (deltas sobre inputs, no sobre datos persistidos) → API → tests.
3. **Validation** — Comandos abajo.

## Validation
```
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py makemigrations plan
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py migrate
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py showmigrations plan
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test plan
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff check . && docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff format --check . && docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend mypy .
```

## Required Documentation Updates
- [ ] `core/docs/architecture/architecture.md` — contrato de escenarios y eventos
- [ ] `docs/architecture/api-registry.md` — nuevos endpoints
- [ ] `core/docs/project-status.md` y `docs/project-status.md` — estado de la fase

## Risks
- Fugas de contaminación (snapshots de escenario marcados oficiales por error): cubrir con test específico.
- Aceptación no transaccional podría dejar plan y evento inconsistentes: usar transacción + `select_for_update` (patrón de `finalize_monthly_close`).

## Completion Criteria
- [ ] AC-E04-001..005 cumplidos
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits, `feat(plan): ...`)
