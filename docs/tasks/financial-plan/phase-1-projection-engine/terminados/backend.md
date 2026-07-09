# Financial Plan — Fase 1: Motor de proyección (Core backend, sin UI)

## Title
Crear la app `plan` con el motor de proyección determinista y su API, sin UI.

## Context
Primera fase ejecutable del módulo `financial-plan` (ver `../README.md` y `../spec.md`). La auditoría (Fase 0) está completada: el mapa de correspondencia spec↔código y las decisiones de diseño son vinculantes. Esta fase entrega el motor puro con tests exhaustivos y la API de plan/proyección. Sin UI, sin escenarios, sin recomendaciones (spec §19.D: primer PR = estructura del motor + tipos + tests).

## Area
`backend`

## Stack
`core`

## Scope

### In scope
1. App Django nueva `core/backend/plan/` registrada en `config/settings.py` y `config/urls.py` (`path("api/plan/", include("plan.urls"))`).
2. Modelos (migraciones aditivas y reversibles):
   - `FinancialPlan`: `user` (OneToOne efectivo: unique plan vigente), `household_type` (`single|family`), `target_date`, `target_monthly_income_today_eur`, `projection_end_date`, `preservation_target_eur` (nullable), `preserved_asset_ids` (JSON, nullable), `profile` (`security|balanced|growth`, default `balanced`), `status`, `members` (M2M → `memberships.FamilyMember`), timestamps. Validar máx. 2 adultos.
   - `PlanAssetFunction`: `user`, `asset` (FK `net_worth.Asset`, unique por usuario), `function` (`productive|security|short_term_goal|family_use|unknown`). Override de la inferencia.
   - `AssumptionSet`: `name`, `inflation_rate`, `productive_return_rate`, `non_productive_appreciation_rate`, `income_growth_rate`, `contribution_growth_rate`, `withdrawal_rate`, `default_liability_rate`, `is_default`. **Data migration** con seed global: `prudent`, `expected` (default), `favorable`.
   - `ProjectionSnapshot`: `plan`, `scenario` (nullable, FK se añade en Fase 3; dejar campo nullable como IntegerField o diferir FK), `assumption_set`, `assumption_values` (JSON congelado), `calculated_at`, `input_hash`, `result_json`, `quality_level`, `is_official`.
3. Migración aditiva en `memberships.FamilyMember` (campos opcionales): `birth_date`, `employment_income_end_date`, `pension_start_date`, `estimated_monthly_pension_today_eur`, `other_future_income_today_eur`.
4. `plan/services_classification.py` — `AssetClassificationService`:
   - Inferencia por defecto: `investments/*`, `real_estate/second_home`, `real_estate/rental` → `productive`; `cash/*` → `security`; `real_estate/primary_home`, `vehicle/*`, `furnishings/*` → `family_use`; `other` → `unknown`.
   - Override por `PlanAssetFunction`.
   - Valor neto: restar pasivos asociados vía `Liability.financed_asset` (evitar doble contabilización).
   - `productive_capital = sum(productive_assets_net_value)`; `security_capital` análogo.
5. `plan/services_projection.py` — `ProjectionService` como **funciones puras deterministas** (inputs explícitos, sin I/O dentro del cálculo):
   - Proyección anual (FR-PROJ-001): capital productivo, capital de seguridad, activos no productivos, pasivos (cuadros de amortización desde datos de `Liability`: TAE, plazo, sistema), patrimonio neto, ingresos laborales, pensiones, otros ingresos, gastos, aportaciones, retiradas.
   - Capital objetivo simple (FR-PROJ-002) y **periodo puente** cuando `target_date` < inicio de pensión (FR-PROJ-003): etapa puente cubierta íntegramente por cartera + etapa posterior cubriendo solo el gap restante. Nunca aplicar una única regla del 4 % a todo.
   - Fecha proyectada (FR-PROJ-004): primer año con capital suficiente + sostenibilidad hasta fin de horizonte + respeto del patrimonio preservado si existe.
   - Renta sostenible (FR-PROJ-005) y progreso (FR-PROJ-007, documentar denominador usado).
   - Suavizado (FR-PROJ-008, decisión tomada): aportación **planificada** (precedencia: `InvestmentContributionInterval` + `AnnualExpenseEntry` con `cashflow_role ∈ {savings, investment}`) + umbral mínimo para comunicar cambio de año proyectado.
   - Tres escenarios con el mismo esquema de respuesta (FR-PROJ-009).
   - Euros actuales: gasto objetivo en euros actuales; inflación de hipótesis solo hacia futuro. Conversión multi-divisa de la posición actual con `core.services.convert_currency_detailed` hacia `UserSettings.base_currency`.
   - `input_hash` = hash estable del payload de inputs consolidados + valores de hipótesis; persistir snapshot con hipótesis congeladas (FR-ASSUMP-003).
6. `plan/services_quality.py` — calidad de datos (FR-DATA-001/002): nivel `initial|medium|high|needs_review` con desglose de factores (patrimonio completo, deudas, presupuesto, histórico contable, pensiones, aportaciones, frescura de datos).
7. API DRF (`plan/views.py`, `plan/serializers.py`, `plan/urls.py`), ownership validado en todo:
   - `GET/POST/PATCH /api/plan/` — creación idempotente (si existe plan, `POST` actualiza y devuelve 200; un solo plan vigente por usuario).
   - `POST /api/plan/recalculate/` — recalcula y persiste snapshot oficial.
   - `GET /api/plan/projection/?scenario=prudent|expected|favorable` (default `expected`).
   - `GET /api/plan/history/` — histórico básico de snapshots oficiales.
   - `GET /api/plan/members/`, `POST`, `PATCH /api/plan/members/{id}/` — sobre `FamilyMember` extendido (solo adultos vinculables al plan).
   - `GET/PUT /api/plan/asset-functions/` — clasificación efectiva (inferida + override) y edición de overrides.
   - Contrato de respuesta (spec §16.7): cada cifra con valor, unidad, hipótesis aplicadas, `calculated_at` y `quality_level`.
8. Tests en `plan/tests/`: los 10 casos financieros mínimos de spec §13, determinismo (doble ejecución → mismo `input_hash` y `result_json`), clasificación con overrides y deuda asociada, idempotencia de creación, aislamiento entre usuarios.

### Out of scope
- UI (Fase 2). Escenarios/`PlanEvent` (Fase 3). `Finding`/`Recommendation` y cierre mensual (Fase 4).
- Hipótesis editables por usuario (post-MVP; solo lectura de los 3 sets globales).
- Proyección de tipos de cambio (posición convertida a moneda base a fecha actual).
- Cambios en `net_worth`, `budget` o `accounting` (solo lectura de sus datos).

## Plan
1. **Diagnosis** — Leer `../README.md`, `../spec.md`, `core/docs/architecture/architecture.md` y los servicios a reutilizar: `net_worth/services_summaries.py`, `net_worth/services_timelines.py`, `net_worth/services.py` (`build_inflation_adjuster`), `core/services.py` (FX), `budget/services.py` (taxonomías).
2. **Change implementation** — App + modelos + migraciones (incluida la aditiva de `memberships`); servicios puros; API; seed de `AssumptionSet`.
3. **Validation** — Tests + calidad + migraciones aplicadas y verificadas (comandos abajo).

## Validation
Dentro de Docker (repo raíz):
```
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py makemigrations plan memberships
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py migrate
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py showmigrations plan memberships
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test plan
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test accounting accounts budget memberships net_worth core
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff format --check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend mypy .
```
(Si se trabaja en Core standalone, usar los equivalentes `docker compose -f core/docker-compose.yml exec backend ...`.)
Esperado: todo en verde; suite existente sin regresiones; proyección de plan simple < 1 s (NFR-003, medible en test).

## Required Documentation Updates
- [ ] `core/docs/architecture/architecture.md` — nueva app `plan`, contrato de proyección y regla de precedencia de aportaciones
- [ ] `docs/architecture/api-registry.md` — endpoints `/api/plan/*` consumibles por el SaaS
- [ ] `core/docs/project-status.md` — estado de la fase
- [ ] `docs/project-status.md` — estado de la fase

## Risks
- Complejidad del periodo puente: mitigar con funciones puras pequeñas y los casos §13 como tabla de verdad.
- Migración sobre `memberships.FamilyMember`: campos opcionales con default null, reversible (NFR-005); la suite de memberships debe seguir en verde.
- `ProjectionSnapshot.scenario` se define nullable desde el inicio para no migrar en Fase 3.
- Rendimiento con muchos activos: consolidar inputs en una sola pasada de queries antes de entrar al motor puro.

## Completion Criteria
- [ ] AC-E02-001..005 cumplidos (ver `../spec.md` §12)
- [ ] Los 10 casos financieros de §13 tienen test y pasan
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits, `feat(plan): ...`)
