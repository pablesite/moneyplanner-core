# Sincronizacion FX en Core

## Objetivo
Mantener poblada la tabla `FxRate` para las divisas no base usadas por activos y pasivos del modulo de patrimonio.

## Comando manual
Desde `core/`:

```bash
docker compose exec backend python manage.py sync_fx_rates --for-active-positions --quote-currency EUR
```

Eso inspecciona activos y pasivos activos, detecta la fecha historica mas antigua por divisa y rellena el historico faltante hasta hoy.

## Rango explicito
Para forzar unas divisas concretas:

```bash
docker compose exec backend python manage.py sync_fx_rates --currencies USD BTC ETH --quote-currency EUR --start-date 2025-03-03
```

## Fuentes
- `USD` y otras fiat: `Frankfurter`
- `BTC` y `ETH`: `CoinGecko`

## Backfill automatico
Al crear o actualizar un activo o un pasivo en divisa distinta de la moneda base del usuario, Core intenta completar hacia atras el historico que falte para esa posicion.

Si la fuente externa falla, la creacion de la posicion no se bloquea; el backfill queda como mejor esfuerzo y puede reintentarse con el comando anterior.

## Tarea automatica diaria
`core/docker-compose.yml` incluye un servicio `fx_sync` que ejecuta una sincronizacion al arrancar y la repite cada 24 horas por defecto.

Variables disponibles en `core/backend/.env`:
- `FX_SYNC_ENABLED=1`
- `FX_SYNC_QUOTE_CURRENCY=EUR`
- `FX_SYNC_INTERVAL_SECONDS=86400`

Comandos utiles:

```bash
cd core
docker compose up -d fx_sync
docker compose logs --tail 100 fx_sync
```
