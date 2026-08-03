# Fase 3 - QA del motor de settlement

## Title

Validar matematicamente el motor de preview y su compatibilidad con el cierre existente.

## Context

La liquidacion combina historico contable, ownership dinamico, presupuesto y saldos de varias
cuentas. Los tests de endpoint no bastan: se necesita una matriz de invariantes y regresion que
detecte creacion de dinero, doble conteo y cambios para usuarios no activados.

## Area

`qa`

## Stack

`core`

## Scope

### In scope

1. Fixtures de usuario individual, bolsa comun desactivada, familia 50/50 y familia dinamica.
2. Caso canonico: nominas individuales, gasto ordinario dinamico, reserva ordinaria y asignacion
   50/50 a otra cuenta.
3. Pago compartido desde cuenta personal y pago individual desde cuenta compartida.
4. Miembro con saldo insuficiente y recomendacion inversa.
5. Multiples cuentas con el mismo ownership y seleccion explicita de destino.
6. Enero con ventana cruzando año, años bisiestos, redondeo de tres miembros y FX.
7. Monederos fisicos, baseline de compensacion y ausencia de doble conteo tras fecha de corte.
8. Draft cambiante, finalize congelado, reopen y lock.
9. Missing ownership, missing destination, incompatible target, missing ledger coverage and null data.
10. Regresion del payload y lifecycle actuales con settlement desactivado.
11. Presupuesto plan-managed y partidas term recurrent en el mes correcto.
12. Medicion de queries y tiempo sobre un fixture de al menos 10.000 movimientos.

### Out of scope

1. Validacion visual SaaS.
2. Transferencias creadas automaticamente, cubiertas en fase 6.
3. Datos de produccion o dumps dentro de la suite automatizada.

## Plan

1. Construir builders deterministas de household, ownership, cuentas, presupuesto y ledger.
2. Expresar invariantes como assertions reutilizables, no solo snapshots de payload.
3. Ejecutar matriz por servicio y API.
4. Añadir regresiones a `budget/tests/test_monthly_close.py` y tests focalizados de settlement.
5. Documentar cualquier limitacion real de cobertura antes de habilitar la UX.

## Validation

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py test budget accounting memberships net_worth
docker compose -f core/docker-compose.yml exec backend python manage.py test budget.tests.test_monthly_close
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
```

## Required Documentation Updates

- [ ] `core/docs/tasks/monthly-close-settlement/spec.md` - registrar excepciones descubiertas.
- [ ] `core/docs/project-status.md` - resultado del gate backend.

## Risks

- Fixtures demasiado pequeños pueden ocultar N+1 y errores de signo.
- Assertions sobre totales sin desglose pueden dejar pasar redistribuciones incorrectas entre miembros.
- Tests basados en el porcentaje 61/39 fijo invalidarian el objetivo dinamico; cada periodo debe
  derivar su propio reparto desde ingresos previos.

## Completion Criteria

- [ ] All matrix scenarios pass with per-member and household invariants.
- [ ] The disabled-mode regression suite is green.
- [ ] Query count does not grow linearly with transactions or budget rows.
- [ ] All validation commands pass.
- [ ] All required documentation updates done.
- [ ] Spec moved to `terminados/`.
- [ ] Commit created (Conventional Commits).
