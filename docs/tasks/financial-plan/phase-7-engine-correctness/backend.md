# Financial Plan — Fase 7: Correctitud del motor (Core backend)

## Title
Sanear los inputs del motor: ventana de año fiscal en Cimientos y aportaciones, exclusión de ingresos puntuales, corte de la renta laboral y taxonomía de gasto coherente entre proyección y diagnóstico.

## Context

La auditoría en navegador con datos reales (`docs/tasks/financial-plan/browser-audit-2026-07-11.md`, hallazgos **A-1 a A-5**) demuestra que **el diagnóstico que Mi Plan muestra hoy es incorrecto**, no por un error de fórmula sino porque los inputs que llegan al motor están mal acotados:

1. **A-1** — `services_foundations.py:88-93` lee todas las partidas activas del usuario sin filtrar `fiscal_year`. Con datos reales eso produce `committed_surplus = -78.834,58 €` (verificado al céntimo contra la BD y contra el servicio), porque suma compromisos de **2016 a 2031**, incluidos préstamos ya extinguidos. La misma sesión muestra en `/presupuesto` un balance FY2026 de **+44.579,57 €**. De ahí salen contaminados el score de flujo de caja (44/100), el fondo de emergencia (1,5 meses comprometidos, score 14/100), el finding de superávit negativo y la recomendación principal que ve el usuario.
2. **A-2** — `services_projection.py:132-134` mete los ingresos `one_off` (159.304,40 € en 2026) en `annual_income`, y `future_income_for_year()` los proyecta como renta laboral creciente hasta 2065.
3. **A-3** — `employment_income_end_date` se pide en el setup, se guarda y **no se usa**: la renta laboral no se corta nunca.
4. **A-4** — Cimientos solo reconoce `structural_recurrent+operating` y `term_recurrent+temporary_commitment`; el resto desaparece en silencio, incluida una línea que **genera el propio motor** al incorporar un escenario (`term_recurrent+operating`, el año parcial del coche). La proyección, en cambio, filtra solo por `cashflow_role='operating'`: 44.210 € frente a los 41.410 € de cimientos.
5. **A-5** — `ProjectionInputs.annual_operating_expenses` se calcula y no se usa.

Es la fase que debe ir primero: sin ella, cualquier mejora de UX presenta con más claridad un diagnóstico equivocado.

## Area
`backend`

## Stack
`core`

## Scope

### In scope

1. **Ventana temporal canónica.** Introducir un único concepto de «año fiscal activo del plan» y usarlo en todo el motor. Definición propuesta (fijarla en el spec del módulo antes de implementar): el año natural en curso (`date.today().year`), coherente con el «FY activo» que ya usa `/presupuesto`.
   - Helper compartido en `plan/` (p. ej. `plan_fiscal_year(plan)`), reutilizado por cimientos, aportaciones y proyección.
   - `annual_income_entries()` / `annual_expense_entries()` (`services_foundations.py:88-93`) filtran por ese año.
   - `planned_contribution_amount()` (`services_projection.py:515`) filtra las líneas `savings`/`investment` por ese año. Los `InvestmentContributionInterval` no llevan año fiscal: se mantienen como están.
   - `debt_metrics()` y el resto de consumidores de esos helpers heredan el filtro; revisar cada uno.

2. **Ingresos: separar estructural de puntual en la proyección.**
   - `annual_income` del motor excluye `time_profile='one_off'` (misma definición que `structural_income()` en cimientos) y se acota al año fiscal activo.
   - Decidir y documentar qué se hace con los ingresos puntuales: la propuesta es **ignorarlos en la renta recurrente** y, si se quieren reflejar, tratarlos como un aporte único al capital del año correspondiente (equivalente a un `PlanEvent` con `initial_outflow` negativo). Si se opta por ignorarlos en el MVP, dejarlo explícito en la doc y en el drawer de Supuestos.
   - Unificar la definición de ingreso entre `services_projection.py` y `services_foundations.py` en un helper único.

3. **Corte de la renta laboral (A-3).** `future_income_for_year()` deja de sumar `labor_income` a partir del año de `employment_income_end_date` (el mínimo de los adultos activos del plan, o el máximo — decidir y documentar; con dos adultos lo correcto es cortar la renta de cada uno por su propia fecha, lo que exige repartir `annual_income` por adulto o, si no es posible con los datos actuales, aplicar el corte agregado en la fecha más tardía y documentar la limitación).
   - Si el campo está vacío, comportamiento actual (renta indefinida) pero con aviso en calidad de datos.

4. **Taxonomía de gasto coherente (A-4).**
   - Definir en un único sitio la clasificación de gasto que consume el motor (una función `expense_buckets(entries)` en lugar de filtros duplicados).
   - Que la clasificación sea **exhaustiva**: toda partida activa del año cae en algún bucket (operativo, compromiso temporal, aportación, compra de activo, impuesto/otros) o queda registrada como «no clasificable» en calidad de datos.
   - Corregir el generador de escenarios (`services_scenarios.py`) para que las líneas que crea usen combinaciones que el diagnóstico reconoce (el año parcial del coche no puede ser `term_recurrent+operating` si ese par no existe para cimientos).
   - Alinear el filtro de gasto de la proyección con el de cimientos.

5. **A-5.** Usar `annual_operating_expenses` (p. ej. como semilla/validación del nivel de vida objetivo) o retirarlo de `ProjectionInputs`.

6. **Calidad de datos.** Añadir factores para los casos que hoy fallan en silencio: partidas del año activo no clasificables, ausencia de `employment_income_end_date`, ingresos puntuales relevantes ignorados.

7. **Tests.** Cubrir con datos de tabla:
   - partidas de años pasados y futuros no contaminan los cimientos del año activo;
   - reproducción del caso real: ingresos 2026 + compromisos 2016-2031 → `committed_surplus` positivo y coherente con el balance del FY;
   - ingreso `one_off` no aparece en la renta proyectada;
   - la renta laboral se corta en `employment_income_end_date`;
   - toda partida activa cae en un bucket (test de exhaustividad sobre el conjunto de combinaciones `time_profile × cashflow_role`);
   - un escenario incorporado genera líneas que los cimientos reconocen (test de ida y vuelta con `services_scenarios`).

### Out of scope
- Cambiar el modelo de datos de `budget` (la fase usa `fiscal_year`, `time_profile` y `cashflow_role` tal como están).
- La frontera de edición presupuesto/plan (fase 8).
- El ciclo de vida de acontecimientos (fase 6).
- UI (fase 9), más allá de exponer los nuevos factores de calidad de datos en la API.

## Plan

1. **Diagnosis** — Reproducir las cifras del informe con los datos reales antes de tocar nada:
   ```
   docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py shell -c "
   from django.contrib.auth import get_user_model
   from plan.models import FinancialPlan
   from plan.services_foundations import FoundationService
   u = get_user_model().objects.get(username='pablesite')
   print(FoundationService().calculate(plan=FinancialPlan.objects.get(user=u))['cash_flow'])
   "
   ```
   Debe salir `committed_surplus: -78834.58`. Ese es el valor que la fase tiene que dejar de producir.
2. **Change implementation** — Helper de año fiscal → cimientos → aportaciones → ingresos de la proyección → corte de renta laboral → taxonomía única de gasto → generador de escenarios → calidad de datos.
3. **Validation** — Comandos abajo + reejecutar el shell de diagnóstico y comprobar que el superávit comprometido pasa a ser coherente con el balance FY2026 de `/presupuesto`.

## Validation

```
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test plan budget
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff format --check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend mypy .
```

Validación funcional obligatoria (no basta con los tests): recargar `/plan` con el usuario real y comprobar que
- el superávit de Cimientos es coherente con el balance del FY activo de `/presupuesto`,
- la cobertura del fondo de emergencia deja de estar deprimida por deudas extinguidas,
- la fecha proyectada cambia (se espera que **empeore**: hoy está inflada por A-2/A-3),
- las recomendaciones que se muestran siguen teniendo sentido con el diagnóstico saneado.

## Required Documentation Updates
- [ ] `core/docs/tasks/financial-plan/spec.md` — ventana de año fiscal, definición de ingreso estructural, corte de renta laboral y taxonomía de gasto como decisiones vinculantes
- [ ] `core/docs/architecture/architecture.md` — contrato de los cimientos y de los inputs del motor
- [ ] `core/docs/project-status.md` + `docs/project-status.md` — estado de la fase
- [ ] `docs/tasks/financial-plan/browser-audit-2026-07-11.md` — marcar A-1..A-5 como resueltos

## Risks
- **La fecha proyectada del usuario empeorará** al retirar los ingresos puntuales y cortar la renta laboral. Es el resultado correcto, pero es un cambio visible y brusco: conviene comunicarlo en el drawer de Supuestos y avisar al usuario antes de dar la fase por cerrada.
- Elegir «año natural en curso» como ventana puede no encajar si en el futuro el FY del presupuesto deja de ser el año natural: por eso la ventana va en **un solo helper**, no replicada.
- El corte de renta laboral con dos adultos y un `annual_income` agregado es una aproximación: documentar la limitación explícitamente en lugar de esconderla.
- Los snapshots ya guardados (`ProjectionSnapshot`) contienen proyecciones calculadas con los inputs viejos: decidir si se invalidan o se conservan como histórico.

## Completion Criteria
- [ ] All validation commands pass
- [ ] Validación funcional en navegador con datos reales ejecutada y anotada
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
