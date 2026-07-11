# The Arkenstone — Spec-Driven Development Specification

**Status:** v1.1 — validada contra el código el 2026-07-09
**Target:** MVP de la nueva orientación de producto
**Stack actual:** Django 5.2 + Django REST Framework + Vue 3 + Vite + Pinia + PostgreSQL 16
**Audience:** agentes implementadores / desarrolladores del proyecto
**Idioma funcional:** español

> **Nota de validación (2026-07-09).** Esta spec se redactó sin mirar el código y ha sido auditada contra el repo real. Las correcciones y decisiones vinculantes están en `README.md` (misma carpeta): ubicación del motor en Core backend, capability `core.plan`, UI solo en frontend SaaS, absorción de `/estado-financiero`, extensión de `FamilyMember` en lugar de `PlanMember`, precedencia de aportación mensual, inflación histórica con IPC real y rutas en castellano. Donde esta spec contradiga el `README.md`, **gana el `README.md`**. Las anotaciones inline `[Validación]` marcan los puntos afectados. La Fase 0 (auditoría, §12 Épica E-01 y §19) está **completada**: el mapa de correspondencia vive en `README.md`.

---

# 1. Resumen ejecutivo

The Arkenstone deja de ser únicamente una herramienta para registrar patrimonio, presupuesto y contabilidad. Pasa a ser una aplicación de **planificación financiera personal o familiar** que utiliza esos datos para responder:

1. ¿Hacia dónde se dirige mi situación financiera?
2. ¿Cuándo podría dejar de depender del trabajo?
3. ¿Qué patrimonio estoy construyendo y preservando?
4. ¿Cómo afectan mis decisiones vitales a mi futuro?
5. ¿Qué debería hacer a continuación?

El producto se articula alrededor de un único **Plan Financiero**, personal o familiar, observado desde dos dimensiones permanentes:

- **Capacidad financiera futura:** capital productivo acumulado frente al capital necesario para sostener el nivel de vida deseado.
- **Trayectoria patrimonial:** evolución del patrimonio neto total, incluidos activos productivos, liquidez, vivienda habitual, otros bienes y deudas.

La aplicación ya dispone de una base funcional relevante: patrimonio, presupuesto, contabilidad y cierre mensual. La nueva versión añade una capa superior de planificación y decisión llamada **Mi Plan**, reutilizando al máximo los modelos y flujos existentes.

---

# 2. Principios de producto

## PP-001 — Un solo plan

Cada usuario tendrá un único plan financiero vigente. El plan podrá representar a una sola persona, a una pareja o a una unidad familiar consolidada. En el MVP no se modelarán reglas jurídicas o internas complejas de reparto económico.

## PP-002 — Dos dimensiones paralelas

El plan siempre mostrará: (1) la capacidad del capital productivo para financiar la vida futura, y (2) la trayectoria del patrimonio familiar completo. Ninguna de las dos sustituye a la otra.

## PP-003 — El capital objetivo es calculado

El usuario no debe tener que decidir cuánto capital necesita acumular.

El usuario define: una fecha objetivo, un nivel de vida mensual deseado, otros ingresos futuros previstos y, opcionalmente, un patrimonio mínimo a preservar.

Arkenstone calcula: capital productivo necesario, capital productivo actual, fecha proyectada de consecución, aportación requerida, y patrimonio proyectado y preservado.

## PP-004 — Euros actuales

Los objetivos de gasto e ingresos se expresarán por defecto en euros actuales. La inflación se aplicará internamente para las proyecciones nominales.

### Decisiones vinculantes de inputs del motor (Fase 7)

1. El FY activo del plan es el año natural actual (`date.today().year`) y se resuelve en un único helper. Cimientos, renta estructural y aportaciones presupuestadas solo leen partidas activas de ese FY.
2. La renta estructural excluye `time_profile=one_off`. En el MVP los ingresos puntuales no se capitalizan automáticamente: se ignoran en la renta recurrente; un efecto patrimonial futuro debe modelarse explícitamente como `PlanEvent`.
3. La renta laboral agregada se corta tras `employment_income_end_date`. Como las partidas de ingreso actuales no están atribuidas de forma fiable a cada miembro, en hogares con varios adultos se usa la fecha más tardía y se expone la falta de fechas en calidad de datos. Esta aproximación debe sustituirse por renta por adulto cuando exista atribución canónica.
4. La taxonomía de gasto del plan es exhaustiva y se resuelve por `cashflow_role` en un único clasificador: operativo, compromiso temporal, aportación, compra de activo, impuesto/otros o no clasificable. Cimientos y proyección consumen esa misma clasificación.
5. Los snapshots anteriores se conservan como histórico de los cálculos efectuados con inputs antiguos. Todo recálculo posterior genera un snapshot y un hash nuevos.

> **[Validación]** El histórico usa IPC real (`InflationIndex`, INE nacional + CCAA, ya sincronizado por `market_data_sync`); las hipótesis de inflación solo se aplican hacia futuro.

## PP-005 — Incertidumbre explícita

Toda previsión se mostrará como estimación, nunca como certeza. El MVP tendrá tres escenarios: **prudente**, **esperado** y **favorable**. La interfaz destacará el escenario esperado.

## PP-006 — Plan vigente separado de simulaciones

Una decisión hipotética no alterará el plan real hasta que el usuario pulse explícitamente **Incorporar al plan**.

## PP-007 — Motor determinista

Los cálculos, diagnósticos y recomendaciones del MVP no dependerán de un LLM. Se utilizarán fórmulas deterministas, reglas de negocio, plantillas de texto y simulaciones reproducibles.

## PP-008 — Reutilización antes que rediseño

Antes de crear nuevas entidades o campos se debe auditar el modelo actual. No se añadirá una nueva clasificación de activos si la información ya puede inferirse de tipos de cuenta, tipos de activo, etiquetas, titularidad, categorías, objetivos existentes o metadatos actuales.

> **[Validación]** Auditoría hecha. La clasificación funcional se infiere de `Asset.Category/Subcategory`; solo se persiste un override (`PlanAssetFunction`). Ver mapa en `README.md`.

---

# 3. Terminología

- **Plan financiero** — configuración central que define la vida financiera futura deseada y las hipótesis utilizadas para proyectarla.
- **Fecha objetivo** — año o fecha a partir de la cual el trabajo debería dejar de ser económicamente imprescindible para la unidad financiera.
- **Nivel de vida objetivo** — cantidad mensual neta, en euros actuales, que la unidad desea sostener desde la fecha objetivo.
- **Capital productivo** — capital destinado a financiar la vida futura: fondos, ETF, acciones, planes de pensiones, depósitos de inversión, segunda vivienda destinada a alquiler o venta, otros activos monetizables o generadores de renta.
- **Patrimonio neto** — suma de todos los activos menos todos los pasivos. Incluye activos productivos y no productivos.
- **Capital de seguridad** — liquidez o activos reservados para fondo de emergencia, imprevistos, gastos operativos u objetivos próximos. No cuenta automáticamente como capital para financiar la independencia.
- **Acontecimiento vital** — decisión o cambio que afecta al plan: compra de vivienda o coche, estudios, reforma, excedencia, reducción de jornada, negocio, amortización de deuda, otro desembolso o cambio de ingresos/gastos.
- **Escenario** — simulación independiente que compara una decisión hipotética con el plan vigente.
- **Proyección** — resultado de aplicar las hipótesis del plan a los datos actuales y futuros.
- **Cierre mensual** — ritual de revisión que resume lo ocurrido, actualiza el plan y propone una acción para el siguiente periodo.

---

# 4. Alcance del MVP

## Incluido

Un único plan financiero por usuario; unidad personal o familiar consolidada (uno o dos adultos); configuración de fecha objetivo, nivel de vida mensual, otros ingresos futuros y patrimonio mínimo preservado opcional; clasificación o inferencia de capital productivo; cálculo de capital objetivo, fecha proyectada y renta sostenible orientativa; trayectoria patrimonial; escenarios prudente/esperado/favorable; pantalla **Mi Plan**; integración ligera con Patrimonio; simulador genérico de decisiones; incorporación de escenarios al plan; marcadores de decisiones en la evolución patrimonial; cierre mensual conectado al plan; diagnósticos y recomendaciones deterministas; indicador de calidad de los datos.

## Excluido

Bienes gananciales; separación de bienes; reglas de aportación en pareja; compensaciones económicas entre miembros; equidad financiera individual; recomendaciones de productos financieros concretos; trading; bots; fiscalidad avanzada; planificación jurídica de herencias; simulaciones de fallecimiento o separación; Monte Carlo avanzado; integración automática con la Seguridad Social; LLM conversacional; optimización automática de carteras; publicidad y monetización; automatización bancaria.

---

# 5. Flujo principal de usuario

## Journey J-001 — Primera configuración

1. El usuario se registra.
2. Indica si el plan representa solo a una persona o a una pareja/familia.
3. Introduce la edad de cada adulto.
4. Define la fecha o año objetivo.
5. Define el nivel de vida mensual deseado en euros actuales.
6. Introduce otros ingresos futuros previstos.
7. Opcionalmente, define un patrimonio mínimo a preservar.
8. Arkenstone reutiliza el patrimonio existente o solicita datos agregados mínimos.
9. Se genera la primera proyección.
10. Se muestra **Mi Plan**.

## Journey J-002 — Uso habitual

1. El usuario registra o importa movimientos.
2. Revisa presupuesto y patrimonio.
3. Realiza el cierre mensual.
4. Arkenstone actualiza indicadores.
5. Arkenstone identifica una o dos cuestiones relevantes.
6. Arkenstone propone una acción.
7. El usuario acepta, modifica, simula o descarta la propuesta.

## Journey J-003 — Decisión vital

1. El usuario crea una simulación.
2. Define fecha e impacto financiero.
3. Arkenstone compara el escenario con el plan vigente.
4. El usuario modifica variables.
5. El usuario descarta o incorpora el escenario al plan.
6. Si se incorpora: se recalcula el plan y aparece como marcador futuro.
7. Cuando ocurre: se registra como decisión histórica y se compara previsto frente a real.

---

# 6. Requisitos funcionales

# 6.1. Configuración del plan

## FR-PLAN-001 — Crear plan

El sistema debe permitir crear un plan financiero asociado al usuario autenticado.

### Datos mínimos

- `household_type`: `single` | `family`
- `target_date` o `target_year`
- `target_monthly_income_today_eur`
- `projection_end_age` o `projection_end_year`
- `active_assumption_set_id`

### Criterios de aceptación

- El usuario solo puede tener un plan vigente.
- La creación debe ser idempotente: si existe un plan, el flujo debe editarlo y no crear uno nuevo.
- El plan debe poder recalcularse.

## FR-PLAN-002 — Adultos del plan

El MVP debe permitir uno o dos adultos.

### Datos

Nombre o alias; fecha de nacimiento o edad; año previsto de finalización de ingresos laborales; año previsto de inicio de pensión; pensión mensual estimada en euros actuales; otros ingresos recurrentes futuros opcionales.

> **[Validación]** No se crea `PlanMember`: se extiende `FamilyMember` (`memberships`) con estos campos opcionales, y `FinancialPlan` referencia a los adultos participantes vía M2M (máx. 2). Ver decisión 5 del `README.md`.

### Simplificación MVP

Todos los activos, gastos e ingresos se consolidan a nivel de unidad financiera. No se calcula una independencia financiera individual por miembro.

## FR-PLAN-003 — Objetivo de preservación

El usuario podrá configurar opcionalmente: una cantidad mínima de patrimonio neto a preservar y/o activos concretos a preservar. En el MVP, la preservación de activos concretos se limita a una lista de IDs de activos.

## FR-PLAN-004 — Editar objetivo

Al cambiar cualquier dato del objetivo: el plan se recalcula, se genera un nuevo snapshot y se mantiene un histórico básico de cambios.

---

# 6.2. Hipótesis

## FR-ASSUMP-001 — Conjuntos de hipótesis

Tres conjuntos: prudente, esperado, favorable. Cada conjunto define como mínimo: inflación anual; rentabilidad nominal o real del capital productivo; crecimiento anual de aportaciones; crecimiento anual de ingresos laborales; tasa de retirada orientativa; revalorización de activos no productivos; coste o interés de pasivos cuando no exista dato específico.

## FR-ASSUMP-002 — Configuración

La primera entrega usa valores de configuración global gestionados por backend (seed vía data migration). La edición por usuario avanzado queda para una fase posterior.

## FR-ASSUMP-003 — Versionado

Cada snapshot de proyección debe guardar: qué conjunto de hipótesis utilizó, qué valores exactos se utilizaron y la fecha de cálculo.

---

# 6.3. Clasificación de patrimonio

## FR-ASSET-001 — Auditoría previa

> **[Validación]** Completada. Ver mapa de correspondencia en `README.md`.

## FR-ASSET-002 — Clasificación funcional

Cada activo debe poder resolverse a una función conceptual: `productive` | `security` | `short_term_goal` | `family_use` | `unknown`.

### Regla MVP

- Una cuenta o activo tendrá una única función principal. No se divide un mismo saldo entre varias funciones.
- La primera vivienda se clasifica por defecto como `family_use`.
- Una segunda vivienda se clasifica por defecto como `productive`, salvo modificación del usuario.
- El fondo de emergencia será `security`.

> **[Validación]** Mapa de inferencia por defecto sobre la taxonomía existente: `investments/*`, `real_estate/second_home`, `real_estate/rental` → `productive`; `cash/*` → `security`; `real_estate/primary_home`, `vehicle/*`, `furnishings/*` → `family_use`; `other/*` → `unknown`.

## FR-ASSET-003 — Inferencia

La clasificación se infiere de los datos existentes. El override del usuario se persiste en el modelo `PlanAssetFunction` (app `plan`); no se añade ningún campo a `net_worth.Asset`.

## FR-ASSET-004 — Capital productivo

`productive_capital = sum(productive_assets_net_value)`. Para activos con deuda asociada (`Liability.financed_asset`), usar valor neto.

## FR-ASSET-005 — Patrimonio neto

`net_worth = total_assets - total_liabilities`.

> **[Validación]** Ya existe como contrato canónico en `net_worth/services_summaries.py` y el timeline. Reutilizar, no reimplementar.

---

# 6.4. Motor de proyección

## FR-PROJ-001 — Proyección central

El motor debe proyectar, al menos con granularidad anual: capital productivo, capital de seguridad, activos no productivos, pasivos, patrimonio neto, ingresos laborales, pensiones, otros ingresos, gastos, aportaciones y retiradas.

## FR-PROJ-002 — Capital objetivo

Para una fecha posterior al inicio de pensiones:

```
annual_gap = max(0, target_annual_income - stable_future_income)
target_capital = annual_gap / withdrawal_rate
```

Este cálculo se usa como aproximación simple cuando no exista periodo puente.

## FR-PROJ-003 — Retiro anterior a pensión

Si la fecha objetivo es anterior al inicio de pensiones, el motor calcula dos etapas:

1. Periodo puente desde la fecha objetivo hasta el inicio de la pensión.
2. Periodo posterior, en el que la cartera cubre solo la diferencia restante.

No se aplica una única regla del 4 % sobre todos los gastos de por vida.

## FR-PROJ-004 — Fecha proyectada

Primer año en el que: el capital productivo proyectado cubre el capital requerido; el plan es sostenible hasta el final del horizonte; y se respeta, si existe, el patrimonio mínimo a preservar.

## FR-PROJ-005 — Renta sostenible orientativa

`monthly_sustainable_income = productive_capital * withdrawal_rate / 12`

La interfaz debe usar textos como "Equivale aproximadamente a…", "Según las hipótesis seleccionadas…", "No es una renta garantizada."

## FR-PROJ-006 — Trayectoria patrimonial

Serie temporal con: fecha, patrimonio neto, capital productivo, deuda, activos de uso y eventos asociados.

> **[Validación]** El tramo histórico sale de `build_net_worth_timeline` (existente); el motor solo genera el tramo proyectado con el mismo esquema de puntos.

## FR-PROJ-007 — Progreso principal

`progress = min(100, productive_capital / target_capital * 100)`

Cuando el capital objetivo varíe según la etapa temporal, el backend debe documentar qué valor usa como denominador.

## FR-PROJ-008 — Suavizado

Los cambios de proyección derivados del cierre mensual no deben reaccionar de forma excesiva a un único mes.

> **[Validación — decisión tomada]** Estrategia MVP: usar la **aportación planificada** (intervalos de aportación + presupuesto de inversión) en vez de la aportación del último mes, más un **umbral mínimo** para comunicar cambios de año proyectado. La media móvil queda como refinamiento posterior.

## FR-PROJ-009 — Escenarios

Toda proyección debe poder ejecutarse con prudente, esperado y favorable, manteniendo el mismo esquema de respuesta.

---

# 6.5. Pantalla "Mi Plan"

## FR-UI-PLAN-001 — Resumen principal

Fecha objetivo; nivel de vida mensual objetivo; capital productivo actual; capital productivo requerido; porcentaje de progreso; renta sostenible aproximada; fecha proyectada; diferencia entre fecha deseada y proyectada.

## FR-UI-PLAN-002 — Trayectoria patrimonial

Patrimonio neto actual; patrimonio proyectado en la fecha objetivo; patrimonio estimado al final del horizonte; objetivo de preservación si existe; gráfico histórico y proyectado.

## FR-UI-PLAN-003 — Hitos

La barra de progreso podrá mostrar logros: ocio cubierto, alimentación cubierta, gastos esenciales cubiertos, nivel de vida completo cubierto. En el MVP se implementan hitos estándar derivados de categorías agregadas del presupuesto (`consumption_expenses/*`).

## FR-UI-PLAN-004 — Cimientos

Resumen compacto de: flujo de caja, fondo de emergencia, deuda, aportación mensual y calidad de datos.

> **[Validación — decisión tomada]** Los cimientos son el destino del scoring que hoy vive en `frontend/src/domains/guide/` (deuda, flujo de caja, fondo de emergencia, salud patrimonial), portado a backend en la Fase 4. Mi Plan **absorbe** `/estado-financiero` (Fase 5).

## FR-UI-PLAN-005 — Próximos acontecimientos

Lista de acontecimientos incorporados al plan: fecha, tipo, impacto estimado sobre la fecha objetivo e impacto sobre patrimonio preservado.

## FR-UI-PLAN-006 — Siguiente acción

Como máximo una recomendación principal y una secundaria.

---

# 6.6. Integración con Patrimonio

## FR-PATR-001 — Mantener la vista actual

La vista de Patrimonio sigue siendo el módulo especializado en qué tiene el usuario, qué debe, cómo se compone el patrimonio y cómo ha evolucionado.

## FR-PATR-002 — Resumen de función

Patrimonio podrá mostrar: capital productivo, capital de seguridad, patrimonio de uso y deuda.

## FR-PATR-003 — Marcadores

La gráfica de evolución patrimonial debe poder mostrar marcadores de: decisiones pasadas, objetivos futuros incorporados, fecha objetivo, inicio de pensiones, amortización de deuda y otras decisiones relevantes.

## FR-PATR-004 — Tooltip de decisión

Cada marcador muestra: nombre, fecha, impacto previsto, impacto real si ya ocurrió, activo creado, deuda creada, cambio de gasto o ingreso, e impacto sobre la fecha objetivo.

---

# 6.7. Laboratorio de escenarios

## FR-SCEN-001 — Crear escenario

Crear un escenario sin modificar el plan vigente.

### Campos mínimos

Nombre; fecha de inicio; desembolso inicial; cambio de gasto mensual; cambio de ingreso mensual; duración; nueva deuda; nuevo activo; cambio en aportación mensual; notas.

## FR-SCEN-002 — Tipos

Plantillas MVP: vivienda, vehículo, estudios, reforma, excedencia, reducción de jornada, negocio, amortización de deuda, genérico. Las plantillas solo preconfiguran campos; el motor es común.

## FR-SCEN-003 — Comparación

Comparar plan vigente vs escenario simulado. Indicadores mínimos: fecha proyectada; capital productivo en fecha objetivo; patrimonio neto en fecha objetivo; patrimonio final; fondo de emergencia; deuda; aportación necesaria.

## FR-SCEN-004 — Incorporar al plan

Al incorporar un escenario: se crea un acontecimiento activo (`PlanEvent`), se recalcula el plan, el escenario queda vinculado al acontecimiento, se genera un snapshot y se marca como `accepted`.

## FR-SCEN-005 — No contaminación

Los escenarios en borrador o descartados no modifican: plan, presupuesto, patrimonio, recomendaciones ni snapshots oficiales.

---

# 6.8. Cierre mensual

## FR-CLOSE-001 — Resumen

El cierre mensual debe resumir: ingresos, gastos, excedente, ahorro, inversión, variación patrimonial, amortización de deuda y desviaciones presupuestarias.

> **[Validación]** `compute_monthly_close_state` ya construye la mayor parte; la integración con plan añade la capa de impacto, no duplica el resumen.

## FR-CLOSE-002 — Explicación

Identificar las principales causas: categorías con mayor desviación, gastos extraordinarios, variación de valor de activos, cambios de ingresos, cambios de deuda.

## FR-CLOSE-003 — Impacto en el plan

Mostrar: variación de capital productivo, estado de la trayectoria, cambio material de fecha proyectada, estado de objetivos activos y calidad de datos.

## FR-CLOSE-004 — Atención

Destacar como máximo dos hallazgos.

## FR-CLOSE-005 — Acción siguiente

Proponer una acción concreta. El usuario podrá aceptar, modificar, simular, posponer o descartar.

---

# 6.9. Diagnósticos y recomendaciones

## FR-FIND-001 — Hallazgos MVP

- `EMERGENCY_FUND_BELOW_TARGET`
- `NEGATIVE_CASH_FLOW`
- `HIGH_COST_DEBT`
- `RETIREMENT_TARGET_OFF_TRACK`
- `SECONDARY_GOAL_UNDERFUNDED`
- `PRODUCTIVE_CAPITAL_STAGNANT`
- `DATA_INCOMPLETE`

> **[Validación]** Las fórmulas de fondo de emergencia, flujo de caja, deuda cara y salud patrimonial se portan desde `frontend/src/domains/guide/phaseDiagnostics.ts` (referencia de cálculo), no se inventan de cero.

## FR-REC-001 — Recomendaciones MVP

Reconstruir fondo de emergencia; reducir deuda cara; aumentar aportación; ajustar fecha objetivo; ajustar nivel de vida objetivo; reprogramar un objetivo secundario; reducir desembolso de un acontecimiento; completar datos.

## FR-REC-002 — Explicabilidad

Cada recomendación incluye: acción, motivo, datos que la activan, impacto esperado, coste o riesgo, alternativas y regla que la generó.

## FR-REC-003 — Perfil

Tres perfiles: seguridad, equilibrado, crecimiento. El perfil influye en prioridades, no en cálculos contables.

## FR-REC-004 — Plantillas

El texto se genera mediante plantillas parametrizadas. No se requiere LLM.

---

# 6.10. Calidad de datos

## FR-DATA-001 — Estado de precisión

Nivel cualitativo: inicial, media, alta, necesita revisión.

## FR-DATA-002 — Factores

Patrimonio completo; deudas completas; presupuesto existente; histórico contable; pensiones configuradas; aportaciones configuradas; datos actualizados.

## FR-DATA-003 — Mejora guiada

La interfaz debe explicar qué dato falta y qué indicador mejoraría al completarlo.

---

# 7. Modelo de dominio (validado)

> **[Validación]** Modelo conceptual mapeado contra el código. `PlanMember` eliminado (se extiende `FamilyMember`). Todos los modelos nuevos viven en la app `plan` de Core backend. Detalle de campos definitivos en los task specs de cada fase.

- **FinancialPlan** — `user`, `household_type`, `target_date`, `target_monthly_income_today_eur`, `projection_end_date`, `preservation_target_eur`, `preserved_asset_ids`, `profile`, `status`, `members` (M2M → `memberships.FamilyMember`, máx. 2 adultos), timestamps.
- **FamilyMember (extendido, migración aditiva)** — + `birth_date`, `employment_income_end_date`, `pension_start_date`, `estimated_monthly_pension_today_eur`, `other_future_income_today_eur` (todos opcionales).
- **PlanAssetFunction** — `user`, `asset` (FK `net_worth.Asset`, unique), `function` (`productive|security|short_term_goal|family_use|unknown`). Override de la inferencia.
- **AssumptionSet** — `name`, `inflation_rate`, `productive_return_rate`, `non_productive_appreciation_rate`, `income_growth_rate`, `contribution_growth_rate`, `withdrawal_rate`, `default_liability_rate`, `is_default`. Seed global: prudente/esperado/favorable.
- **ProjectionSnapshot** — `plan`, `scenario` (nullable), `assumption_set`, `assumption_values` (JSON congelado), `calculated_at`, `input_hash`, `result_json`, `quality_level`, `is_official`.
- **Scenario** — `plan`, `name`, `template_type`, `status` (`draft|accepted|discarded`), `created_at`, `accepted_at`.
- **ScenarioEvent** — `scenario`, `start_date`, `end_date`, `initial_outflow`, `monthly_expense_delta`, `monthly_income_delta`, `monthly_contribution_delta`, `new_asset_value`, `new_asset_type`, `new_debt_principal`, `new_debt_interest_rate`, `new_debt_term_months`, `metadata_json`.
- **PlanEvent** — `plan`, `source_scenario` (nullable), `name`, `event_type`, `planned_date`, `actual_date`, `status`, `planned_impact_json`, `actual_impact_json`.
- **Finding** — `plan`, `code`, `severity`, `period`, `evidence_json`, `status`.
- **Recommendation** — `finding`, `code`, `priority`, `action_json`, `impact_json`, `alternatives_json`, `status`.

---

# 8. Servicios de backend

- **ProjectionService** — cargar datos consolidados; resolver clasificación; cargar hipótesis; ejecutar proyección; calcular escenarios; persistir snapshots; hash de inputs.
- **AssetClassificationService** — mapear taxonomía actual a funciones conceptuales; aplicar inferencias; permitir override; evitar doble contabilización (valor neto con `financed_asset`).
- **ScenarioService** — crear escenarios; aplicar eventos; comparar con plan vigente; incorporar escenarios.
- **FindingService** — evaluar métricas (port de `phaseDiagnostics.ts`); generar hallazgos; evitar duplicados; cerrar hallazgos resueltos.
- **RecommendationService** — aplicar reglas; calcular impacto; generar alternativas; renderizar plantillas.
- **MonthlyClosePlanService** — enlazar cierre mensual y plan; actualizar métricas; generar snapshots; lanzar diagnósticos.

---

# 9. API (Core backend, `/api/plan/`)

> **[Validación]** Todo en Core backend (`core/backend/config/urls.py`). Nombres definitivos en los task specs.

## Plan

- `GET /api/plan/` · `POST /api/plan/` · `PATCH /api/plan/`
- `POST /api/plan/recalculate/`
- `GET /api/plan/projection/` · `GET /api/plan/projection/?scenario=prudent|expected|favorable`
- `GET /api/plan/history/`

## Members

- `GET /api/plan/members/` · `POST /api/plan/members/` · `PATCH /api/plan/members/{id}/`

## Scenarios

- `GET /api/plan/scenarios/` · `POST /api/plan/scenarios/`
- `GET /api/plan/scenarios/{id}/comparison/`
- `POST /api/plan/scenarios/{id}/accept/` · `POST /api/plan/scenarios/{id}/discard/`

## Findings y recommendations

- `GET /api/plan/findings/` · `GET /api/plan/recommendations/`
- `POST /api/plan/recommendations/{id}/accept/` · `.../dismiss/` · `.../simulate/`

## Monthly close

- `GET /api/budget/monthly-closes/{id}/plan-impact/`
- `POST /api/budget/monthly-closes/{id}/finalize-plan-update/`

---

# 10. Frontend (SaaS, `frontend/`)

> **[Validación]** Solo frontend SaaS en el MVP. `core/frontend/` no se toca.

## Rutas

`/plan` · `/plan/setup` · `/plan/escenarios` · `/plan/escenarios/:id` · impacto del cierre integrado en `/cierre-mensual`.

## Store Pinia — `usePlanStore`

Estado: plan, miembros, proyección esperada, proyecciones prudente/favorable, eventos, hallazgos, recomendaciones, calidad de datos, loading/error. Acciones: load/save plan, recalculate, load projections, accept scenario, dismiss recommendation.

## Componentes principales

`PlanHero`, `ProductiveCapitalProgress`, `ProjectedDateCard`, `NetWorthTrajectoryChart`, `PlanFoundations`, `PlanEventsTimeline`, `PlanRecommendationCard`, `DataQualityCard`, `ScenarioComparison`, `ScenarioForm`, `ProjectionAssumptionsDrawer`.

---

# 11. Requisitos no funcionales

- **NFR-001 Reproducibilidad** — mismos inputs e hipótesis → mismos resultados.
- **NFR-002 Trazabilidad** — cada cifra rastreable hasta inputs, hipótesis, fórmula y snapshot.
- **NFR-003 Rendimiento** — proyección anual de un plan simple < 1 s en backend.
- **NFR-004 Seguridad** — ownership validado en todos los endpoints; sin datos a LLM externos; registrar cambios sensibles.
- **NFR-005 Migraciones seguras** — no eliminar campos; no cambiar semántica; migraciones reversibles; probar con fixtures representativos.
- **NFR-006 Feature flag** — Mi Plan activable mediante capability `core.plan` (sistema de capabilities existente).
- **NFR-007 Explicabilidad** — evitar afirmaciones categóricas: "estimado", "aproximadamente", "según las hipótesis", "escenario esperado".
- **NFR-008 Responsive** — desktop y móvil.
- **NFR-009 Accesibilidad** — contraste; no depender solo del color; texto equivalente en gráficos; navegación por teclado en formularios.

---

# 12. Criterios de aceptación por épica

## Épica E-01 — Auditoría del sistema actual — ✅ COMPLETADA (2026-07-09)

Mapa de modelos y correspondencia en `README.md`. Ninguna migración creada antes de aprobar el mapa.

## Épica E-02 — Motor de proyección

- AC-E02-001 — Plan simple sin pensión: capital objetivo, fecha proyectada y trayectoria.
- AC-E02-002 — Retiro antes de pensión: periodo puente y posterior separados.
- AC-E02-003 — Se generan tres escenarios.
- AC-E02-004 — El motor es determinista.
- AC-E02-005 — Cada resultado incluye las hipótesis utilizadas.

## Épica E-03 — Mi Plan

- AC-E03-001 — Un usuario con datos existentes abre `/plan` y ve una primera proyección.
- AC-E03-002 — La barra usa capital productivo, no patrimonio neto total.
- AC-E03-003 — La trayectoria incluye histórico y proyección.
- AC-E03-004 — La pantalla distingue capacidad financiera futura y patrimonio familiar.
- AC-E03-005 — La pantalla muestra calidad de datos.

## Épica E-04 — Escenarios

- AC-E04-001 — Crear un escenario de compra de vehículo.
- AC-E04-002 — El escenario no modifica el plan antes de aceptarse.
- AC-E04-003 — La comparación muestra cambio de fecha y patrimonio.
- AC-E04-004 — Al aceptar, se crea un evento y se recalcula el plan.
- AC-E04-005 — El evento aparece en la trayectoria.

## Épica E-05 — Cierre mensual

- AC-E05-001 — El cierre muestra impacto sobre capital productivo y patrimonio.
- AC-E05-002 — No comunica cambios de días o semanas irrelevantes.
- AC-E05-003 — Genera como máximo dos hallazgos principales.
- AC-E05-004 — Genera una recomendación accionable.

---

# 13. Estrategia de pruebas

## Unitarias

Fórmulas de capital objetivo; periodo puente; conversión euros actuales/nominales; clasificación; proyección de deuda; cálculo de patrimonio; reglas de diagnóstico; recomendaciones.

## Integración

Patrimonio actual → ProjectionService; escenario → comparación; aceptación → PlanEvent; cierre mensual → snapshot; cambios de plan → histórico.

## Frontend

Render de estados incompletos; loading y error; comparación de escenarios; accesibilidad básica; responsive.

## Regresión

Patrimonio, presupuesto, contabilidad y cierre mensual existentes siguen funcionando sin pérdida de datos.

## Casos de prueba financieros mínimos

1. Persona sin activos.
2. Persona con inversiones y sin deuda.
3. Persona con vivienda habitual e hipoteca.
4. Pareja con dos pensiones en fechas diferentes.
5. Retiro antes de pensión.
6. Fondo de emergencia alto.
7. Compra de coche.
8. Compra de segunda vivienda.
9. Excedencia de 12 meses.
10. Objetivo de preservación incompatible.

---

# 14. Plan de implementación (validado)

> **[Validación]** Fases renumeradas tras completar la auditoría. El desglose ejecutable vive en los task specs (`README.md` → tabla de fases). Correspondencia con la spec original: Fase 0 completada; Fase 1 = motor; Fase 2 = configuración y Mi Plan; Fase 3 = escenarios; Fase 4 = cierre y recomendaciones (incluye port de cimientos); Fase 5 = absorción de Estado financiero (sustituye al "refinamiento" original, que queda post-MVP).

---

# 15. Backlog por prioridad

- **P0** — App `plan`; FinancialPlan; FamilyMember extendido; AssumptionSet; ProjectionService; snapshots; capital productivo; patrimonio neto; capital objetivo; periodo puente; fecha proyectada; API; Mi Plan; gráfico de trayectoria; calidad de datos. *(Fases 1-2)*
- **P1** — Scenario; ScenarioEvent; comparación; incorporación; PlanEvent; marcadores. *(Fase 3)*
- **P2** — Finding; Recommendation; reglas MVP; integración con cierre; absorción de Estado financiero. *(Fases 4-5)*
- **P3 (post-MVP)** — Hipótesis editables; hitos personalizados; simuladores especializados; reparto de pareja; monetización; LLM.

---

# 16. Instrucciones específicas para el agente implementador

1. La auditoría (Fase 0) ya está hecha: **no reauditar**, leer `README.md` y este documento.
2. Implementar primero el motor como funciones o servicios puros. Añadir tests antes de conectar la UI.
3. No introducir LLM ni librerías financieras complejas sin justificar.
4. No cambiar los módulos actuales de forma destructiva; migraciones solo aditivas.
5. Gatear la nueva experiencia con la capability `core.plan`.
6. Mantener el cálculo en backend; no duplicar lógica financiera en Vue.
7. Cada endpoint debe devolver: valor, unidad, hipótesis, fecha de cálculo y nivel de calidad.
8. Toda recomendación debe indicar la regla que la generó.
9. Ante ambigüedad entre esta spec y el código actual: documentar la decisión y detener esa parte hasta resolverla con el usuario.
10. Seguir el flujo de trabajo del repo: skill `validate` antes de cada commit, migraciones aplicadas y verificadas, Conventional Commits, docs canónicos actualizados al cerrar cada fase.

---

# 17. Definition of Done del MVP

El MVP se considera terminado cuando un usuario puede:

1. Configurar su fecha objetivo y nivel de vida deseado.
2. Reutilizar el patrimonio ya registrado.
3. Ver cuánto capital productivo tiene.
4. Ver cuánto capital necesita.
5. Ver su porcentaje de progreso.
6. Ver su fecha deseada y fecha proyectada.
7. Ver la trayectoria de su patrimonio neto.
8. Ver cuánto patrimonio podría preservar.
9. Crear una simulación.
10. Compararla con su plan.
11. Incorporarla al plan.
12. Verla como marcador en la trayectoria.
13. Completar un cierre mensual.
14. Recibir una recomendación determinista.
15. Entender las hipótesis de los resultados.

---

# 18. Preguntas post-auditoría — RESUELTAS

> **[Validación]** Las 15 preguntas de la spec original quedan respondidas por la auditoría. Resumen: inversiones = `Asset(category=investments)` + `InvestmentAssetEvent` + `InvestmentContributionInterval`; histórico de valor = `AssetValuation`/`LiabilityValuation` + timeline; préstamos↔activos = `Liability.financed_asset`; no existe entidad de objetivo (se crea `FinancialPlan`); fondo de emergencia = heurística frontend a portar; aportación mensual = 3 fuentes con precedencia definida; cuenta/activo/posición = `LedgerAccount` (contable) vs `Asset` (patrimonial) enlazados por FK; titularidad = `Ownership`/`OwnershipSplit`/`OwnershipLink`; históricos disponibles = valoraciones + checkins + timeline mensual; cierre mensual usa `compute_monthly_close_state`; cálculos backend = summaries/timelines/monthly-close; cálculos duplicados en frontend = scoring del guide (~2.500 líneas, se absorbe); valores futuros = solo compromisos de deuda/aportación (el motor de proyección es nuevo); permisos = JWT + ownership por usuario en Core, RBAC en SaaS; sin migración se puede implementar solo la inferencia de clasificación (todo lo demás requiere modelos nuevos aditivos).

---

# 19. Frase de producto

> **The Arkenstone no solo te dice dónde está tu dinero. Te ayuda a entender hacia dónde vas y cómo cada decisión cambia tu futuro.**
