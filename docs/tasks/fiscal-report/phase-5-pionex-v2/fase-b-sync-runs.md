# Phase 5B — Historial y trazabilidad de sync runs

## Context

Hoy sólo persistimos `last_sync_at`, `last_sync_stats`, `last_sync_gaps` en
`BrokerCredential` (ver `models.py:7-41`): cada sync sobreescribe al anterior.
El frontend `FiscalLatestImports.vue` muestra contadores pero no permite
auditar qué trades concretos se trajeron ni cuándo.

Phase 5B introduce un modelo `BrokerSyncRun` que guarda cada ejecución y expone
endpoints para hacer drill-down a los registros creados/actualizados.

## Area

`backend`

## Stack

`core`

## Scope

### In scope

- Nuevo modelo `BrokerSyncRun` que persiste cada ejecución.
- Registrar en el run las PKs creadas/actualizadas (trades, income events,
  bot results) para reconstruir el detalle.
- Endpoints REST:
  - `GET /api/v1/broker/sync-runs/` con filtros por credencial/año.
  - `GET /api/v1/broker/sync-runs/<id>/` con detalle y listas paginadas.
  - `GET /api/v1/broker/trades/` paginado con filtros.
  - `GET /api/v1/broker/income-events/` paginado.
  - `GET /api/v1/broker/bot-results/` y `GET /api/v1/broker/bot-results/<id>/`
    con fills integrados (producto de Phase 5A).
- Mantener los campos legacy (`last_sync_*`) para no romper UI existente.

### Out of scope

- FX intradía (Phase 5C).
- Cambios en FIFO (Phase 5D).
- Frontend de drill-down (Phase 5F).

## Plan

### 1. Diagnosis

- Releer `broker_sync.py:sync_pionex` para entender dónde interceptar la lista
  de PKs creadas. `update_or_create()` ya devuelve `(obj, created)`.
- Confirmar convenciones de paginación en el resto del Core (DRF pagination).

### 2. Change implementation

**`models.py`**
```python
class BrokerSyncRun(models.Model):
    credential = models.ForeignKey(BrokerCredential, on_delete=models.CASCADE,
                                    related_name="sync_runs")
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    year = models.IntegerField()
    status = models.CharField(max_length=20,
        choices=[("running","running"),("ok","ok"),
                 ("partial","partial"),("failed","failed")],
        default="running")
    stats = models.JSONField(default=dict)
    gaps = models.JSONField(default=list)
    new_trade_ids = models.JSONField(default=list)
    updated_trade_ids = models.JSONField(default=list)
    new_income_event_ids = models.JSONField(default=list)
    updated_income_event_ids = models.JSONField(default=list)
    new_bot_result_ids = models.JSONField(default=list)
    updated_bot_result_ids = models.JSONField(default=list)

    class Meta:
        ordering = ["-started_at"]
```

Migración + `makemigrations` + `migrate`.

**`services/broker_sync.py`**
- Al inicio de `sync_pionex`: crear `BrokerSyncRun(status="running")`.
- Mantener buffer de PKs creadas/actualizadas en `SyncStats` y volcar al run
  al final.
- Calcular `status`:
  - `ok` si no hay gaps.
  - `partial` si hay gaps pero sync completó.
  - `failed` si la excepción se propagó (wrap en `try/except` que también
    persiste el run antes de re-raise).
- Copiar también a `BrokerCredential.last_sync_*` (compat).

**`serializers.py` + `views.py` + `urls.py`**
- Listar + detalle de `BrokerSyncRun`.
- Listados paginados de `BrokerTrade`, `IncomeEvent`, `BotNetResult` con
  filtros: `credential`, `year`, `source`, `symbol`, `side`, `bot_id`.
- Filtro `sync_run=<id>` que resuelve vía las PKs del run.

Registrar URLs en `core/backend/broker_integrations/urls.py`.

### 3. Validation

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations broker_integrations
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
docker compose -f core/docker-compose.yml exec backend python manage.py test broker_integrations
```

**Smoke test manual**:

1. Lanzar sync → verificar `BrokerSyncRun` creado con `status=ok` o `partial`.
2. `GET /api/v1/broker/sync-runs/?credential=<id>` devuelve lista cronológica.
3. `GET /api/v1/broker/sync-runs/<id>/` devuelve stats, gaps y listados
   paginados de registros tocados.
4. Lanzar un sync con API KO (wrong key) → run queda `status=failed`
   con mensaje en `gaps`.

## Required Documentation Updates

- [ ] `core/docs/architecture/architecture.md` — añadir sección `BrokerSyncRun`
      y resumen del nuevo flujo.
- [ ] `core/docs/architecture/api-registry.md` — listar nuevos endpoints.
- [ ] `core/docs/project-status.md` — marcar Phase 5B cerrada.

## Risks

1. **Tamaño de `*_ids` en JSONField** si el sync trae miles de trades:
   capar en un número razonable (por ejemplo 5000 IDs por run) y loguear
   overflow como gap.
2. **Compatibilidad con frontend actual**: mantener el payload existente de
   `last_sync_status` sin cambios. Validar con `/informe-fiscal` antes de cerrar.
3. **Privacidad**: cerciorarse de que los endpoints nuevos respetan ownership
   (reutilizar helpers existentes de `broker_integrations/views.py`).

## Completion Criteria

- [ ] Migración aplicada y verificada.
- [ ] Cada `sync_pionex` crea un `BrokerSyncRun` con los IDs de los registros.
- [ ] Endpoints nuevos responden con paginación y filtros.
- [ ] `last_sync_status` existente sigue funcionando sin cambios de contrato.
- [ ] Comandos de validación pasan.
- [ ] Documentation updates done.
- [ ] Spec movida a `terminados/`.
- [ ] Commit: `feat(broker-integrations): persist sync runs and add drill-down endpoints`.
