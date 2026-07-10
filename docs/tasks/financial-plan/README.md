# Módulo `financial-plan` — Mi Plan (The Arkenstone)

Índice canónico del módulo de planificación financiera. Este documento es el entregable de la **Fase 0 / Épica E-01** de la spec: auditoría del sistema actual y mapa de correspondencia spec ↔ código. Ninguna migración debe crearse sin que este mapa esté aprobado (AC-E01-003) — cumplido el 2026-07-09.

**Spec canónica:** `spec.md` (en esta carpeta), validada contra el código el 2026-07-09.

---

## Qué es

Capa superior de planificación y decisión sobre los módulos existentes (patrimonio, presupuesto, contabilidad, cierre mensual). Un único **Plan Financiero** por usuario con dos dimensiones permanentes:

1. **Capacidad financiera futura** — capital productivo acumulado vs capital necesario para sostener el nivel de vida deseado.
2. **Trayectoria patrimonial** — evolución del patrimonio neto completo (histórico + proyección).

Motor determinista (sin LLM), tres escenarios de hipótesis (prudente / esperado / favorable), laboratorio de simulaciones no contaminantes, e integración con el cierre mensual.

## Decisiones de diseño acordadas (2026-07-09)

| # | Decisión | Detalle |
|---|----------|---------|
| 1 | **Ubicación del motor** | App Django nueva `plan` en `core/backend/` (OSS). Los datos de dominio viven en la BD de Core; la regla de boundaries prohíbe duplicar dominio en el backend SaaS. API bajo `/api/plan/`. |
| 2 | **Packaging** | Gateado por capability `core.plan` en `docs/architecture/capabilities-matrix.md`. El packaging comercial (Community vs premium) se decide después sin tocar código. |
| 3 | **UI** | Solo en frontend SaaS (`frontend/src/domains/plan/`). `core/frontend/` no se toca en el MVP. |
| 4 | **Estado financiero** | **Mi Plan absorbe `/estado-financiero`**: sus diagnósticos (deuda, flujo de caja, fondo de emergencia, salud patrimonial) se portan al backend como "Cimientos" del plan (Fase 4) y la ruta antigua se retira con redirect (Fase 5). La fase 5 eliminada del guide ("Independencia financiera") es exactamente lo que Mi Plan implementa. |
| 5 | **Miembros del plan** | Se extiende `FamilyMember` (migración aditiva en `memberships`) con campos opcionales: `birth_date`, `employment_income_end_date`, `pension_start_date`, `estimated_monthly_pension_today_eur`, `other_future_income_today_eur`. `FinancialPlan` selecciona adultos participantes vía M2M (máx. 2 en MVP). No se crea `PlanMember`. |
| 6 | **Clasificación funcional de activos** | Inferencia desde taxonomía existente + override persistido en modelo `PlanAssetFunction` (app `plan`, FK a `Asset`). No se modifica `net_worth`. |
| 7 | **Aportación mensual (precedencia)** | Planificada = `InvestmentContributionInterval` + líneas de presupuesto con `cashflow_role ∈ {savings, investment}`. Real = ledger (`quick_entry_kind=investment`) / `InvestmentAssetEvent`. El suavizado (FR-PROJ-008) usa la aportación planificada, no la del último mes. |
| 8 | **Inflación** | Histórico con IPC real (`InflationIndex`, INE nacional + CCAA); hipótesis de inflación solo hacia futuro (`AssumptionSet`). |
| 9 | **Multi-divisa** | El motor proyecta en moneda base del usuario (`UserSettings.base_currency`) convirtiendo la posición actual con el FX existente. No se proyectan tipos de cambio. |
| 10 | **Rutas frontend** | `/plan`, `/plan/setup`, `/plan/escenarios`, `/plan/escenarios/:id` (castellano, coherente con `/patrimonio`, `/cierre-mensual`). |
| 11 | **Casos financieros mínimos en Fase 1** | Los casos "compra de coche", "compra de segunda vivienda" y "excedencia" se cubren como datos base ya incorporados al plan. La simulación hipotética de esos eventos queda para Fase 3 (`Scenario`/`ScenarioEvent`). |

## Mapa de correspondencia spec ↔ código

| Concepto spec | Código actual | Reutilizable | Cambio requerido |
|---|---|---|---|
| Patrimonio neto | `net_worth`: `Asset`/`Liability` + `services_summaries.py` + `build_net_worth_timeline` (`services_timelines.py`) | ✅ Sí | Ninguno. Timeline mensual histórico con comparativas ya existe. |
| Capital productivo | Taxonomía `Asset.Category/Subcategory` (`net_worth/models.py`) | ✅ Inferible | `AssetClassificationService`: `investments/*`, `second_home`, `rental` → `productive`; `cash/*` → `security`; `primary_home`, `vehicle`, `furnishings` → `family_use`. Override en `PlanAssetFunction`. Valor neto: restar `financing_liabilities` (FK `Liability.financed_asset` ya existe). |
| Fondo de emergencia | Heurística SOLO frontend (`frontend/src/domains/guide/phaseDiagnostics.ts`: liquidez elegible / gasto operativo estructural mensual) + subcategoría presupuesto `savings_allocation/emergency_fund` | ⚠️ Parcial | Portar la heurística de cobertura en meses al backend (Fase 4). |
| Aportación mensual | 3 fuentes: `InvestmentContributionInterval`, `AnnualExpenseEntry` con `cashflow_role ∈ {savings, investment}`, eventos reales (`InvestmentAssetEvent`, ledger) | ⚠️ Sí, con regla | Precedencia definida en decisión 7 (la spec no la definía). |
| Deuda / pasivos | `Liability`: TAE, plazo, sistemas francés/alemán/americano, `payment_frequency`, `cancellation_forecast_enabled`, `principal_amount` | ✅ Sí | Ninguno en modelo. El motor proyecta cuadros de amortización con lo existente. |
| Cierre mensual | `MonthlyClose` (`budget/models.py`) `draft→finalized→locked` + `compute_monthly_close_state` (`budget/services_monthly_close.py`) | ✅ Sí | Endpoint plan-impact + hook en finalize (Fase 4). |
| Ingresos/gastos futuros | `AnnualIncomeEntry`/`AnnualExpenseEntry` con `time_profile`, `cashflow_role`, taxonomía con `retirement_pension` | ✅ Sí | El gasto operativo estructural ≈ nivel de vida actual (semilla del objetivo). |
| Inflación / euros actuales | `InflationIndex` (worker `market_data_sync`), `UserSettings.inflation_region`, `build_inflation_adjuster` (`net_worth/services.py`) | ✅ Mejor que la spec | Ver decisión 8. FX: `convert_currency_detailed`. |
| Adultos del plan | `FamilyMember` (`memberships/models.py`) solo nombre + rol adult/child | ⚠️ Parcial | Migración aditiva (decisión 5). |
| Titularidad | `Ownership`/`OwnershipSplit`/`OwnershipLink` | ✅ Existe | NO se usa en cálculos MVP (unidad consolidada). |
| FinancialPlan, AssumptionSet, ProjectionSnapshot, Scenario, ScenarioEvent, PlanEvent, Finding, Recommendation | No existen | ❌ Nuevos | Modelos nuevos en app `plan`, todos aditivos. |
| Motor de proyección | Solo timelines históricos | ❌ Nuevo | `ProjectionService` determinista, granularidad anual, 3 escenarios, periodo puente. |
| Casos tipo coche/segunda vivienda/excedencia | Activos, deudas, presupuesto e ingresos actuales | ✅ Como estado base | Fase 1 no crea escenarios: esos casos se prueban como datos ya incorporados al plan. Fase 3 añadirá comparación hipotética no contaminante. |
| Feature flag | Capabilities estáticas SaaS (`frontend/src/domains/capabilities/index.ts`, helpers `canUse...`) | ✅ Sí | Añadir `core.plan` + `canUsePlan()`. |
| Diagnósticos/recomendaciones | Scoring 4 fases 100% en frontend (`frontend/src/domains/guide/`, ~2.500 líneas TS) | ⚠️ Lógica portable | Port a backend en Fase 4; retirada de `/estado-financiero` en Fase 5. |

## Fases y task specs

| Fase | Prioridad | Alcance | Spec |
|------|-----------|---------|------|
| 1 — Motor de proyección | P0 ✅ | Core backend, sin UI. App `plan`, modelos base, `AssetClassificationService`, `ProjectionService`, calidad de datos, API de plan/proyección, tests financieros. | `phase-1-projection-engine/terminados/backend.md` |
| 2 — Mi Plan UI + onboarding | P0 ✅ | Frontend SaaS. Dominio `plan/`, capability `core.plan`, `/plan` + `/plan/setup`, hero, progreso, trayectoria, calidad de datos. | `../../../../docs/tasks/financial-plan/phase-2-mi-plan-ui/terminados/frontend.md` (repo raíz) |
| 3 — Laboratorio de escenarios | P1 🔄 | Backend Core completado; frontend SaaS pendiente. `Scenario`/`ScenarioEvent`/`PlanEvent`, comparación, incorporación, marcadores en Patrimonio. | `phase-3-scenarios/terminados/backend.md` + `../../../../docs/tasks/financial-plan/phase-3-scenarios/frontend.md` |
| 4 — Cimientos, cierre y recomendaciones | P2 | Backend + frontend. `Finding`/`Recommendation`, port del scoring del guide, plan-impact del cierre mensual. | `phase-4-findings-close/backend.md` + `../../../../docs/tasks/financial-plan/phase-4-findings-close/frontend.md` |
| 5 — Absorción de Estado financiero | P2 | Frontend SaaS + docs. Redirect `/estado-financiero` → `/plan`, retirada del dominio `guide/`, capability. | `../../../../docs/tasks/financial-plan/phase-5-absorb-financial-state/frontend.md` |

Regla de ejecución: las fases son secuenciales. El primer PR de código es la Fase 1 (motor + tipos + tests, sin UI, sin reglas de recomendación — spec §19.D).

## Riesgos

1. El motor con periodo puente (FR-PROJ-003) es la pieza de mayor complejidad algorítmica → Fase 1 aislada con tests exhaustivos.
2. La absorción de Estado financiero (Fase 5) depende de que el port de fórmulas (Fase 4) alcance paridad razonable con `phaseDiagnostics.ts`; si no, la retirada se pospone sin bloquear el resto.
3. Migración aditiva sobre `FamilyMember`: campos opcionales, reversible, sin cambiar semántica actual (NFR-005).
