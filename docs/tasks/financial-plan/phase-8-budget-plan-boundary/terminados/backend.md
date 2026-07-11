# Financial Plan — Fase 8: Frontera presupuesto ↔ plan (Core backend)

## Title
Formalizar los dos niveles de presupuesto: partidas recurrentes (entrada manual) y partidas de plan (generadas y gobernadas por Mi Plan, de solo lectura fuera de él).

## Context

Decisión de producto (2026-07-11): **el presupuesto tiene dos niveles**.

1. **Recurrente** — lo que el usuario gasta de forma estable (alimentación, transporte, ocio…). Entrada manual legítima en `/presupuesto`.
2. **Puntual / compromisos** — lo que nace de una decisión simulada en Mi Plan (compra de coche, segunda vivienda, excedencia…). **Solo debe entrar desde Mi Plan.** Si el usuario mete estas partidas a mano, Mi Plan no puede interpretarlas ni mantener su ciclo de vida.

El modelo ya soporta la distinción a medias (hallazgos **A-7** y **A-8** del informe `docs/tasks/financial-plan/browser-audit-2026-07-11.md`):

- las líneas creadas al incorporar un escenario llevan `event_group = "plan_event:<scenario_id>"` (`plan/services_scenarios.py:319,342`) — el linaje existe;
- pero **nada las protege**: se editan y se borran desde `/presupuesto` como cualquier otra partida, y el `PlanEvent` no se entera (el motor sigue aplicando los deltas de su `planned_impact_json` aunque el presupuesto ya no los refleje);
- peor: `event_group` es un **campo de texto libre** en el formulario de partida, así que un usuario puede escribir `plan_event:7` a mano y falsificar el linaje.

Esta fase pone la frontera en el backend. La parte visible es `phase-8-budget-plan-boundary/frontend.md` (repo raíz). La baja de un evento (retirar sus líneas) es la fase 6, ya planificada: esta fase es su condición previa, porque sin protección el `event_group` no es una fuente de verdad fiable.

## Area
`backend`

## Stack
`core`

## Scope

### In scope

1. **`event_group` gestionado deja de ser escribible por el usuario.**
   - Reservar el prefijo `plan_event:` : `BudgetAnnualExpenseSerializer` / `BudgetAnnualIncomeSerializer` rechazan (`validation_error`) cualquier `event_group` que empiece por `plan_event:` si la petición **no** viene del servicio de incorporación de escenarios.
   - Alternativa preferible si encaja con el modelo: campo derivado `is_plan_managed` (propiedad o campo persistido) que el serializer expone como **read-only**, en lugar de hacer depender la semántica de un prefijo de texto. Evaluar en la diagnosis y elegir una; documentar la decisión.
2. **Partidas gestionadas: solo lectura en la API de presupuesto.**
   - `PATCH`/`PUT`/`DELETE` sobre una partida con linaje de plan → `403` con el contrato canónico de errores (`{code, message, details}`), con un `code` propio (p. ej. `plan_managed_entry`) y un mensaje accionable que apunte a Mi Plan.
   - Excepción a decidir en la diagnosis: si se quiere permitir editar el **importe** de una línea gestionada del año en curso (ajuste fino sin romper el linaje), hacerlo explícito; por defecto, **no**.
3. **Exponer el linaje en la API.** Los serializers de partidas anuales devuelven, además de `event_group`, los campos que la UI necesita para explicar la partida sin adivinar: `is_plan_managed`, `plan_event_id`, `plan_event_name`.
4. **Endpoint de trazabilidad inversa.** `GET /api/plan/events/{id}/budget-lines/` → líneas de presupuesto (ingreso y gasto, con año fiscal, importe y perfil) generadas por ese acontecimiento. Lo consume el detalle de escenario (A-11) y lo necesitará la fase 6 para la baja.
5. **Saneado de datos existentes.** Comando de gestión o migración de datos que detecte líneas con `event_group` con prefijo `plan_event:` **sin** `PlanEvent` correspondiente (falsificadas o huérfanas tras un borrado) y las reporte; decidir si se limpian o solo se listan.
6. **Tests.** Rechazo de escritura manual del prefijo reservado; 403 al editar/borrar una línea gestionada; el servicio de incorporación sí puede crearlas; `budget-lines` devuelve exactamente las líneas del evento; aislamiento entre usuarios.

### Out of scope
- Retirar/recortar líneas al cerrar un evento (**fase 6**).
- Cambiar la taxonomía `time_profile`/`cashflow_role` (**fase 7**).
- Simplificar el formulario de partida manual (frontend de esta fase).

## Plan
1. **Diagnosis** — Revisar `budget/serializers.py` y `budget/views.py` (permisos actuales de partidas anuales), `plan/services_scenarios.py` (creación con `event_group`) y decidir entre «prefijo reservado» y «campo `is_plan_managed`».
2. **Change implementation** — Linaje read-only → bloqueo de escritura → exposición en serializers → endpoint de trazabilidad → saneado.
3. **Validation** — Comandos abajo.

## Validation

```
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py makemigrations
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py migrate
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test plan budget
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff format --check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend mypy .
```

## Required Documentation Updates
- [x] `core/docs/tasks/financial-plan/spec.md` — los dos niveles de presupuesto como decisión vinculante
- [x] `core/docs/architecture/architecture.md` — linaje `plan_event` y contrato de solo lectura
- [x] `docs/architecture/api-registry.md` — `GET /api/plan/events/{id}/budget-lines/` y nuevos campos de los serializers de partida
- [x] `core/docs/project-status.md` + `docs/project-status.md`
- [x] `docs/tasks/financial-plan/browser-audit-2026-07-11.md` — marcar A-7 (y A-8 en su parte de backend) como resueltos

## Risks
- Bloquear el borrado puede **atrapar** al usuario si tiene líneas gestionadas de un escenario que ya no quiere: la salida debe existir antes de cerrar la fase (descartar/cerrar el evento desde Mi Plan → fase 6). Si la fase 6 aún no está, dejar una válvula de escape documentada.
- Datos reales ya existentes pueden tener `event_group` a mano con formato parecido: el saneado debe **reportar antes que borrar**.
- Un 403 mal comunicado se lee como un bug: el mensaje debe decir qué hacer y dónde.

## Completion Criteria
- [x] All validation commands pass
- [x] All required documentation updates done
- [x] Spec moved to `terminados/`
- [x] Commit created (Conventional Commits)

## Completion note (2026-07-11)

- Se eligió linaje derivado sin migración de modelo: `event_group` persiste `plan_event:<PlanEvent.id>` y la API expone campos de lectura.
- La auditoría reportó ocho líneas legacy con ID de escenario; `--repair-legacy-scenario-ids` las migró de forma determinista y la segunda pasada devolvió cero huérfanas.
- No existe edición parcial de importes: toda partida gestionada queda protegida hasta que la Fase 6 ofrezca su cierre desde Mi Plan.
