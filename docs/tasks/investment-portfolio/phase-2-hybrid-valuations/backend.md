# Cartera - Fase 2: valoracion hibrida

## Context
Las posiciones cotizadas necesitan cierres diarios y las agregadas valoraciones manuales. La fuente, fecha y obsolescencia deben ser explicitas.

## Area
`backend`

## Stack
`core`

## Scope
1. Crear `InstrumentPrice`, valoraciones manuales y mapeo confirmado proveedor/instrumento.
2. Extender `market_data_sync` con dataset `instrument_prices` y registro de adaptadores.
3. Antes de elegir proveedor inicial, comparar APIs oficiales por cobertura real, licencia, estabilidad, historico, rate limits y coste; documentar la decision.
4. Reutilizar CoinGecko/CryptoCompare para cripto cuando el contrato sea compatible.
5. Resolver cierre diario, refresh bajo demanda, fallback manual y umbral de stale por tipo.
6. Importar revalorizaciones existentes como fuente historica derivada sin duplicar valor ni modificar asientos.
7. Exponer cobertura/salud y procedencia de cada valor.

## Plan
1. Ejecutar spike de proveedores con una muestra de ISIN/tickers reales.
2. Implementar protocolo, primer adaptador, persistencia y reconciliacion.
3. Probar fallos, remapeo explicito, stale y valores manuales.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio core
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py sync_market_data --datasets instrument_prices --mode reconcile
```

## Required Documentation Updates
- [ ] `core/docs/architecture/architecture.md` - capa de precios y precedencia.
- [ ] `core/docs/operations/dev-setup.md` - configuracion del proveedor.
- [ ] `docs/architecture/api-registry.md` - endpoints consumidos por SaaS.
- [ ] Project status de Core y SaaS.

## Risks
Licencias o simbolos ambiguos pueden invalidar un proveedor. Ninguna coincidencia entra en produccion sin confirmacion de mercado, divisa e instrumento.

## Completion Criteria
- [ ] Cotizados de la muestra reciben cierres diarios o incidencia explicita.
- [ ] Productos custom aceptan valor manual fechado.
- [ ] Fallos externos no borran el ultimo valor valido.
- [ ] Calidad, tests, docs y commit completados.

