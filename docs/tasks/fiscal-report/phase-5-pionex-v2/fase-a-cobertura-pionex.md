# Phase 5A — Cobertura y validación de datos Pionex

## Context

El sync actual (`sync_pionex` en `core/backend/broker_integrations/services/broker_sync.py:492-582`)
sólo trae fills de `BTC_USDT` y `ETH_USDT` hardcodeados y obtiene el resumen
agregado de cada bot (`realized_profit`) sin los fills individuales. Esto impide
aplicar FIFO estricto a la actividad de los bots y deja fuera cualquier par que
el usuario haya operado además de BTC/ETH. Además, no hay ninguna validación que
confirme que los datos traídos reconcilian con los saldos actuales de la cuenta.

Phase 5A amplía la cobertura para que la foto de actividad en Pionex quede completa
antes de aplicar cualquier cálculo fiscal.

## Area

`backend`

## Stack

`core`

## Scope

### In scope

- Auto-descubrimiento de símbolos spot a partir de balances + historial + env override.
- Nuevo método `PionexClient.get_bot_spot_grid_orders(bot_id)` que consume
  `/api/v1/bot/order/spotGrid/orders` (o endpoint equivalente tras validación).
- Persistir cada fill de bot como `BrokerTrade` con `source="pionex_bot_api"` y
  nuevo FK opcional `bot` hacia `BotNetResult`.
- Auto-descubrimiento de bases activas para Dual Investment (actualmente env
  `PIONEX_DUAL_BASES`).
- `balance_reconciliation`: al final del sync, comparar saldos calculados vs
  `get_balances()`, emitir gap `balance_mismatch` con detalle por asset si difiere.

### Out of scope

- Historial persistente de sync runs (Phase 5B).
- FX intradía (Phase 5C).
- Cambios en FIFO o fiscal_report (Phase 5D).
- Binance (Phase 6).

## Plan

### 1. Diagnosis

- Confirmar en la doc oficial de Pionex el endpoint correcto para fills de bots
  de grid spot (candidato: `/api/v1/bot/order/spotGrid/orders`).
- Validar con credencial real: ventana de tiempo admitida, paginación,
  campos expuestos.
- Revisar `BrokerTrade.raw` existente para entender qué campos ya persistimos.

### 2. Change implementation

**`services/pionex_client.py`**
- Nuevo método `get_bot_spot_grid_orders(bot_id, start_ms=None, end_ms=None) -> list[dict]`.
- Paginación defensiva (iterar por tiempo si el endpoint devuelve ventana limitada).

**`services/broker_sync.py`**
- Sustituir la lista hardcodeada de símbolos por `discover_spot_symbols(credential)`:
  1. Balances con `amount > 0`.
  2. Símbolos ya vistos en `BrokerTrade` del ownership.
  3. Override `PIONEX_SPOT_SYMBOLS` (env, CSV).
- Tras `get_bot_orders`, por cada bot descubierto:
  - Llamar `get_bot_spot_grid_orders(bot_id)`.
  - Mapear a `BrokerTrade` (source=`pionex_bot_api`, `bot=<BotNetResult>`).
  - Dedupe por `(source, trade_id)`.
- Auto-descubrir bases para Dual Investment desde balances (mantener override env
  como precedencia opcional).
- Nuevo bloque `compute_balance_reconciliation(credential)` que se ejecuta al
  final del sync y añade gaps `balance_mismatch` si difiere.

**`models.py`**
- Añadir `bot: FK("BotNetResult", null=True, blank=True, on_delete=SET_NULL,
  related_name="fills")` a `BrokerTrade`.
- Añadir choice `pionex_bot_api` a `BrokerTrade.source`.
- Migración + `makemigrations` + `migrate`.

### 3. Validation

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations broker_integrations
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend python manage.py showmigrations broker_integrations
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
docker compose -f core/docker-compose.yml exec backend python manage.py test broker_integrations
```

**Smoke test manual** con credencial Pionex real (año 2025):

1. Sincronizar → verificar:
   - Aparecen `BrokerTrade` con `source=pionex_bot_api` y `bot` asignado.
   - Aparecen símbolos más allá de BTC/ETH si el usuario los ha operado.
   - Gaps `balance_mismatch` documentados (si los hay) con saldo esperado vs real.
2. Validar que `realized_profit` del summary ≈ `sum(fills)` por bot (margen
   configurable para fee rounding).

## Required Documentation Updates

- [ ] `core/docs/architecture/architecture.md` — documentar nuevos campos de
      `BrokerTrade` y nueva lista de `source` choices.
- [ ] `core/docs/tasks/fiscal-report/phase-0-api-exploration/notes.md` — añadir
      hallazgos del endpoint `bot/order/spotGrid/orders`.
- [ ] `core/docs/project-status.md` — marcar Phase 5A cerrada al terminar.

## Risks

1. **Endpoint bot/spotGrid/orders con cobertura limitada**: si sólo devuelve las
   últimas N órdenes por bot, paginar por ventana temporal usando `period_start`
   / `period_end` del `BotNetResult`.
2. **Símbolos con saldo nulo pero historial pasado**: asegurar que
   `discover_spot_symbols` los incluye vía trades previos en DB.
3. **balance_reconciliation con depósitos/retiros on-chain no sincronizados**:
   permitir tolerancia configurable y documentar fuentes no cubiertas (aparecerán
   como `balance_mismatch` hasta que Phase 5D incorpore `ManualCostBasis`).

## Completion Criteria

- [ ] Migración aplicada y verificada con `showmigrations`.
- [ ] `BrokerTrade.source` admite `pionex_bot_api`; FK `bot` operativo.
- [ ] Sync real con 2 bots o más genera fills individuales por bot.
- [ ] `balance_reconciliation` reporta gaps cuando difiere de `get_balances()`.
- [ ] Todos los comandos de validación pasan.
- [ ] Documentation updates done.
- [ ] Spec movida a `terminados/`.
- [ ] Commit: `feat(broker-integrations): expand pionex coverage with bot fills and balance reconciliation`.
