# Phase 5 — Informe fiscal Pionex v2 (fiabilidad AEAT)

## Context

El MVP cerrado en Phases 1-4 no es fiable para presentar a la AEAT. Los problemas
identificados por el usuario y confirmados en la exploración (2026-04-24):

1. FX diario demasiado impreciso para criptos volátiles.
2. Cobertura Pionex incompleta: símbolos hardcodeados (BTC/ETH), bots sin fills
   individuales, validación cruzada inexistente.
3. Sin trazabilidad en sync: sólo `last_sync_stats` del último run.
4. `exchange_buy = "missing"` renderizado literal, con `cost_eur = 0` que sesga
   al alza el informe.
5. Bots grid sólo llegan como resumen (`realized_profit`). No pasan por FIFO.
6. Sin explicabilidad venta→lotes ni export para asesor/AEAT.

Phase 5 resuelve estos puntos sólo para Pionex. Binance queda para Phase 6.

## Decisiones tomadas con el usuario (2026-04-24)

1. **FX por minuto** con klines públicas de Binance (sin auth) + caché persistente.
2. **Bots grid FIFO estricto**: fills individuales como `BrokerTrade`, integrados
   al pool FIFO global. `BotNetResult` queda como fila de conciliación.
3. **Explicabilidad FIFO completa**: matching venta→lotes + export CSV/PDF.

## Tasks

| Orden | Spec | Tipo | Área | Resumen |
|-------|------|------|------|---------|
| 1 | [fase-a-cobertura-pionex.md](fase-a-cobertura-pionex.md) | Agente | backend | Auto-descubrimiento de símbolos, fills de bot vía API, validación de saldos |
| 2 | [fase-b-sync-runs.md](fase-b-sync-runs.md) | Agente | backend | Historial `BrokerSyncRun` + endpoints drill-down |
| 3 | [fase-c-fx-intradia.md](fase-c-fx-intradia.md) | Agente | backend | `intraday_fx` con klines 1m + `MarketRateSnapshot` + `price_eur`/`fee_eur` en `BrokerTrade` |
| 4 | [terminados/fase-d-fifo-matching.md](terminados/fase-d-fifo-matching.md) | Agente | backend | Matching venta→lotes, `gap_reason` tipado, `ManualCostBasis` |
| 5 | [terminados/fase-e-export-aeat.md](terminados/fase-e-export-aeat.md) | Agente | backend | Export CSV/PDF anexo AEAT |
| 6 | [fase-f-frontend-drilldown.md](fase-f-frontend-drilldown.md) | Manual | frontend | Drill-down sync runs, matching visible, modal de coste manual |

El orden es secuencial para backend (A→B→C→D→E). Fase F puede arrancar en
paralelo con D/E una vez el contrato API de D esté cerrado.

## Entregables comunes

- Migraciones generadas y aplicadas.
- Tests dentro de contenedor (`python manage.py test broker_integrations`).
- Ruff/mypy verdes.
- Documentación canónica actualizada (ver lista en cada spec).
- `project-status.md` con cada task marcada al cerrarse.
- Spec movida a `terminados/` al completar.
