# Phase 5C — FX intradía por minuto con caché persistente

## Context

`services/eur_converter.py` trabaja con granularidad diaria (Frankfurter + 
CoinGecko diario). Cada trade de Pionex se convierte a EUR usando el tipo de
cambio del día completo, lo que introduce error arbitrario en criptos volátiles
intradía. Para ser fiable a efectos AEAT cada movimiento debe valorarse con el
precio efectivo en el momento del fill.

Phase 5C introduce un servicio `intraday_fx` con granularidad por minuto,
caché persistente en base de datos y persistencia de `price_eur` / `fee_eur`
pre-calculados en el propio `BrokerTrade` (para que el FIFO no dependa de
recalcular en cada request).

## Area

`backend`

## Stack

`core`

## Scope

### In scope

- Nuevo modelo `MarketRateSnapshot` con granularidad `1m | 1h | 1d`.
- Nuevo servicio `services/intraday_fx.py` que:
  - Descarga klines 1m públicas de Binance (`GET /api/v3/klines`).
  - Cachea en `MarketRateSnapshot` (lazy, sólo minutos con trades).
  - Expone `get_rate_at(timestamp, asset) -> Decimal` (asset→EUR).
- Nuevos campos `BrokerTrade.price_eur` y `BrokerTrade.fee_eur` (pre-calculados
  al sincronizar).
- Comando `manage.py recompute_trade_eur` para poblar trades existentes sin
  re-sincronizar.
- Seguir usando `eur_converter.py` diario para entidades con timestamp natural
  diario (`IncomeEvent`, `BotNetResult`, `FuturesPosition`).

### Out of scope

- Cambios en FIFO (consumirá `price_eur`/`fee_eur` en Phase 5D).
- Cambios en frontend.

## Plan

### 1. Diagnosis

- Verificar disponibilidad de pares EUR directos en Binance para los assets
  operados por el usuario (`BTCEUR`, `ETHEUR`, `SOLEUR`, `BNBEUR`).
- Para pares sin EUR directo: cadena `asset/USDT → USDT/EUR` (USDT/EUR vía
  Frankfurter `EURUSD` como aproximación 1 USD ≈ 1 USDT).
- Validar rate limits públicos de klines Binance (`/api/v3/klines`, 1000 velas
  por request, sin auth).

### 2. Change implementation

**`models.py`**
```python
class MarketRateSnapshot(models.Model):
    pair = models.CharField(max_length=20)          # 'BTCEUR', 'ETHUSDT', 'EURUSD'
    interval = models.CharField(max_length=4)       # '1m' | '1h' | '1d'
    open_time = models.DateTimeField(db_index=True)
    close = models.DecimalField(max_digits=24, decimal_places=10)
    high = models.DecimalField(max_digits=24, decimal_places=10, null=True, blank=True)
    low  = models.DecimalField(max_digits=24, decimal_places=10, null=True, blank=True)
    source = models.CharField(max_length=30)        # 'binance_klines', 'frankfurter', 'coingecko'
    raw = models.JSONField(default=dict)

    class Meta:
        unique_together = (("pair", "interval", "open_time"),)
        indexes = [models.Index(fields=["pair", "interval", "open_time"])]
```

Añadir a `BrokerTrade`:
```python
price_eur = models.DecimalField(max_digits=24, decimal_places=10, null=True, blank=True)
fee_eur   = models.DecimalField(max_digits=24, decimal_places=10, null=True, blank=True)
eur_rate_source = models.CharField(max_length=30, blank=True)  # 'binance_klines_1m' | 'daily_fallback'
```

Migraciones.

**`services/intraday_fx.py`** (nuevo):
```python
def fetch_klines(pair: str, start_ms: int, end_ms: int, interval: str = "1m") -> list[dict]:
    """Descarga paginada desde Binance public klines."""
    ...

def ensure_range(pair: str, start_ms: int, end_ms: int, interval: str = "1m") -> None:
    """Descarga y persiste en MarketRateSnapshot el rango solicitado si falta."""
    ...

def get_rate_at(timestamp: datetime, asset: str, *, quote: str = "EUR") -> tuple[Decimal, str]:
    """Devuelve (rate, source_tag) para asset→quote en el minuto exacto.
    Fallback: resolver vía USDT si no hay par directo; daily si klines no existen."""
    ...
```

**`services/broker_sync.py`**
- Tras crear/actualizar un `BrokerTrade`, llamar `intraday_fx.get_rate_at(
  trade.timestamp, trade.quote_asset)` para calcular `price_eur = price * rate`
  (y similar para `fee_eur` usando `fee_asset`).
- Guardar `eur_rate_source` para diagnóstico.
- Pre-descargar el rango temporal del sync antes de recorrer trades para
  minimizar llamadas.

**`management/commands/recompute_trade_eur.py`** (nuevo):
```bash
python manage.py recompute_trade_eur --credential <id> --year YYYY [--interval 1m|1h|1d]
```
- Recorre `BrokerTrade` filtrados y rellena `price_eur`/`fee_eur`.
- Idempotente.

### 3. Validation

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations broker_integrations
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
docker compose -f core/docker-compose.yml exec backend python manage.py test broker_integrations
```

**Unit tests** para `intraday_fx.py`:
- Lookup exacto al minuto.
- Lookup en minuto sin datos → descarga + reintento.
- Fallback USDT→EUR para asset sin par EUR directo.
- Fallback daily cuando intradía no disponible (ej. fechas muy antiguas).

**Smoke test manual**:
1. Sync completo → todos los `BrokerTrade` del último año traen `price_eur` y
   `fee_eur` no nulos.
2. `manage.py recompute_trade_eur --credential <id> --year 2025` → idempotente.
3. Comparar `price_eur` para un trade conocido con el FX real en Binance a esa
   hora (desviación < 0.5 %).

## Required Documentation Updates

- [ ] `core/docs/architecture/architecture.md` — sección `market_data` /
      `intraday_fx` (o ampliar la existente de `market_data_sync`).
- [ ] `core/docs/operations/market-data-sync.md` — referencia al nuevo servicio
      y fuente Binance klines.
- [ ] `core/docs/project-status.md` — marcar Phase 5C cerrada.

## Risks

1. **Volumen de `MarketRateSnapshot`**: 1 minuto × 1 año × 4 pares ≈ 2 M filas.
   Mitigar: descarga lazy (sólo rangos con trades) + índice compuesto. Documentar
   el coste y considerar purga de minutos sin uso si crece demasiado.
2. **Assets sin par EUR directo**: cadena USDT→EUR introduce un pequeño error
   (USDT se asume paridad USD). Documentar y añadir warning en el report.
3. **Rate limits klines Binance**: el endpoint público tiene pesos. Añadir
   backoff y agrupar rangos en lotes de 1000 velas (1000 min ≈ 16h).
4. **Timezone**: `BrokerTrade.timestamp` se asume UTC. Validar que los 
   CSVs (UTC+0 según Phase 1) y la API (epoch ms) quedan normalizados antes
   de este hito.

## Completion Criteria

- [ ] Migraciones aplicadas y verificadas.
- [ ] `intraday_fx.get_rate_at` devuelve valores coherentes en tests.
- [ ] Todos los `BrokerTrade` tras sync tienen `price_eur`/`fee_eur` pobladas.
- [ ] `recompute_trade_eur` pobla trades ya existentes.
- [ ] Tests unitarios pasan.
- [ ] Documentation updates done.
- [ ] Spec movida a `terminados/`.
- [ ] Commit: `feat(broker-integrations): add minute-granularity FX for broker trades`.
