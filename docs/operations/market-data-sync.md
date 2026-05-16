# Market Data Sync in Core

## Objective
Keep Core market datasets synchronized and observable without manual CRUD flows.

Current managed datasets:
1. `FX` daily rates in `FxRate`
2. `IPC` monthly index (Spain + CCAA) in `InflationIndex`

Provider notes:
1. Fiat FX uses `frankfurter`.
2. Crypto FX uses `coingecko` with automatic fallback to `cryptocompare` when CoinGecko rejects/rate-limits historical requests.

## Canonical Command
From `core/`:

```bash
docker compose exec backend python manage.py sync_market_data --datasets fx inflation --mode reconcile
```

Modes:
1. `reconcile`: fills historical gaps and then refreshes incremental tail.
2. `refresh`: fetches only missing incremental tail.

Examples:

```bash
docker compose exec backend python manage.py sync_market_data --datasets fx --mode refresh
docker compose exec backend python manage.py sync_market_data --datasets inflation --mode reconcile
```

## Worker Service
`docker-compose.yml` includes `market_data_sync` service.

Default behavior:
1. Runs a periodic loop.
2. Executes `sync_market_data --datasets fx inflation --mode reconcile`.
3. Keeps user paths non-blocking if provider fetches fail.

Environment variables:
1. `FX_SYNC_ENABLED=1`
2. `FX_SYNC_INTERVAL_SECONDS=86400`

Useful commands:

```bash
cd core
docker compose up -d market_data_sync
docker compose logs --tail 100 market_data_sync
```

## Observability
Backend status endpoint:

```bash
GET /api/core/market-data/status/
```

Returns:
1. `supported_inflation_regions`
2. per-dataset sync states (`required_start_date`, `covered_until`, `last_attempt_at`, `last_success_at`, `last_error`)
3. latest synced rows for `FX` and `IPC`

Frontend `/data` consumes this endpoint and is now an observational dashboard (no manual add/delete flow for FX/IPC).
