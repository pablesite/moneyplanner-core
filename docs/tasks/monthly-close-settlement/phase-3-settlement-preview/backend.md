# Fase 3 - Motor de preview y recomendaciones

## Title

Calcular saldos economicos, reservas, compensaciones y rutas de transferencia sin crear movimientos.

## Context

Con ownership resoluble y entradas configuradas, el cierre puede transformar saldos fisicos en un
plan de distribucion explicable. Esta fase completa la version backend utilizable: produce una vista
previa exacta y snapshots finalizables, pero el usuario sigue ejecutando y registrando las
transferencias manualmente.

## Area

`backend`

## Stack

`core`

## Scope

### In scope

1. Servicio puro `compute_monthly_close_settlement` separado de la orquestacion del endpoint.
2. Apertura desde el settlement finalizado anterior o baseline de activacion.
3. Variacion economica por miembro desde movimientos `posted`, asignada por ownership del movimiento.
4. Transferencias internas neutrales para ingreso/gasto y relevantes solo para localizacion fisica.
5. Deteccion explicable de pagos cruzados dentro del perimetro configurado, con transaccion origen.
6. Reserva del siguiente mes para gasto operativo y compromisos temporales recurrentes activos.
7. Asignaciones de ahorro/inversion a la cuenta destino; exclusion de puntual, transferencia y roles
   no soportados, con warning explicito.
8. Solver de saldos objetivo por cuenta y miembro, incluyendo aportaciones inversas cuando falta
   financiacion individual.
9. Modelos snapshot del settlement y recomendaciones por ruta, ownership y miembro.
10. Payload aditivo `ownership_settlement` en el GET actual del cierre, con estados `disabled`,
    `not_ready`, `ready`, `finalized` y calidad de datos.
11. Congelar reparto, inputs, importes y recomendaciones al finalizar; limpiar/recalcular al reabrir
    sin tocar snapshots de cierres anteriores.
12. Permitir finalizar el cierre dual existente aunque settlement este `not_ready`, dejando trazado
    que no hubo liquidacion fiable.
13. Absorber la deuda documentada del filtro de titularidad: residual y perimetro deben usar el mismo
    resolver economico cuando settlement este activo, sin parches de frontend divergentes.

### Out of scope

1. Crear transferencias ledger.
2. Marcar una recomendacion como ejecutada.
3. Reservar puntuales automaticamente.
4. Recomendar FX o transferencias entre monedas distintas.
5. Optimizar en que banco ejecutar una ruta cuando hay varios equivalentes.

## Plan

1. Construir value objects y funciones puras para ownership, flujos, requisitos y routing.
2. Añadir consultas agregadas y caches por request; prohibir N+1 por movimiento o partida.
3. Persistir snapshots solo en transiciones de lifecycle, no durante cada GET.
4. Integrar el payload aditivo en `compute_monthly_close_state`.
5. Añadir errores/readiness accionables y trazabilidad por fila.
6. Cubrir los escenarios de `qa.md` con fixtures deterministas.

## Validation

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations budget
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend python manage.py showmigrations budget
docker compose -f core/docker-compose.yml exec backend python manage.py test budget accounting memberships net_worth plan
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
```

## Required Documentation Updates

- [ ] `core/docs/architecture/architecture.md` - algoritmo, lifecycle y snapshots.
- [ ] `core/docs/architecture/accounting-movements-architecture.md` - neutralidad de transferencias.
- [ ] `core/docs/roadmap/product-roadmap.md` - ownership settlement pasa a implementacion.
- [ ] `docs/architecture/api-registry.md` - payload `ownership_settlement`.
- [ ] `docs/project-status.md` - resolver pendiente de residual/perimetro por titular.
- [ ] `core/docs/project-status.md` - cerrar version backend de preview.

## Risks

- Un solver que no conserve invariantes puede crear dinero. Cada etapa debe reconciliar por miembro,
  cuenta, ownership y total familiar.
- Mezclar check-ins estimados con ledger no permite atribucion exacta. Un perfil activo exige cobertura
  suficiente y degrada a `not_ready`; nunca estima ownership desde un delta global.
- Backdated movements can invalidate draft previews. Frozen snapshots remain immutable and reopening
  is the explicit recalculation boundary.
- Credit cards and negative cash balances require sign-aware tests; no `max(0)` silencioso.

## Completion Criteria

- [ ] The combined dynamic-share plus 50/50 example reconciles to the cent.
- [ ] Personal-account payment of a shared expense produces the expected compensation.
- [ ] Shared-account payment of an individual expense charges only that member economically.
- [ ] Internal transfers do not change household or member economic totals.
- [ ] Every target account has compatible effective ownership.
- [ ] Disabled and not-ready profiles do not regress normal close finalization.
- [ ] Finalized snapshots remain immutable and reopen behavior is explicit.
- [ ] Performance/query assertions pass for a 12-month realistic fixture.
- [ ] All validation commands pass.
- [ ] All required documentation updates done.
- [ ] Spec moved to `terminados/`.
- [ ] Commit created (Conventional Commits).
