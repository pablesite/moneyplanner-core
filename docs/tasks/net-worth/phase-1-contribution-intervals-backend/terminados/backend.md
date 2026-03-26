# Task: Contribution Intervals — Backend

## Title
Intervalos de aportación periódica en activos de inversión (backend)

## Context
Hoy el activo de inversión soporta un único intervalo de aportación periódica codificado como campos planos en el modelo `Asset` (`monthly_contribution_amount`, `investment_contribution_frequency`, `investment_contribution_currency`, `expected_end_date`, `investment_contribution_mode`). El usuario necesita poder definir múltiples intervalos independientes, cada uno con su propia fecha de inicio, fecha de fin, importe, frecuencia y moneda. Esto permite representar estrategias de DCA variables (ej: 300€/mes hasta dic 2025, luego 600€/mes desde mar 2026 sin fecha de fin).

La fecha de apertura del activo (`asset.start_date`) es independiente de cuándo empieza el primer intervalo de aportación. El selector `investment_contribution_mode` desaparece: si el activo tiene intervalos → periódica; sin intervalos → sin aportaciones previstas.

## Area
`backend`

## Stack
`core`

## Scope

### En scope
1. Nuevo modelo `InvestmentContributionInterval` con FK a `Asset`
2. Schema migration + data migration (activos periódicos existentes → un intervalo desde campos legacy)
3. `InvestmentContributionIntervalSerializer` con validación de no-solapamiento
4. `AssetSerializer` actualizado: incluye `contribution_intervals` como lista nested writable (patrón `set` en `update()`)
5. `_build_investment_contribution_schedule()` actualizado para iterar sobre intervalos
6. Tests del nuevo modelo y del servicio de schedule

### Fuera de scope
- Cambios en frontend (Phase 2)
- Eliminar los campos legacy del modelo `Asset` (se conservan dormantes por compatibilidad)
- Cambios en `sync_generated_budget_commitments_for_asset` (consume el output del schedule builder sin cambios)
- Cambios en `services_assets_core.py` projected value (ídem)

## Plan

### 1. Modelo (`core/backend/net_worth/models.py`)

Añadir después del modelo `Asset`:

```python
class InvestmentContributionInterval(models.Model):
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="contribution_intervals",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=20, decimal_places=8, validators=[MinValueValidator(Decimal("0"))]
    )
    frequency = models.CharField(
        max_length=20,
        choices=Asset.InvestmentContributionFrequency.choices,
        default=Asset.InvestmentContributionFrequency.MONTHLY,
    )
    currency = models.CharField(max_length=3, null=True, blank=True)

    class Meta:
        ordering = ["start_date"]

    def clean(self) -> None:
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("end_date must be >= start_date")
```

### 2. Migrations

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations net_worth
```

Crear adicionalmente una **data migration** manual (`0XXX_migrate_legacy_contribution_intervals.py`):

```python
def migrate_legacy_intervals(apps, schema_editor):
    Asset = apps.get_model("net_worth", "Asset")
    Interval = apps.get_model("net_worth", "InvestmentContributionInterval")
    for asset in Asset.objects.filter(
        investment_contribution_mode="periodic_contribution",
        monthly_contribution_amount__isnull=False,
    ).exclude(monthly_contribution_amount=0):
        Interval.objects.create(
            asset=asset,
            start_date=asset.start_date,
            end_date=asset.expected_end_date,
            amount=asset.monthly_contribution_amount,
            frequency=asset.investment_contribution_frequency or "monthly",
            currency=asset.investment_contribution_currency or None,
        )
```

### 3. Serializer (`core/backend/net_worth/serializers.py`)

**Nuevo `InvestmentContributionIntervalSerializer`:**

```python
class InvestmentContributionIntervalSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentContributionInterval
        fields = ["id", "start_date", "end_date", "amount", "frequency", "currency"]
```

**En `AssetSerializer`:**

- Añadir campo: `contribution_intervals = InvestmentContributionIntervalSerializer(many=True, required=False)`
- Añadir en `fields`: `"contribution_intervals"`
- En `validate()`: verificar no-solapamiento de intervalos (si `contribution_intervals` está en attrs)
- En `create()`: tras crear el asset, crear los intervalos de `contribution_intervals`
- En `update()`: usar patrón `set` — eliminar los intervalos existentes y recrear desde el payload

**Validación de no-solapamiento:**
```python
def _validate_no_overlap(intervals_data):
    sorted_intervals = sorted(intervals_data, key=lambda x: x["start_date"])
    for i in range(len(sorted_intervals) - 1):
        current_end = sorted_intervals[i].get("end_date")
        next_start = sorted_intervals[i + 1]["start_date"]
        if current_end is None or current_end >= next_start:
            raise serializers.ValidationError(
                "Los intervalos de aportación no pueden solaparse."
            )
```

### 4. Schedule builder (`core/backend/net_worth/services_assets_budget.py`)

Modificar `_build_investment_contribution_schedule()`:

```python
def _build_investment_contribution_schedule(*, asset, as_of_date=None, horizon_end_date=None):
    if asset.category != Asset.AssetCategory.INVESTMENTS:
        return []

    intervals = list(asset.contribution_intervals.all())
    if not intervals:
        # Legacy fallback: activos no migrados (no debería ocurrir tras data migration)
        return _build_legacy_schedule(asset=asset, as_of_date=as_of_date, horizon_end_date=horizon_end_date)

    schedule = []
    for interval in intervals:
        schedule.extend(
            _build_interval_schedule(
                interval=interval,
                asset_currency=asset.currency,
                as_of_date=as_of_date,
                horizon_end_date=horizon_end_date,
            )
        )
    return sorted(schedule, key=lambda x: x[0])
```

Extraer la lógica actual de `_build_investment_contribution_schedule` en `_build_legacy_schedule` (sin cambios funcionales).

Crear `_build_interval_schedule(interval, asset_currency, as_of_date, horizon_end_date)` que aplica la misma lógica de iteración que el schedule actual pero usando los campos del `InvestmentContributionInterval`.

### 5. Tests (`core/backend/net_worth/tests/`)

Añadir o extender tests para:
- Creación de asset con 0, 1 y N intervalos via API
- Validación de solapamiento en serializer
- `_build_investment_contribution_schedule` con múltiples intervalos
- Data migration: activos legacy generan exactamente un intervalo correcto
- `sync_generated_budget_commitments_for_asset` con múltiples intervalos produce entradas anuales correctas

## Validation

```bash
# Migrations
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations net_worth
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend python manage.py showmigrations net_worth

# Calidad
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .

# Tests
docker compose -f core/docker-compose.yml exec backend python manage.py test net_worth
```

## Required Documentation Updates

- [ ] `core/docs/project-status.md` — actualizar estado de la tarea a ✅ y mover spec a `terminados/`
- [ ] `core/docs/architecture/architecture.md` — si se añade endpoint/campo nuevo a la API pública de assets, documentar

## Risks

- **Data migration irreversible:** si se pierde el mapping legacy→interval, los activos pierden su configuración de aportación. Mitigación: verificar en test que todos los activos periódicos tienen exactamente un intervalo tras la migración.
- **Campos legacy dormantes:** `services_assets_budget.py` y `services_assets_core.py` todavía referencian los campos legacy como fallback. Asegurar que el fallback no se activa para activos recién creados (deben crear intervalos, no usar campos legacy).
- **N+1 en schedule builder:** `asset.contribution_intervals.all()` se llama para cada activo en listados masivos. Mitigación: usar `prefetch_related("contribution_intervals")` en las queries de assets que llamen al builder.

## Completion Criteria

- [ ] Modelo `InvestmentContributionInterval` creado con migración schema aplicada
- [ ] Data migration ejecutada y todos los activos periódicos pre-existentes tienen ≥1 intervalo
- [ ] API `PATCH /api/net-worth/assets/{id}/` acepta y persiste `contribution_intervals`
- [ ] Solapamiento de intervalos devuelve 400 con mensaje descriptivo
- [ ] `_build_investment_contribution_schedule` usa intervalos (no campos legacy) para activos con intervalos
- [ ] Tests de backend pasan sin regresiones
- [ ] Calidad (ruff + mypy) sin errores
- [ ] Spec movida a `terminados/`
- [ ] Commit Conventional: `feat(net-worth): multi-interval investment contribution schedule`
