# Phase 5D — FIFO con matching completo y categorización de gaps

## Context

`services/fifo_calculator.py` genera hoy una lista de lotes realizados
(línea 80-94) pero no enlaza cada venta con los lotes de compra que consume.
Cuando la cantidad vendida supera el pool disponible, emite un "lote fantasma"
con `exchange_buy: "missing"` y `cost_eur: 0` (línea 101-121), lo que:

1. Sesga al alza la ganancia del informe (todo se convierte en plusvalía).
2. Muestra al usuario la cadena literal `"missing"` sin ningún contexto.

Phase 5D reescribe la salida del FIFO para exponer el matching venta→lotes,
categoriza los gaps con razones explícitas y habilita asignación manual de
coste de adquisición cuando la compra original ocurrió antes del período
sincronizado.

## Area

`backend`

## Stack

`core`

## Scope

### In scope

- Reescribir `fifo_calculator.py` para emitir una estructura `FifoSaleMatch`
  por cada SELL, con los lotes consumidos y sus PKs.
- Usar los `price_eur`/`fee_eur` ya poblados por Phase 5C (no convertir otra vez).
- Asignar `fee_eur` proporcionalmente entre lotes al calcular `gain_loss_eur`.
- Nuevo modelo `ManualCostBasis` para coste de adquisición previo al período.
- Enum `gap_reason`: `null` | `pre_period_buy` | `missing_data` |
  `balance_transfer_in`. Nunca más `exchange_buy: "missing"` plano.
- `fiscal_report.py` actualiza la estructura JSON para exponer matches y gaps
  tipados.

### Out of scope

- Export CSV/PDF (Phase 5E).
- Cambios frontend (Phase 5F).

## Plan

### 1. Diagnosis

- Releer la salida actual de `fiscal_report.py` (`ganancias_perdidas_trades[].lotes`).
- Identificar consumidores de esa estructura (endpoint, tests, frontend) para
  planear retrocompatibilidad.

### 2. Change implementation

**`models.py`**
```python
class ManualCostBasis(models.Model):
    ownership = models.ForeignKey("memberships.Ownership", on_delete=models.CASCADE)
    asset = models.CharField(max_length=10)
    quantity = models.DecimalField(max_digits=24, decimal_places=10)
    quantity_remaining = models.DecimalField(max_digits=24, decimal_places=10)
    acquired_at = models.DateTimeField()
    cost_eur = models.DecimalField(max_digits=24, decimal_places=10)
    exchange_origin = models.CharField(max_length=20, default="external")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["ownership", "asset", "acquired_at"])]
```
Migración.

**`services/fifo_calculator.py`** — reescribir salida:
```python
@dataclass
class MatchedLot:
    buy_trade_id: int | None
    manual_cost_basis_id: int | None
    buy_date: datetime | None
    buy_exchange: str | None  # 'pionex' | 'binance' | 'manual' | None
    buy_symbol: str | None
    quantity_consumed: Decimal
    unit_price_eur: Decimal
    cost_eur: Decimal
    fee_eur_allocated: Decimal
    gain_loss_eur: Decimal
    hold_days: int

@dataclass
class FifoSaleMatch:
    sell_trade_id: int
    sell_date: datetime
    sell_exchange: str
    sell_symbol: str
    quantity_sold: Decimal
    proceeds_eur: Decimal
    fee_eur: Decimal
    matched_lots: list[MatchedLot]
    gap_quantity: Decimal
    gap_reason: str | None  # 'pre_period_buy' | 'missing_data' | 'balance_transfer_in'
```

Algoritmo actualizado:
1. Cargar `BrokerTrade` del ownership + `base_asset` del año, orden cronológico.
2. Pool inicial alimentado con `ManualCostBasis` pendientes (quantity_remaining>0)
   del ownership/asset, ordenados por `acquired_at`.
3. Procesar cada SELL consumiendo del pool. Por cada consumo emitir `MatchedLot`.
4. Si el SELL queda parcialmente descubierto:
   - Si el asset tiene `ManualCostBasis` totalmente agotado **pero** el gap
     corresponde a cantidad adquirida antes del año fiscal (heurística: asset
     con balance_mismatch detectado en Phase 5A con signo positivo) →
     `gap_reason = "pre_period_buy"`.
   - Si `balance_reconciliation` reportó un `balance_mismatch` concreto →
     `gap_reason = "missing_data"`.
   - En otro caso → `gap_reason = "balance_transfer_in"`.
5. Persistir el consumo en `ManualCostBasis.quantity_remaining` (idempotencia
   garantizada reseteando antes de cada cálculo).

**`services/fiscal_report.py`**
- Salida `ganancias_perdidas_trades[asset].sales` con la lista de `FifoSaleMatch`.
- Mantener agregado por asset (`valor_transmision_eur`, `valor_adquisicion_eur`,
  `ganancia_eur`, `perdida_eur`) calculado desde los matches.
- Sustituir `lotes[].exchange_buy = "missing"` por `sales[].gap_reason`.
- Añadir aviso específico por cada `gap_reason` en `avisos[]`.

**`views.py` + `serializers.py`**
- Actualizar serializer de `fiscal-report` para exponer la nueva estructura.
- Nuevo CRUD ligero para `ManualCostBasis`:
  - `POST /api/v1/broker/manual-cost-basis/`
  - `GET  /api/v1/broker/manual-cost-basis/?asset=BTC`
  - `DELETE /api/v1/broker/manual-cost-basis/<id>/`

### 3. Validation

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations broker_integrations
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
docker compose -f core/docker-compose.yml exec backend python manage.py test broker_integrations
```

**Tests unitarios** `fifo_calculator`:
- Una SELL cubre 2 BUYs parciales; se emiten 2 `MatchedLot` con cantidades
  correctas.
- `fee_eur` del SELL se reparte proporcionalmente en `fee_eur_allocated`.
- `ManualCostBasis` se consume antes de BUYs reales si `acquired_at` es
  anterior.
- Gap descubierto → `gap_reason="pre_period_buy"` por defecto; cambia a
  `missing_data` si `balance_reconciliation` lo marca.
- Fills de bot (source=`pionex_bot_api`, FK `bot` seteada) entran al pool
  junto a los spot manuales.

**Smoke test manual**: generar informe fiscal 2025 y verificar que:
- Cada venta con `gap_quantity>0` expone `gap_reason` tipado, nunca `"missing"`.
- Añadir un `ManualCostBasis` vía endpoint para un asset con gap y regenerar
  → el gap se reduce o desaparece.

## Required Documentation Updates

- [ ] `core/docs/architecture/architecture.md` — documentar `ManualCostBasis`
      y nuevas estructuras de salida.
- [ ] `core/docs/architecture/api-registry.md` — endpoints CRUD de
      `manual-cost-basis` y nueva shape de `fiscal-report`.
- [ ] `core/docs/frontend/fiscal-report-ux-notes.md` — actualizar notas sobre
      explicabilidad y remoción del literal `"missing"`.
- [ ] `core/docs/project-status.md` — marcar Phase 5D cerrada.

## Risks

1. **Breaking change en shape del endpoint** `fiscal-report`: versionar el
   response con un flag (`schema_version: 2`) y mantener compatibilidad en
   frontend (Phase 5F migra).
2. **Asignación proporcional de fees**: decidir y documentar política clara
   (proporcional al coste o a la cantidad). Aplicar consistentemente en tests.
3. **Estado mutable de `ManualCostBasis.quantity_remaining`**: recalcular
   siempre desde cero al generar el informe (no depender de estado previo)
   para que sea reproducible.

## Completion Criteria

- [ ] Migración aplicada y verificada.
- [ ] FIFO emite `FifoSaleMatch` con `matched_lots` poblados correctamente.
- [ ] Ningún lote emite `exchange_buy="missing"` plano.
- [ ] `ManualCostBasis` consumible desde FIFO y manejable vía endpoints.
- [ ] Tests unitarios pasan.
- [ ] Documentation updates done.
- [ ] Spec movida a `terminados/`.
- [ ] Commit: `feat(broker-integrations): expose FIFO sale-lot matching with typed gap reasons`.
