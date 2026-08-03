# Fase 2 - Entradas y activacion de la liquidacion

## Title

Modelar la configuracion opt-in, el ownership presupuestario, las rutas de fondos y el baseline.

## Context

El motor necesita saber que cuentas participan, donde debe terminar cada asignacion y que parte del
saldo inicial corresponde a cada miembro. Las partidas anuales solo conservan hoy `owner_name`, y
los monederos pueden mezclar efectivo fisico con ajustes ficticios. Todos los cambios deben ser
aditivos para que el cierre actual siga funcionando sin configuracion familiar.

## Area

`backend`

## Stack

`core`

## Scope

### In scope

1. Crear un perfil de settlement por usuario, desactivado por defecto, con fecha de activacion,
   moneda base y estado de readiness.
2. Configurar cuentas participantes con roles explicitos: operativa, destino personal, destino de
   asignacion y efectivo fisico; permitir un destino personal principal por miembro y moneda.
3. Añadir FK nullable de ownership a `AnnualIncomeEntry` y `AnnualExpenseEntry`, manteniendo
   `owner_name` como compatibilidad de lectura durante la migracion.
4. Añadir a gastos una cuenta de settlement nullable que represente donde se retiene o transfiere el
   importe previsto. Derivarla desde `source_asset` solo cuando el vinculo contable sea inequivoco.
5. Validar user ownership en todas las relaciones y compatibilidad efectiva ownership/cuenta para el
   mes objetivo mediante el resolver de fase 1.
6. Modelar baseline de activacion por miembro y cuenta, mas ajustes de apertura con suma cero.
7. Soportar la separacion de monederos mixtos: saldo fisico aceptado y diferencia convertida en ajuste
   de apertura, sin reescribir movimientos historicos.
8. Endpoint de readiness que enumere cuentas, destinos, partidas sin ownership, incompatibilidades,
   monederos pendientes y cobertura ledger.
9. Serializers y endpoints de configuracion idempotentes, siempre scoped al usuario.
10. Preservar lineas gestionadas por Mi Plan: ownership y destino derivados se modifican solo desde el
    servicio propietario, no desde Presupuesto.

### Out of scope

1. Calcular recomendaciones de transferencia.
2. Cambiar saldos de activos durante el readiness.
3. Borrar o recategorizar historico de monederos.
4. Hacer obligatorios los nuevos campos para perfiles desactivados.
5. Añadir capability o restriccion por plan comercial.

## Plan

1. Diseñar modelos bajo `budget` para evitar duplicar dominio en SaaS y mantener `MonthlyClose` como
   agregado propietario.
2. Añadir migraciones nullable/default-off y validaciones de tenant.
3. Extender serializers de presupuesto sin romper clientes existentes.
4. Implementar activacion/readiness como operacion explicita y repetible.
5. Añadir baseline/ajustes de apertura y contrato de monederos.
6. Probar usuarios single, bolsa comun, familia fija y familia dinamica.

## Validation

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations budget
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend python manage.py showmigrations budget
docker compose -f core/docker-compose.yml exec backend python manage.py test budget memberships accounting net_worth plan
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
```

## Required Documentation Updates

- [ ] `core/docs/architecture/architecture.md` - perfil, rutas y baseline de settlement.
- [ ] `core/docs/architecture/accounting-movements-architecture.md` - cuentas participantes.
- [ ] `docs/architecture/api-registry.md` - configuracion y readiness.
- [ ] `core/docs/project-status.md` - cerrar fase y habilitar motor.

## Risks

- Una FK directa desde presupuesto a contabilidad puede crear dependencias de migracion. Resolver el
  orden explicitamente y no importar modelos en tiempo de carga.
- `owner_name` puede divergir del ownership estructurado. La API debe declarar el FK como fuente
  canonica cuando exista y no intentar reconciliar nombres heurísticamente.
- Una partida de Plan puede quedar editable por una ruta lateral. Reusar las protecciones de linaje.
- El split de monedero es irreversible si se muta historico. Solo crear baseline y exigir confirmacion.

## Completion Criteria

- [ ] Existing users remain disabled and all existing APIs remain compatible.
- [ ] Readiness explains every missing or incompatible input.
- [ ] Budget ownership and destination reject cross-user data.
- [ ] Managed Plan rows preserve their ownership/destination lifecycle boundary.
- [ ] Wallet activation records physical cash and zero-sum opening adjustments without rewriting history.
- [ ] Migrations applied and verified.
- [ ] All validation commands pass.
- [ ] All required documentation updates done.
- [ ] Spec moved to `terminados/`.
- [ ] Commit created (Conventional Commits).
