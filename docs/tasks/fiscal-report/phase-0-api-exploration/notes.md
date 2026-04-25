# Phase 0 — Exploración de APIs Pionex y Binance

## Tipo: Manual
## Stack: core

## Objetivo

Verificar qué endpoints cubren qué datos antes de implementar. Rellenar la tabla de cobertura
y actualizar las specs de Phase 1 y 2 en consecuencia.

---

## Pionex (HMAC-SHA256, base: https://api.pionex.com)

Autenticacion (confirmada en docs oficiales):
- Query obligatoria: `timestamp` (ms epoch, ventana valida +/-20s)
- Headers obligatorios: `PIONEX-KEY`, `PIONEX-SIGNATURE`
- Firma GET: construir payload segun docs (`METHOD + PATH_URL + QUERY + TIMESTAMP`)
- Nota operativa: definir `User-Agent` explicito en el cliente HTTP para evitar bloqueos 403
  en algunos entornos de ejecucion (observado en contenedor Docker durante la exploracion).

| Endpoint | Esperado | ¿Disponible? | ¿Cobertura 2024? | Notas |
|---|---|---|---|---|
| GET /api/v1/trade/fills | Fills signal bots spot | Si (docs) | Pendiente validacion con key real | Params: symbol, startTime, endTime. Endpoint devuelve ultimos 100 fills si se excede limite. |
| GET /api/v1/bot/orders/spotGrid/order | Bot summary: realizedProfit, fechas | | | Params: botId |
| GET /api/v1/bot/order/spotGrid/orders | Fills individuales de bot spot-grid | Parcial (implementado en cliente, pendiente confirmacion con key real) | Pendiente validacion con key real | Params usados en cliente: `botId`, `startTime`, `endTime`, `limit`, `pageToken`. Parsing defensivo de `orders/results/list/rows/items` y paginacion por `nextPageToken` o ventana temporal. |
| GET /api/v1/earn/dual/records | Dual Investment yields | Si (docs) | Pendiente validacion con key real | Sin CSV fallback disponible. Paginado: `limit`, `endTime` (required), `startTime` opcional. |
| GET /api/v1/account/balances | Verificar conexion basica | Si (docs) | Pendiente validacion con key real | Requiere permiso `Enable reading`. |
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
| Pionex fills signal bots | Sí (docs; auth validada en private endpoint) | `trading.csv` (Spot) | API-first + CSV fallback |
| Pionex grid bot summary | Sí (docs; requiere `botId`) | No disponible | Solo API |
| Pionex Dual Investment | Sí (docs; paginado por `endTime` + `limit`) | `structured-products.csv` (vacío) | Solo API |
| Pionex Staking/Rebase | No confirmado en API durante Phase 0 | `staking.csv` (completo) | CSV obligatorio (API opcional si se confirma endpoint) |
| Pionex CommissionIn | No confirmado en API durante Phase 0 | `others.csv` (6178 filas) | CSV obligatorio |
| Pionex Futures positions | No confirmado en API durante Phase 0 | `position_futures.csv` (~10 filas) | CSV obligatorio (API opcional si se confirma endpoint) |
| Pionex deposits/withdrawals | No confirmado en API durante Phase 0 | `deposit-withdraw.csv` | Phase 5G: modelo `DepositWithdrawal` + importer `pionex_deposit_withdraw`; incluido en balance reconciliation |
| Binance Convert orders | Sí (probado: `/sapi/v1/convert/tradeFlow`) | `órdenes-de-Convert.csv` (27 filas) | API-first + CSV fallback |
| Binance Simple Earn Interest | Sí (probado: `/sapi/v1/simple-earn/flexible/history/rewardsRecord`, `type` requerido, ventana 90d) | `transacciones.csv` (619 filas) | API-first + CSV fallback |
| Binance Transaction Buy | Sí (probado: `/sapi/v1/pay/transactions`) | `transacciones.csv` (triplets ×13) | API-first + CSV fallback |
| Binance Referral Commission | No usable (`/sapi/v1/rebate/taxQuery` => `100001003 Verification failed`) | `transacciones.csv` (5 filas) | CSV obligatorio |

---

## Resultado esperado

1. Tabla de cobertura rellena con: endpoint disponible sí/no, cobertura histórica 2024, decisión API/CSV/ambos.
2. Actualizar las specs de Phase 1 (`phase-1-pionex/terminados/backend.md`) y Phase 2 (`phase-2-binance/terminados/backend.md`)
   con los endpoints confirmados que implementar en cada cliente.
3. Anotar límites de paginación descubiertos (ventanas máximas de tiempo, límite de registros por request).

## Hallazgos tecnicos de la exploracion (2026-04-22) — Binance

1. Credenciales Binance validadas con exito en endpoints privados (`/api/v3/account`, `/sapi/v1/convert/tradeFlow`,
   `/api/v3/myTrades`, `/sapi/v1/pay/transactions`).
2. `GET /sapi/v1/simple-earn/flexible/history/rewardsRecord` requiere `type` (por ejemplo `ALL`, `BONUS`, `REALTIME`).
3. `GET /sapi/v1/simple-earn/flexible/history/rewardsRecord` tiene ventana maxima de 90 dias
   (`-6021 Query time range too large` al usar >90 dias).
4. `GET /sapi/v1/capital/deposit/hisrec` tiene ventana maxima de 90 dias (`-4047` al usar >90 dias).
5. `GET /sapi/v1/rebate/taxQuery` responde `100001003 Verification failed` para esta cuenta/clave
   (mantener fallback CSV para referral commission).
6. `GET /sapi/v1/convert/tradeFlow` con 31 dias no errorea, pero devuelve mismo volumen que 30 dias en esta prueba;
   tratar como ventana efectiva mensual para sync robusto.

## Hallazgos tecnicos de la exploracion (2026-04-22)

1. Rate limits Pionex (docs): 10 req/s por IP y 10 req/s por account en endpoints privados.
2. Si se supera limite: HTTP 429 y baneo temporal; aplicar throttling/backoff en `PionexClient`.
3. `GET /api/v1/trade/fills` retorna los fills mas recientes cuando se excede el maximo por request
   (usar ventanas temporales y paginacion defensiva por tramos).
4. `GET /api/v1/earn/dual/records` permite paginado por `endTime` + `limit`; incorporar iteracion
   hasta cubrir rango fiscal anual.

## Hallazgos tecnicos Phase 5A (2026-04-24)

1. Se habilita en Core el consumo de `GET /api/v1/bot/order/spotGrid/orders` para traer fills individuales de bots spot-grid.
2. La respuesta del endpoint no esta validada aun con credencial real en entorno del proyecto, por lo que el cliente usa parseo tolerante y fallback de paginacion por ventana temporal.
3. Pendiente smoke test real para confirmar contrato final de campos antes de cerrar Phase 5A.

## Resultado Phase 5G (2026-04-25)

Cobertura API Pionex confirmada como implementada:

| Categoria | Cobertura | Mecanismo |
|---|---|---|
| Fills spot/bot | API-first (`pionex_api`, `pionex_bot_api`) | `sync_pionex` → `_record_trade_fill` con `fiscal_provenance=api` |
| Dual Investment yields | API-first (`pionex_dual_invest_api`) | `sync_pionex` → `_record_dual_income` |
| Staking/Rebase | CSV fallback (`pionex_staking_csv`) | `import_pionex_staking` |
| CommissionIn | CSV fallback (`pionex_commission_csv`) | `import_pionex_others` |
| Futures positions | CSV fallback (`pionex_csv`) | `import_pionex_futures` |
| Deposits/Withdrawals | CSV fallback (`pionex_csv`) | `import_pionex_deposit_withdraw` → `DepositWithdrawal` |

Dedup API/CSV implementado en Phase 5G:
- `BrokerTrade.fiscal_identity_key` = SHA-256[:16] de `(symbol|side|qty|price|ts_minute)`.
- FIFO pool deduplica por esta clave; API gana sobre CSV cuando coinciden.
- `source_comparison` en `reliability` informa de `matched/api_only/csv_only/conflicting_*`.
- Ventas sin coste completo (`gap_reason=balance_transfer_in`) bloquean `resumen_declarable`; `ManualCostBasis` lo desbloquea.
- `schema_version=3`: payload añade `reliability`, `resumen_declarable`, `resumen_diagnostico`.
