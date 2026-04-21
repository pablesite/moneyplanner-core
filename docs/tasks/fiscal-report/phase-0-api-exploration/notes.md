# Phase 0 — Exploración de APIs Pionex y Binance

## Tipo: Manual
## Stack: core

## Objetivo

Verificar qué endpoints cubren qué datos antes de implementar. Rellenar la tabla de cobertura
y actualizar las specs de Phase 1 y 2 en consecuencia.

---

## Pionex (HMAC-SHA256, base: https://api.pionex.com)

Autenticación: `timestamp` (ms epoch) + `api_key` como query params + firma HMAC-SHA256
sobre el query string completo ordenado alfabéticamente.

| Endpoint | Esperado | ¿Disponible? | ¿Cobertura 2024? | Notas |
|---|---|---|---|---|
| GET /api/v1/trade/fills | Fills signal bots spot | | | Params: symbol, startTime, endTime, limit |
| GET /api/v1/bot/orders/spotGrid/order | Bot summary: realizedProfit, fechas | | | Params: botId |
| GET /api/v1/earn/dual/records | Dual Investment yields | | | Sin CSV fallback disponible |
| GET /api/v1/account/balances | Verificar conexión básica | | | — |
| ❓ /api/v1/earn/history | Staking/Rebase issued/claimed profit | | | Fallback: `staking.csv` (130 filas) |
| ❓ /api/v1/account/commission | CommissionIn rebates USDT | | | Fallback: `others.csv` (6178 filas) |
| ❓ /api/v1/futures/positions/history | Posiciones perpetuas cerradas | | | Fallback: `position_futures.csv` (~10 filas) |

---

## Binance (HMAC-SHA256, base: https://api.binance.com)

API key con permisos: Read Info, Spot & Margin Trading, Convert History, Earn.

| Endpoint | Esperado | ¿Disponible? | ¿Cobertura 2024? | Notas |
|---|---|---|---|---|
| GET /sapi/v1/convert/tradeFlow | Convert USDC→BTC/ETH (todos) | | | Fallback: `órdenes-de-Convert.csv` (27 filas) |
| GET /sapi/v1/simple-earn/flexible/history/rewardsRecord | Earn Interest USDT/BTC/ETH | | | Fallback: `transacciones.csv` (619 filas) |
| GET /api/v3/myTrades | Spot trades clásicos | | | Esperamos vacío para este usuario |
| ❓ GET /sapi/v1/pay/transactions | Transaction Buy DCA (triplets) | | | Fallback: `transacciones.csv` (13 triplets) |
| ❓ GET /sapi/v1/rebate/taxQuery | Referral Commission USDC | | | Fallback: `transacciones.csv` (5 filas) |
| GET /sapi/v1/capital/deposit/hisrec | Depósitos on-chain ETH/BTC | | | Confirmar coste adquisición ETH MetaMask |

---

## Tabla de cobertura final (rellenar antes de iniciar Phase 1)

| Fuente de datos | API disponible | CSV fallback | Decisión final |
|---|---|---|---|
| Pionex fills signal bots | | `trading.csv` (Spot) | |
| Pionex grid bot summary | | No disponible | |
| Pionex Dual Investment | | `structured-products.csv` (vacío) | Solo API |
| Pionex Staking/Rebase | | `staking.csv` (completo) | |
| Pionex CommissionIn | | `others.csv` (6178 filas) | |
| Pionex Futures positions | | `position_futures.csv` (~10 filas) | |
| Binance Convert orders | | `órdenes-de-Convert.csv` (27 filas) | |
| Binance Simple Earn Interest | | `transacciones.csv` (619 filas) | |
| Binance Transaction Buy | | `transacciones.csv` (triplets ×13) | |
| Binance Referral Commission | | `transacciones.csv` (5 filas) | |

---

## Resultado esperado

1. Tabla de cobertura rellena con: endpoint disponible sí/no, cobertura histórica 2024, decisión API/CSV/ambos.
2. Actualizar las specs de Phase 1 (`phase-1-pionex/backend.md`) y Phase 2 (`phase-2-binance/backend.md`)
   con los endpoints confirmados que implementar en cada cliente.
3. Anotar límites de paginación descubiertos (ventanas máximas de tiempo, límite de registros por request).
