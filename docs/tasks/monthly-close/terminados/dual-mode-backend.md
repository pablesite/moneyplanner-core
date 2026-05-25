# Cierre Mensual — Modo Dual (Backend)

## Context
El cierre mensual existe como wizard de 4 pasos en el frontend pero no tiene modelo propio en backend. Los datos viven dispersos en tres modelos de checkin (`LiquidityMonthlyCheckin`, `AnnualIncomeMonthlyCheckin`, `AnnualExpenseMonthlyCheckin`) y en el ledger contable.

Se necesita una capa backend que soporte dos perfiles de usuario con un solo flujo adaptativo:
- **Power user**: registra cada movimiento → cierre = verificación + sign-off
- **Casual user**: introduce saldos bancarios a fin de mes → sistema sugiere distribución por categorías
- **Usuario mixto**: registra algunos movimientos → sistema completa los huecos

El sistema detecta automáticamente la cobertura (ledger vs checkin vs nada) y adapta lo que muestra y sugiere. No hay selección explícita de "modo".

## Area
`backend`

## Stack
`core`

## Scope

### In scope
1. Modelo `MonthlyClose` (lifecycle wrapper sobre checkins existentes)
2. Nuevo status `estimated` en los tres modelos de checkin (para distinguir distribuciones algorítmicas de datos manuales)
3. Servicio de computación del estado del cierre (`compute_monthly_close_state`)
4. Algoritmo de distribución inteligente (`compute_smart_distribution`) — usa presupuesto como prior, resta movimientos conocidos, distribuye residual proporcionalmente
5. Servicio de aplicación de distribución a checkins (`apply_distribution_to_checkins`)
6. Ciclo de vida: DRAFT → FINALIZED → LOCKED, con reapertura (FINALIZED → DRAFT)
7. Bloqueo de edición de checkins cuando el cierre está FINALIZED/LOCKED
8. API REST: GET/PATCH close, POST finalize/reopen/lock
9. Tests unitarios y de integración API

### Out of scope
- Cambios en frontend (otro agente haciendo refactor)
- Cierre anual (siguiente iteración)
- Transferencias de ownership al cierre (futuro)
- Cambios en la vista de resultados del frontend

## Plan

### 1. Modelo y migraciones
- Añadir `MonthlyClose` en `budget/models.py`
- Añadir choice `estimated` a status en `AnnualIncomeMonthlyCheckin`, `AnnualExpenseMonthlyCheckin` (budget) y `LiquidityMonthlyCheckin` (net_worth)
- Generar y aplicar migraciones

### 2. Servicio principal (`budget/services_monthly_close.py`)
- `compute_monthly_close_state(user, fiscal_year, month)` — orquesta los 3 summary builders existentes, detecta coverage, calcula delta liquidez, genera sugerencias si hay huecos
- `_get_previous_month_liquidity_total(user, fiscal_year, month)` — cadena de fallback: MonthlyClose finalizado → liquidity summary → `Asset.amount`
- `compute_smart_distribution(...)` — algoritmo de distribución proporcional
- `apply_distribution_to_checkins(...)` — persiste sugerencias aceptadas como checkins con status `estimated` o `adjusted`
- `finalize_monthly_close(...)` — DRAFT → FINALIZED, snapshot de totales
- `reopen_monthly_close(...)` — FINALIZED → DRAFT
- `lock_monthly_close(...)` — FINALIZED → LOCKED

### 3. API endpoints (`budget/views_monthly_close.py`)
- `GET /api/budget/monthly-close/{year}/{month}/`
- `PATCH /api/budget/monthly-close/{year}/{month}/`
- `POST /api/budget/monthly-close/{year}/{month}/finalize/`
- `POST /api/budget/monthly-close/{year}/{month}/reopen/`
- `POST /api/budget/monthly-close/{year}/{month}/lock/`

### 4. Bloqueo de checkins
- Validación en vistas PATCH de checkins existentes (`budget/views.py`, `net_worth/views.py`): si existe MonthlyClose FINALIZED/LOCKED para ese mes → 409 Conflict

### 5. Tests
- Unit tests para servicios (cobertura de los casos: sin datos, full ledger, full checkin, mixto, sin presupuesto, delta negativo)
- API tests para endpoints (CRUD, transiciones de estado, bloqueo, auth)

## Validation
```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations budget net_worth
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend python manage.py test budget
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
```

## Required Documentation Updates
- [ ] `core/docs/project-status.md` — marcar cierre mensual como 🔄 En curso, añadir tarea a "En curso"
- [ ] `core/docs/roadmap/product-roadmap.md` — actualizar sección CIERRE DEL MES con decisiones tomadas
- [ ] `core/docs/architecture/architecture.md` — añadir MonthlyClose al modelo de datos si aplica
- [ ] `docs/project-status.md` (Core) — actualizar referencia si aplica

## Risks
- **Performance**: `compute_monthly_close_state` llama a 3 summary builders en secuencia. Aceptable para MVP; cachear en JSONField si se degrada.
- **Rounding**: Distribución proporcional puede generar errores de céntimos. Mitigación: ajustar último ítem para absorber diferencia.
- **Bloqueo de checkins**: Añadir validación en vistas existentes requiere cuidado para no romper el flujo actual. Mitigación: solo bloquear si existe MonthlyClose con status FINALIZED/LOCKED; si no existe, no afecta.
- **Concurrencia**: `get_or_create` en MonthlyClose + UniqueConstraint previene duplicados. `select_for_update` en finalize/lock para race conditions.

## Completion Criteria
- [ ] Modelo MonthlyClose creado con migración aplicada
- [ ] Status `estimated` añadido a los 3 modelos de checkin con migración aplicada
- [ ] Servicio `compute_monthly_close_state` funcional con los 3 modos de cobertura
- [ ] Algoritmo de distribución inteligente funcional (con y sin presupuesto)
- [ ] Ciclo de vida completo: DRAFT → FINALIZED → LOCKED + reopen
- [ ] Bloqueo de checkins cuando cierre FINALIZED/LOCKED
- [ ] 5 endpoints API funcionales y protegidos con auth
- [ ] Tests unitarios y de API pasando
- [ ] Calidad (ruff, mypy) sin errores nuevos
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
