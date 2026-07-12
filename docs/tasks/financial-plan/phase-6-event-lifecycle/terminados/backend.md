# Financial Plan — Fase 6: Ciclo de vida de acontecimientos (Core backend)

## Title
Baja de acontecimientos incorporados: retirar del presupuesto y de la proyección los efectos recurrentes de un evento cuando el activo deja de existir (venta, desguace, cancelación).

## Context
Al incorporar un escenario (Fase 3) se crean líneas de presupuesto con `event_group='plan_event:<scenario_id>'` y el `PlanEvent` entra como input del motor. Decisión de producto (2026-07-11): los gastos recurrentes sin fecha fin son **indefinidos** mientras el activo exista (p. ej. el coste de uso de un coche sigue tras amortizar el préstamo; ver `fix(plan)` ff22948). La contrapartida pendiente es el momento de la baja: cuando el usuario vende o desguaza el coche debe poder cerrarlo, retirando desde esa fecha los gastos recurrentes del presupuesto y los deltas del evento en la proyección. Hoy `PlanEvent` ya tiene `status (planned|occurred|cancelled)`, `actual_date` y `PATCH /api/plan/events/{id}/`, pero ningún flujo retira las líneas de presupuesto ni acota los efectos del evento en el motor.

## Area
`backend`

## Stack
`core`

## Scope

### In scope
1. Modelo (migración aditiva): `PlanEvent.effective_end_date` (nullable). Semántica: fecha desde la que el evento deja de producir efectos (venta/desguace/cancelación del activo). No confundir con `actual_date` (cuándo ocurrió el evento) ni con `status=cancelled` (el evento nunca llegó a ocurrir).
2. `plan/services_events.py` (o extensión de `services_scenarios.py`) — `close_plan_event(event, effective_end_date, disposal_note)`:
   - Validaciones: evento propio del usuario, no cerrado ya (`effective_end_date` vacío), fecha efectiva ≥ `planned_date`.
   - Retirada de líneas de presupuesto del `event_group` asociado a partir de la fecha efectiva:
     - Línea `structural_recurrent` → convertir a `term_recurrent` con `term_end_year/month` = fecha efectiva; si la fecha efectiva es anterior al `fiscal_year` de la línea, eliminarla.
     - Línea `term_recurrent` cuyo término acaba después de la fecha → recortar `term_end_*` (y prorratear `amount_annual` si el año efectivo queda parcial); líneas de años posteriores → eliminar.
     - Años ya transcurridos o líneas `one_off` pasadas: **no se tocan** (el histórico presupuestado se conserva).
   - Registrar en `actual_impact_json` el detalle de líneas modificadas/eliminadas (trazabilidad) y `effective_end_date`.
   - Recalcular proyección oficial.
3. Motor (`services_projection.py`): los deltas recurrentes de un `PlanEvent` con `effective_end_date` dejan de aplicarse a partir de ese año (activo nuevo: decidir si se retira su valor residual del año efectivo en adelante; documentar la decisión en el spec del motor).
4. API: `POST /api/plan/events/{id}/close/` con body `{effective_date, note?}` → evento actualizado + proyección oficial. Ownership validado, idempotencia (segundo close → 400).
5. Tests: retirada correcta de estructurales y term (recorte, prorrateo, eliminación de años posteriores), histórico intacto, motor sin deltas tras la fecha, idempotencia, aislamiento entre usuarios.

### Out of scope
- Tocar activos/pasivos reales de Patrimonio (la baja patrimonial real la hace el usuario en `/patrimonio`, como en Fase 3).
- Generar la línea de ingreso puntual por el valor de venta (extensión futura; anotar en roadmap si se quiere).
- Reabrir un evento cerrado (si hace falta, tarea futura).
- UI (spec frontend de esta fase).

## Plan
1. **Diagnosis** — Revisar `services_scenarios.py` (event_group, `recurring_year_slots`), semántica `TimeProfile` en `budget`, y cómo `services_projection.py` consume `PlanEvent`.
2. **Change implementation** — Migración → servicio de cierre → ajuste del motor → endpoint → tests.
3. **Validation** — Comandos abajo.

## Validation
```
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py makemigrations plan
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py migrate
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py showmigrations plan
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test plan budget
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff check . && docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff format --check . && docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend mypy .
```

## Required Documentation Updates
- [x] `core/docs/architecture/architecture.md` — contrato de cierre de eventos y semántica `effective_end_date`
- [x] `docs/architecture/api-registry.md` — endpoint `POST /api/plan/events/{id}/close/`
- [x] `core/docs/project-status.md` y `docs/project-status.md` — estado de la fase

## Risks
- Recorte/prorrateo incorrecto de líneas → presupuesto inflado o mermado: cubrir con tests de tabla (año parcial, año completo, años posteriores, histórico).
- Doble contabilización en el motor si el evento cerrado se sigue aplicando: test de trayectoria antes/después del cierre.
- Las líneas pueden haber sido editadas o borradas a mano por el usuario tras la incorporación: el cierre debe tolerar `event_group` incompleto sin fallar.

## Completion Criteria
- [x] All validation commands pass
- [x] All required documentation updates done
- [x] Spec moved to `terminados/`
- [x] Commit created (Conventional Commits)

## Completion note (2026-07-12)

- `effective_end_date` tiene granularidad mensual: el mes efectivo ya no produce deltas ni presupuesto recurrente.
- Una línea estructural se divide en tramo histórico completo y último año parcial; líneas futuras se eliminan y `one_off` se conserva.
- El activo virtual mantiene su valor residual porque esta fase no modela el precio de venta; la baja real continúa en Patrimonio.
