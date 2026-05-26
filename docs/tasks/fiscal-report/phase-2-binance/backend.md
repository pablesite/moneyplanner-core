# Phase 2 — Informe fiscal: backend Binance (API-first + CSV fallback)

## Context

Extend `broker_integrations` with Binance integration. Same models as Phase 1.
API-first; CSVs de `finance_data/binance/` como fallback.

For this user: no classic spot trades in order book — all purchases
de BTC/ETH son vía Convert (USDC→BTC/ETH) o Transaction Buy (DCA).

Prerequisito: Phase 1 completada + tabla de cobertura de Phase 0 rellena para Binance.

## Area
`backend`

## Stack
`core`

## Scope

### In scope
- `BinanceClient` (HMAC-SHA256): convert history, earn flexible rewards + endpoints según Phase 0
- CSV importers: `binance_transactions`, `binance_convert`, `binance_recurring`
- Extender `BrokerSyncService` con `sync_binance(credential, year)`
- Tests: client mock, importers, dedup

### Out of scope
- Modelos nuevos (ya creados en Phase 1)
- Motor FIFO / informe (Phase 3)
- Frontend (Phase 4)

## Plan

### 1. Diagnosis
- Confirmar tabla de cobertura de `phase-0-api-exploration/notes.md` para Binance
- Verificar que `broker_integrations` existe con migraciones aplicadas

### 2. Change implementation

**`services/binance_client.py`** (HMAC-SHA256)
```python
# Auth: params + timestamp + signature (HMAC-SHA256 sobre full query string)
# Header: X-MBX-APIKEY

class BinanceClient:
    BASE_URL = 'https://api.binance.com'

    def get_convert_history(self, start_ms: int, end_ms: int) -> list[dict]:
        # GET /sapi/v1/convert/tradeFlow
        # Params: startTime, endTime, limit=1000
        # Paginar hasta cubrir rango completo

    def get_earn_flexible_rewards(self, asset: str, start_ms: int, end_ms: int) -> list[dict]:
        # GET /sapi/v1/simple-earn/flexible/history/rewardsRecord
        # Params: asset, startTime, endTime, size=100

    # Añadir según Phase 0:
    # def get_pay_transactions(self, ...) → Transaction Buy DCA
    # def get_referral_rebates(self, ...) → Referral Commission
```

**`csv_importers/binance_transactions.py`**

Leer `Historial-de-transacciones-*.csv`:
`ID de usuario, Hora, Cuenta, Operación, Moneda, Cambiar, Comentario`

Process by type of Operation:

- `Simple Earn Flexible Interest`:
  → `IncomeEvent` (source=binance_earn_csv, income_type=binance_earn)
  → asset=Moneda, amount=Cambiar (float positivo)

- `Transaction Buy / Transaction Spend / Transaction Fee`:
  → Agrupar triplets por timestamp exacto (mismo segundo, mismo conjunto de operaciones)
  → Identificar: Spend (Moneda=USDC, Cambiar negativo), Buy (Cambiar positivo crypto), Fee (Cambiar negativo crypto)
  → `BrokerTrade` (source=binance_csv, side=BUY)
    - base_asset = Moneda de Buy
    - quote_asset = Moneda de Spend (USDC)
    - quantity = abs(Cambiar de Buy) - abs(Cambiar de Fee)
    - price = abs(Cambiar de Spend) / quantity
    - fee = abs(Cambiar de Fee), fee_asset = Moneda de Fee
  → trade_id = SHA256(hora + "TxBuy" + Moneda_buy + Cambiar_buy)

- `Referral Commission`:
  → `IncomeEvent` (source=binance_referral_csv, income_type=commission)

- `Binance Convert`: **OMITIR** — cubierto por binance_convert.py
- `Simple Earn Flexible Subscription/Redemption`: ignorar (movimientos de capital)
- `Deposit/Withdraw`: ignorar

**`csv_importers/binance_convert.py`**

Learn `Historial-de-órdenes-de-Convert-*.csv`:
`Hora, Billetera, Par, Tipo, Vender, Comprar, Precio, Precio inverso, Fecha actualizada, Status`

- Filter Status=Successful only
- Parsear Vender: `"10.00000000 USDC"` → amount=10.0, asset=USDC
- Parsear Comprar: `"0.00333867 ETH"` → amount=0.00333867, asset=ETH
- → `BrokerTrade` (source=binance_csv, side=BUY)
  - base_asset = asset de Comprar (ETH/BTC)
  - quote_asset = asset de Vender (USDC)
  - quantity = amount de Comprar
  - price = amount_vender / amount_comprar
  - fee = 0 (incluido en el precio de Convert)
- trade_id = SHA256(Hora + Par + Vender_amount)

**`csv_importers/binance_recurring.py`**

Leer `Historial-de-Recurrente-de-compras-recurrentes-de-Convert-*.csv`:
`Fecha, Billetera, Frecuencia, Por hora, Monto original, Moneda original, Monto final, Moneda final, Precio, Precio inverso, Fecha de liquidación, ID del plan, Status`

- Filter Status=SUCCESS only (ignore FAILED)
- → `BrokerTrade` (source=binance_csv, side=BUY)
- trade_id = SHA256(Fecha + ID del plan + Monto original)
- Automatic dedup via `unique_together(source, trade_id)`: if it already exists from binance_convert.py, it is ignored

**Extender `services/broker_sync.py`**
```python
def sync_binance(credential: BrokerCredential, year: int) -> SyncStats:
    # client.get_convert_history → upsert BrokerTrade
    # client.get_earn_flexible_rewards para cada asset [USDT, BTC, ETH] → upsert IncomeEvent
    # Endpoints adicionales según Phase 0
    # Si endpoint no disponible: loggear gap, continuar
```

### 3. Validation

```bash
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
docker compose -f core/docker-compose.yml exec backend python manage.py test broker_integrations
```

Smoke tests manuales:
1. Upload `Historial-de-transacciones-*.csv` → verificar:
   - 619 IncomeEvent con source=binance_earn_csv
   - 13 BrokerTrade con source=binance_csv (de Transaction Buy)
   - 5 IncomeEvent con income_type=commission
2. Upload `Historial-de-órdenes-de-Convert-*.csv` → check 27 additional BrokerTrade
3. Verify that there are no duplicates: total BrokerTrade Binance = 13 (TxBuy) + 27 (Convert) = 40 max
4. `POST /api/v1/broker/sync/{id}/` with Binance credentials → verify API vs CSV data

## Required Documentation Updates
- [ ] `core/docs/architecture/api-registry.md` — actualizar endpoints Binance
- [ ] `core/docs/project-status.md` — marcar Phase 2 completada

## Risks
1. Triplets Transaction Buy/Spend/Fee: si el timestamp no es exactamente el mismo segundo en todos los rows, el agrupamiento falla → usar ventana de ±2s y validar que el triplet tenga exactamente Spend + Buy + Fee del mismo par antes de crear BrokerTrade
2. Dedup between `binance_convert` and `binance_recurring`: deterministic trade_id based on timestamp+par+amount guarantees idempotence; If they match exactly it is the same trade
3. Binance API maximum window per request for `/convert/tradeFlow` is 30 days → page by month

## Completion Criteria
- [ ] `BinanceClient` connects with real API and returns data for year 2025
- [ ] CSV importers cargan los 3 ficheros de `finance_data/binance/` sin errores
- [ ] Sin duplicados entre fuentes (verificar con `BrokerTrade.objects.filter(source__startswith='binance').count()`)
- [ ] All validation commands pass
- [ ] Documentation updates done
- [ ] Spec movida a `terminados/`
- [ ] Commit: `feat(broker-integrations): add binance data layer with API + CSV fallback`
