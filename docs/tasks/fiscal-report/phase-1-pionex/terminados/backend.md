# Phase 1 — Informe fiscal: backend Pionex (API-first + CSV fallback)

## Context

Crear la app `broker_integrations` en Core con los modelos base y la integración con Pionex.
API-first: los CSVs de `finance_data/pionex/` son fallback para lo que la API no cubra.
Resultado: datos de Pionex en DB listos para el motor FIFO de Phase 3.

Prerequisito: Phase 0 completada (tabla de cobertura rellena).

## Area
`backend`

## Stack
`core`

## Scope

### In scope
- Nueva app Django `broker_integrations`
- Modelos: BrokerCredential, BrokerTrade, BotNetResult, FuturesPosition, IncomeEvent
- Cifrado Fernet en `BrokerCredential.api_secret_encrypted` (env: `BROKER_ENCRYPTION_KEY`)
- `PionexClient` (HMAC-SHA256): fills, bot summary, dual investment + endpoints según Phase 0
- CSV importers Pionex: pionex_trading, pionex_futures, pionex_staking, pionex_others, pionex_dust
- `BrokerSyncService`: orquestador API → DB con dedup por `(source, trade_id)`
- Endpoints REST: credentials CRUD, sync, csv-import, sync status
- Tests: modelos, client mock, importers, dedup

### Out of scope
- Integración Binance (Phase 2)
- Motor FIFO / informe fiscal (Phase 3)
- Frontend (Phase 4)
- SaaS mirror

## Plan

### 1. Diagnosis
- Leer `core/docs/project-status.md` y `core/docs/architecture/architecture.md`
- Verificar que no existe app `broker_integrations`
- Confirmar tabla de cobertura de `phase-0-api-exploration/notes.md`

### 2. Change implementation

**Crear app**
```bash
docker compose -f core/docker-compose.yml exec backend python manage.py startapp broker_integrations
```
Registrar en `INSTALLED_APPS` en `core/backend/config/settings/`.

**`models.py`** — definir todos los modelos:

```python
# BrokerCredential
broker: CharField(max_length=20, choices=[('pionex','Pionex'),('binance','Binance')])
label: CharField(max_length=100)
api_key: CharField(max_length=200)
api_secret_encrypted: BinaryField()   # Fernet(env BROKER_ENCRYPTION_KEY)
ownership: FK('memberships.Ownership', on_delete=CASCADE)
created_at, updated_at: DateTimeField(auto_now_add / auto_now)

# BrokerTrade
credential: FK(BrokerCredential, null=True, blank=True, on_delete=SET_NULL)
source: CharField choices=['pionex_api','pionex_csv','binance_api','binance_csv']
trade_id: CharField(max_length=100)  # unique_together(source, trade_id)
symbol: CharField(max_length=20)     # 'BTC_USDT', 'ETHUSDC'
base_asset: CharField(max_length=10)
quote_asset: CharField(max_length=10)
side: CharField choices=['BUY','SELL']
price: DecimalField(max_digits=24, decimal_places=10)
quantity: DecimalField(max_digits=24, decimal_places=10)  # en base_asset
fee: DecimalField(max_digits=24, decimal_places=10)
fee_asset: CharField(max_length=10)
timestamp: DateTimeField(db_index=True)
raw: JSONField()

# BotNetResult
credential: FK(BrokerCredential, on_delete=CASCADE)
bot_id: CharField(max_length=100)    # unique_together(credential, bot_id)
bot_type: CharField(max_length=50)   # 'spot_grid', 'signal_bot_grid'
label: CharField(max_length=200)
base_asset: CharField(max_length=10)
quote_asset: CharField(max_length=10)
realized_profit: DecimalField(max_digits=24, decimal_places=10)  # en quote_asset
total_fee_base: DecimalField(max_digits=24, decimal_places=10)
total_fee_quote: DecimalField(max_digits=24, decimal_places=10)
period_start: DateTimeField()
period_end: DateTimeField()
synced_at: DateTimeField(auto_now=True)
raw: JSONField()

# FuturesPosition
credential: FK(BrokerCredential, null=True, blank=True, on_delete=SET_NULL)
source: CharField choices=['pionex_api','pionex_csv']
position_id: CharField(max_length=200)  # unique_together(source, position_id)
symbol: CharField(max_length=30)        # 'BTC_USDT_PERP'
base_asset: CharField(max_length=10)
side: CharField choices=['long','short']
open_time: DateTimeField()
close_time: DateTimeField()
pnl: DecimalField(max_digits=24, decimal_places=10)          # en USDT
fee: DecimalField(max_digits=24, decimal_places=10)
funding_fee: DecimalField(max_digits=24, decimal_places=10)
net_pnl: DecimalField(max_digits=24, decimal_places=10)      # calculado: pnl - abs(fee) + funding_fee
raw: JSONField()

# IncomeEvent
credential: FK(BrokerCredential, null=True, blank=True, on_delete=SET_NULL)
source: CharField choices=[
    'pionex_staking_api','pionex_staking_csv',
    'pionex_dual_invest_api',
    'pionex_commission_csv',
    'binance_earn_api','binance_earn_csv',
    'binance_referral_csv',
    'manual'
]
income_type: CharField choices=[
    'earn_issued','earn_claimed',
    'dual_invest_yield',
    'commission',
    'binance_earn'
]
asset: CharField(max_length=10)
amount: DecimalField(max_digits=24, decimal_places=10)
timestamp: DateTimeField(db_index=True)
description: CharField(max_length=300)
raw: JSONField()
```

**`services/encryption.py`**
```python
from cryptography.fernet import Fernet
import os

def get_fernet() -> Fernet:
    return Fernet(os.environ['BROKER_ENCRYPTION_KEY'])

def encrypt(value: str) -> bytes:
    return get_fernet().encrypt(value.encode())

def decrypt(encrypted: bytes) -> str:
    return get_fernet().decrypt(encrypted).decode()
```

**`services/pionex_client.py`** (HMAC-SHA256, alineado con docs oficiales)
```python
# Auth (private endpoints):
# - Query param required: timestamp (ms)
# - Required headers: PIONEX-KEY, PIONEX-SIGNATURE
# - GET signature payload: METHOD + PATH_URL + QUERY + TIMESTAMP
# - Add explicit User-Agent header in client session

class PionexClient:
    BASE_URL = 'https://api.pionex.com'

    def get_fills(self, symbol: str, start_ms: int, end_ms: int) -> list[dict]:
        # GET /api/v1/trade/fills
        # Ventanas temporales + iteracion hasta cubrir rango anual.
        # El endpoint retorna ultimos fills al exceder maximo por request.

    def get_bot_summary(self, bot_id: str) -> dict:
        # GET /api/v1/bot/orders/spotGrid/order?botId=...

    def get_dual_invest_records(self, start_ms: int, end_ms: int) -> list[dict]:
        # GET /api/v1/earn/dual/records
        # Paginacion por endTime + limit (startTime opcional)

    # Anadir segun Phase 0:
    # def get_staking_history(self, ...) -> list[dict]   # si existe
    # def get_futures_positions(self, ...) -> list[dict]  # si existe
```

Implementacion recomendada adicional:
- Reintentos con backoff exponencial en 429.
- Throttling defensivo para no superar 10 req/s por IP y 10 req/s por account.

**`csv_importers/pionex_trading.py`**
- Leer `trading.csv`: `date(UTC+0), executed_qty, amount, price, side, symbol, fee, fee_coin, market_type, tax_id`
- Filtrar `market_type == 'Spot'` → `BrokerTrade` (source=pionex_csv)
- `trade_id` = hash SHA256 de `(date + symbol + side + executed_qty + price)` (no hay ID propio)

**`csv_importers/pionex_futures.py`**
- Leer `position_futures.csv`: `position_id, symbol, position_side, open_time, close_time, pnl, fee, funding_fee`
- `net_pnl = Decimal(pnl) - abs(Decimal(fee)) + Decimal(funding_fee)`
- `base_asset` = primer token del símbolo (e.g. `BTC_USDT_PERP` → `BTC`)

**`csv_importers/pionex_staking.py`**
- Leer `staking.csv`: `date(UTC+0), Received Quantity, Received Currency, Sent Quantity, Sent Currency, tag`
- Filtrar `tag in ['issued_profit', 'claimed_profit']` → `IncomeEvent`
- `income_type = 'earn_issued'` / `'earn_claimed'` según tag
- Ignorar filas `stake` y `unstake` (movimientos de capital)

**`csv_importers/pionex_others.py`**
- Leer `others.csv`: `date(UTC+0), coin, amount, tag, comment`
- Filtrar `tag == 'CommissionIn'` → `IncomeEvent` (income_type=commission)
- Ignorar `FundingFee` y `Convert`

**`csv_importers/pionex_dust.py`**
- Leer `dust-collector.csv`: `date(UTC+0), amount, coin, price, swap_value`
- → `BrokerTrade` (side=SELL, base_asset=coin, quote_asset=USDT)
- `price = Decimal(swap_value) / Decimal(amount)`

**`services/broker_sync.py`**
```python
def sync_pionex(credential: BrokerCredential, year: int) -> SyncStats:
    # Para cada símbolo activo (BTC_USDT, ETH_USDT):
    #   client.get_fills(symbol, start_year_ms, end_year_ms) → upsert BrokerTrade
    # client.get_bot_summary(bot_id) para cada bot → upsert BotNetResult
    # client.get_dual_invest_records → upsert IncomeEvent
    # Endpoints opcionales según Phase 0
    # Si endpoint falla con 404/403: loggear gap_detected, continuar
    # Retornar SyncStats: {new_trades, updated_trades, new_bot_results, new_income_events, gaps}
```

**`views.py` + `serializers.py` + `urls.py`**
```
POST   /api/v1/broker/credentials/
GET    /api/v1/broker/credentials/
DELETE /api/v1/broker/credentials/{id}/
POST   /api/v1/broker/sync/{id}/          → retorna SyncStats JSON
GET    /api/v1/broker/sync/{id}/status/   → {last_sync, stats, gaps_detected}
POST   /api/v1/broker/csv-import/         → {broker, file_type, file} multipart
```

Registrar en `core/backend/config/urls.py`:
```python
path('api/v1/broker/', include('broker_integrations.urls')),
```

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

Smoke tests manuales:
1. `POST /api/v1/broker/credentials/` con credenciales Pionex reales → verificar api_secret cifrado en DB
2. `POST /api/v1/broker/sync/{id}/` → verificar BrokerTrade, BotNetResult, IncomeEvent creados
3. Upload `staking.csv` → verificar IncomeEvent con source=pionex_staking_csv
4. Upload `position_futures.csv` → verificar FuturesPosition con net_pnl calculado

## Required Documentation Updates
- [x] `core/docs/architecture/architecture.md` — añadir sección `broker_integrations` con API pública
- [x] `core/docs/architecture/architecture.md` — endpoints públicos de `broker_integrations` registrados en la sección de API
- [x] `core/docs/project-status.md` — marcar Phase 1 completada

## Risks
1. Pionex API rate limits / ventanas de tiempo -> implementar paginacion por rangos temporales con backoff
   y control de throughput (10 req/s IP + 10 req/s account segun docs).
2. Fechas en CSV en UTC+0 sin timezone info → parsear como UTC explícitamente (`datetime.fromisoformat(...).replace(tzinfo=timezone.utc)`)
3. `trade_id` no existe en `trading.csv` → usar hash determinístico; documentar en raw el campo fuente

## Revision post-Phase 1 (2026-04-22)
1. Mantener la estrategia API-first + CSV fallback, pero continuar la exploracion de Pionex API para reducir dependencia de CSV.
2. Abrir linea de investigacion para endpoints alternativos que cubran:
   - eventos staking/rebase
   - comisiones `CommissionIn`
   - historico de futures cerrados
3. Ajustar `PionexClient` para variantes de parametros por endpoint cuando la doc sea inconsistente con respuesta real
   (ejemplo observado: `dual/records` exige `base`, con valores validos como `BTC`, `ETH`, `SOL`, `BNB`).
4. Registrar en cada sync los gaps por endpoint con codigo/mensaje para retroalimentar la matriz de cobertura de Phase 0.
5. Auto-discovery de bots spot grid via `GET /api/v1/bot/orders` (running + finished, paginado) con
   fallback opcional `PIONEX_BOT_IDS` para IDs no descubiertos.

## Completion Criteria
- [x] Migraciones aplicadas y verificadas con `showmigrations`
- [x] `PionexClient` conecta con API real y devuelve datos para año 2025
- [x] CSV importers cargan los 5 ficheros de `finance_data/pionex/` sin errores
- [x] Dedup funciona: importar el mismo CSV dos veces no duplica registros
- [x] Todos los comandos de validación pasan
- [x] Documentation updates done
- [x] Spec movida a `terminados/`
- [x] Commit: `feat(broker-integrations): add pionex data layer with API + CSV fallback`
