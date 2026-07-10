# Financial Plan — Fase 4: Cimientos, cierre mensual y recomendaciones (Core backend)

## Title
Motor de hallazgos y recomendaciones deterministas (port del scoring del guide) e integración del cierre mensual con el plan.

## Context
Cuarta fase del módulo `financial-plan` (ver `../README.md` y `../spec.md` §6.8-6.10). Requiere Fases 1 y 3. Decisión vinculante: **Mi Plan absorbe Estado financiero** — las métricas de cimientos (deuda, flujo de caja, fondo de emergencia, salud patrimonial) se portan del frontend (`frontend/src/domains/guide/phaseDiagnostics.ts`, referencia de fórmulas) al backend, que pasa a ser la única fuente de diagnóstico. La retirada de la ruta antigua es la Fase 5.

## Area
`backend`

## Stack
`core`

## Scope

### In scope
1. Modelos en app `plan` (aditivos): `Finding` (`plan`, `code`, `severity`, `period`, `evidence_json`, `status`) y `Recommendation` (`finding`, `code`, `priority`, `action_json`, `impact_json`, `alternatives_json`, `status`).
2. `plan/services_foundations.py` — métricas de cimientos portadas del guide (usar `phaseDiagnostics.ts` como referencia de cálculo, con tests de paridad sobre fixtures):
   - Deuda: coste medio ponderado, deuda no respaldada (`is_asset_backed=False`), ratio de apalancamiento.
   - Flujo de caja: superávit operativo estructural (presupuesto + ejecución ledger).
   - Fondo de emergencia: liquidez elegible / gasto operativo estructural mensual → cobertura en meses.
   - Salud patrimonial: respaldo de deuda, concentración, liquidez.
   - Aportación mensual planificada (regla de precedencia de la decisión 7 del README).
3. `plan/services_findings.py` — `FindingService` con los códigos MVP (FR-FIND-001): `EMERGENCY_FUND_BELOW_TARGET`, `NEGATIVE_CASH_FLOW`, `HIGH_COST_DEBT`, `RETIREMENT_TARGET_OFF_TRACK`, `SECONDARY_GOAL_UNDERFUNDED`, `PRODUCTIVE_CAPITAL_STAGNANT`, `DATA_INCOMPLETE`. Evitar duplicados por periodo; cerrar hallazgos resueltos.
4. `plan/services_recommendations.py` — `RecommendationService` (FR-REC-001..004): reglas deterministas, texto por plantillas parametrizadas, explicabilidad completa (acción, motivo, datos que la activan, impacto esperado, coste/riesgo, alternativas, regla generadora). El `profile` del plan (`security|balanced|growth`) reordena prioridades, no cálculos.
5. `plan/services_monthly_close.py` — `MonthlyClosePlanService` (FR-CLOSE-003..005):
   - Impacto del cierre en el plan: variación de capital productivo, estado de trayectoria, cambio material de fecha proyectada (con el umbral de suavizado de FR-PROJ-008 — AC-E05-002), estado de objetivos, calidad de datos.
   - Hook en `finalize_monthly_close` (`budget/services_monthly_close.py`): al finalizar, generar snapshot oficial + evaluar findings. Acoplamiento mínimo: `budget` invoca un punto de entrada de `plan` tolerante a ausencia de plan (no-op si el usuario no tiene plan).
   - Máximo 2 hallazgos destacados y 1 acción propuesta por cierre (FR-CLOSE-004/005).
6. API (ownership validado):
   - `GET /api/plan/findings/` · `GET /api/plan/recommendations/`
   - `POST /api/plan/recommendations/{id}/accept/` · `.../dismiss/` · `.../simulate/` (crea `Scenario` borrador preconfigurado desde la recomendación)
   - `GET /api/plan/foundations/` — cimientos para `PlanFoundations` (FR-UI-PLAN-004)
   - `GET /api/budget/monthly-closes/{id}/plan-impact/` (en `budget`, delegando en `plan`)
7. Tests: reglas de diagnóstico y recomendación (evidencia y explicabilidad), paridad de fórmulas portadas vs casos conocidos del guide, hook de cierre (con y sin plan), límites máx. 2 hallazgos / 1 acción, umbral anti-ruido, aislamiento entre usuarios.

### Out of scope
- UI (spec frontend de esta fase). Retirada de `/estado-financiero` (Fase 5).
- Nuevos códigos de hallazgo fuera de FR-FIND-001.
- LLM o texto generativo (solo plantillas).

## Plan
1. **Diagnosis** — Leer `frontend/src/domains/guide/phaseDiagnostics.ts` y `composables.ts` (fórmulas de referencia), `budget/services_monthly_close.py` (punto de hook), `../spec.md` §6.8-6.10.
2. **Change implementation** — Cimientos → findings → recommendations → integración cierre → API.
3. **Validation** — Comandos abajo; suite de `budget` sin regresiones (el hook no puede romper el cierre existente).

## Validation
```
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py makemigrations plan
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py migrate
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py showmigrations plan
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test plan budget
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff check . && docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff format --check . && docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend mypy .
```

## Required Documentation Updates
- [x] `core/docs/architecture/architecture.md` — contrato de findings/recommendations y hook del cierre
- [x] `docs/architecture/api-registry.md` — nuevos endpoints
- [x] `core/docs/project-status.md` y `docs/project-status.md` — estado de la fase

## Risks
- Paridad de fórmulas con el guide: si el port no alcanza paridad razonable, documentar divergencias y posponer la Fase 5 sin bloquear esta.
- El hook en `finalize_monthly_close` toca un flujo crítico validado: debe ser no-op seguro sin plan y no alterar el resultado del cierre; cubrir con tests de regresión de `budget`.

## Completion Criteria
- [x] AC-E05-001..004 cumplidos
- [x] All validation commands pass
- [x] All required documentation updates done
- [x] Spec moved to `terminados/`
- [x] Commit created (Conventional Commits, `feat(plan): ...`)
