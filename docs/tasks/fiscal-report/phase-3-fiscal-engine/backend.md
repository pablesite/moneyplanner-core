# Phase 3 — Tax Report: FIFO Engine + Report Generation

## Context

With Pionex and Binance data in DB (Phases 1 and 2 completed), implement the engine
FIFO global cross-exchange y el servicio que genera el JSON del informe fiscal para el frontend.

La AEAT aplica FIFO globalmente por cripto (no por exchange): compras en Binance y ventas
on Pionex they should be treated as a single pool ordered by timestamp.

Prerequisites: Phases 1 and 2 completed with real data in DB.

## Area
`backend`

## Stack
`core`

## Scope

### In scope
- `eur_converter.py`: FX Frankfurter wrapper (reuse existing client in Core) with in-memory cache
- `fifo_calculator.py`: strict FIFO global cross-exchange by `base_asset` + fiscal year
- `fiscal_report.py`: servicio que genera el JSON completo del informe
- Endpoint `GET /api/v1/broker/fiscal-report/?year=YYYY`
- Unit tests: FIFO, EUR conversion, full report

### Out of scope
- Frontend (Phase 4)
- Core verification

## Plan

### 1. Diagnosis
- Localizar el cliente Frankfurter existente en Core (`core/backend/`) — reutilizarlo, no reimplementar
- Verify that there is BrokerTrade, BotNetResult, FuturesPosition, IncomeEvent with data from 2025

### 2. Change implementation

**`services/eur_converter.py`**
```python
# Buscar y reutilizar el cliente Frankfurter ya existente en Core
# Añadir caché en memoria para el ciclo de cálculo: Dict[Tuple[date, str], Decimal]
# Para USDT/USDC: usar EUR/USD (USDT ≈ 1 USD)
# Para BTC/ETH: precio en USD → convertir con EUR/USD del mismo día
# Si fecha sin cotización (festivo): usar último día disponible anterior

def get_eur_rate(trade_date: date, asset: str) -> Decimal:
    ...
```

**`services/fifo_calculator.py`**

Algoritmo FIFO global:
```
Input:
  - base_asset: str (e.g. 'BTC')
  - year: int
  - ownership: Ownership

Pasos:
  1. Cargar TODOS los BrokerTrade del ownership para base_asset,
     ordenados por timestamp ASC (cross-exchange: Binance + Pionex mezclados)
  2. Separar en:
     - buy_queue: deque de lotes (timestamp, quantity_remaining, price_eur)
     - sells: lista de trades con side=SELL
  3. Para cada SELL (en orden temporal):
     - Consumir BUYs de buy_queue en orden FIFO hasta cubrir la cantidad vendida
     - Por lote parcial o completo consumido:
       cost_eur = qty_consumed * buy_price_eur
       proceeds_eur = qty_consumed * sell_price_eur
       gain_loss_eur = proceeds_eur - cost_eur
  4. Si BUYs insuficientes para cubrir un SELL:
     - Loggear como gap; usar cost_eur=0 para la cantidad no cubierta
     - Añadir aviso al informe

Output por lote realizado:
{
  'buy_date': date,
  'sell_date': date,
  'exchange_buy': str,    # 'binance' / 'pionex'
  'exchange_sell': str,
  'symbol': str,
  'quantity': Decimal,
  'cost_eur': Decimal,
  'proceeds_eur': Decimal,
  'gain_loss_eur': Decimal,
  'hold_days': int,
  'casilla': '332'        # en 2025 no hay distinción corto/largo plazo
}

Nota: BotNetResult y FuturesPosition NO pasan por FIFO.
Se añaden directamente al informe como ganancia neta.
```

**`services/fiscal_report.py`**

```python
def generate_fiscal_report(ownership: Ownership, year: int) -> dict:
    # 1. Capital mobiliario: agrupar IncomeEvent por (source, asset), sumar en EUR
    # 2. Bots: agrupar BotNetResult, convertir realized_profit a EUR
    # 3. Futuros: agrupar FuturesPosition, convertir net_pnl a EUR
    # 4. Trades FIFO: para cada base_asset con trades en el año, llamar fifo_calculator
    # 5. Construir data_sources: qué sources están presentes en DB
    # 6. Construir avisos: gaps FIFO, simplificación bots, derivados futuros
```

Output JSON:
```json
{
  "fiscal_year": 2025,
  "capital_mobiliario": [
    {"fuente": "Pionex Earn/Rebase", "asset": "USDT", "importe_eur": 0.0, "casilla": "029"},
    {"fuente": "Pionex CommissionIn", "asset": "USDT", "importe_eur": 0.0, "casilla": "029"},
    {"fuente": "Pionex Dual Investment", "asset": "USDT", "importe_eur": 0.0, "casilla": "029"},
    {"fuente": "Binance Earn USDT", "asset": "USDT", "importe_eur": 0.0, "casilla": "029"},
    {"fuente": "Binance Earn BTC", "asset": "BTC", "importe_eur": 0.0, "casilla": "029"},
    {"fuente": "Binance Earn ETH", "asset": "ETH", "importe_eur": 0.0, "casilla": "029"},
    {"fuente": "Binance Referral", "asset": "USDC", "importe_eur": 0.0, "casilla": "029"}
  ],
  "ganancias_perdidas_bots": [
    {
      "bot_label": "...", "bot_type": "spot_grid",
      "periodo": "2025-01-01/2025-12-31",
      "ganancia_neta_eur": 0.0, "casilla": "332",
      "aviso_simplificacion": true
    }
  ],
  "ganancias_perdidas_futuros": [
    {
      "position_id": "...", "symbol": "BTC_USDT_PERP", "side": "long",
      "open_time": "2025-06-26T18:28:32Z", "close_time": "2025-06-28T12:22:53Z",
      "net_pnl_eur": 0.0, "casilla": "332", "aviso_derivados": true
    }
  ],
  "ganancias_perdidas_trades": [
    {
      "denominacion": "BTC", "casilla": "332",
      "valor_transmision_eur": 0.0, "valor_adquisicion_eur": 0.0,
      "ganancia_eur": 0.0, "perdida_eur": 0.0,
      "lotes": [
        {
          "buy_date": "2025-01-01", "sell_date": "2025-06-15",
          "exchange_buy": "binance", "exchange_sell": "pionex",
          "quantity": 0.001, "cost_eur": 0.0, "proceeds_eur": 0.0,
          "gain_loss_eur": 0.0, "hold_days": 165
        }
      ]
    }
  ],
  "avisos": [
    "Grid bots: ganancia neta simplificada. Cada ciclo es técnicamente una transmisión independiente. Confirmar con asesor.",
    "Futuros perpetuos: tratamiento fiscal como derivados puede diferir de transmisión de moneda virtual. Confirmar con asesor.",
    "FIFO calculado cross-exchange (Pionex + Binance). Gaps de datos pueden afectar el cálculo."
  ],
  "data_sources": {
    "pionex_api": true,
    "pionex_csv_fallback": ["staking", "others"],
    "binance_api": true,
    "binance_csv_fallback": []
  },
  "resumen": {
    "total_capital_mobiliario_eur": 0.0,
    "total_ganancias_eur": 0.0,
    "total_perdidas_eur": 0.0,
    "neto_ganancias_perdidas_eur": 0.0
  }
}
```

Add a `views.py` + `serializers.py` + `urls.py`:
```
GET /api/v1/broker/fiscal-report/?year=YYYY
```

### 3. Validation

```bash
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
docker compose -f core/docker-compose.yml exec backend python manage.py test broker_integrations
```

Critical unit tests for `fifo_calculator.py`:
- Compra y venta en el mismo exchange → coste correcto
- Compra en Binance, venta en Pionex (cross-exchange) → coste de Binance
- Venta sin compra previa suficiente → aviso en `avisos[]`, cost_eur=0 para parte no cubierta
- Partial purchase: a BUY covers multiple partial SELLs

Smoke test manual:
- `GET /api/v1/broker/fiscal-report/?year=2025`
- Verify that `capital_mobiliario` adds all the IncomeEvents of the year
- Verificar que los lotes de BTC muestran el exchange de compra correcto
- Verificar `aviso_derivados: true` en futuros
- Verificar `data_sources` refleja CSV fallback donde aplique

## Required Documentation Updates
- [ ] `core/docs/architecture/api-registry.md` — añadir endpoint `fiscal-report`
- [ ] `core/docs/project-status.md` — marcar Phase 3 completada

## Risks
1. FX not available for some date (weekend, holiday) → use last previous business day (`get_eur_rate` must look back max 3 days)
2. Insufficient BUYs to cover SELLs (lack of pre-2024 history) → issue explicit notice and do not fail the calculation
3. Frankfurter does not have historical BTC/ETH prices directly → may require alternative source (CoinGecko API) for crypto; check before deploy

## Completion Criteria
- [ ] FIFO tests pass all cases (same exchange, cross-exchange, data gap)
- [ ] Endpoint returns full JSON with consistent numeric totals
- [ ] total capital_movable matches manual sum of IncomeEvent for the year
- [ ] All validation commands pass
- [ ] Documentation updates done
- [ ] Spec movida a `terminados/`
- [ ] Commit: `feat(broker-integrations): add FIFO engine and fiscal report endpoint`
