# Fase 1 - Ownership dinamico por ingresos recurrentes

## Title

Resolver y congelar repartos compartidos derivados de los doce meses anteriores de ingresos.

## Context

`Ownership` soporta hoy un miembro individual o splits compartidos persistidos. El reparto operativo
del hogar debe evolucionar desde el 61/39 manual a un porcentaje calculado con ingresos recurrentes
reales, mientras los ownership 50/50 de inversiones y propiedades permanecen invariantes. Mutar
`OwnershipSplit` cada mes reinterpretaria el historico y no es aceptable.

## Area

`backend`

## Stack

`core`

## Scope

### In scope

1. Añadir a ownership compartido `allocation_basis` con valores `explicit_split` y
   `recurring_income_12m`; default `explicit_split` para todos los datos existentes.
2. Rechazar `recurring_income_12m` en ownership individual.
3. Modelar reglas explicitas de taxonomia de ingreso ponderable por ownership; al activar una
   configuracion dinamica, `salary` es la seleccion inicial, no una inferencia irreversible.
4. Implementar un resolver unico por ownership y mes.
5. Calcular sobre los doce meses naturales completos anteriores usando transacciones `posted`,
   ownership individual, partidas `flow_family=income` y FX de la fecha del movimiento.
6. Crear snapshot mensual de cabecera y shares por miembro, con ventana, totales, source hash,
   estado de calidad y posibilidad de congelacion.
7. API de preview para mostrar importes, meses cubiertos, movimientos excluidos y porcentaje efectivo.
8. Comando read-only de readiness por usuario/ownership para auditar historico antes de activar.
9. Aislamiento multiusuario, redondeo determinista y tests temporales enero/diciembre.

### Out of scope

1. Activar automaticamente ownership existentes no 50/50.
2. Cambiar el resultado del cierre mensual.
3. Crear configuracion frontend.
4. Usar presupuestos previstos en lugar de ingresos ejecutados.
5. Inferir bonus o ingresos extraordinarios como recurrentes.

## Plan

1. Añadir modelos y migraciones en `memberships` con defaults compatibles.
2. Extraer el resolver a un servicio Core reutilizable por patrimonio, presupuesto y cierre.
3. Implementar agregacion contable y conversion FX sin consultas por movimiento.
4. Implementar snapshots draft/frozen y source hash.
5. Exponer preview/readiness sin mutar ownership durante una lectura.
6. Cubrir fixtures fijos, dinamicos, incompletos, FX y aislamiento.

## Validation

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations memberships
docker compose -f core/docker-compose.yml exec backend python manage.py migrate
docker compose -f core/docker-compose.yml exec backend python manage.py showmigrations memberships
docker compose -f core/docker-compose.yml exec backend python manage.py test memberships accounting
docker compose -f core/docker-compose.yml exec backend ruff check .
docker compose -f core/docker-compose.yml exec backend ruff format --check .
docker compose -f core/docker-compose.yml exec backend mypy .
```

## Required Documentation Updates

- [ ] `core/docs/architecture/architecture.md` - estrategias y snapshots de ownership.
- [ ] `core/docs/architecture/accounting-movements-architecture.md` - fuente de ingresos ejecutados.
- [ ] `core/docs/project-status.md` - cerrar fase y habilitar la siguiente.
- [ ] `docs/architecture/api-registry.md` - preview de reparto dinamico.

## Risks

- Reclasificar movimientos pasados puede cambiar previews no congelados. El snapshot finalizado debe
  preservar el resultado historico.
- Una taxonomia demasiado amplia incorpora bonus. La seleccion inicial se limita a salario y toda
  ampliacion es explicita.
- Consultar doce meses de ledger puede ser costoso. Agregar en base de datos, indexar los filtros
  nuevos y medir numero de consultas.
- Datos incompletos no deben producir falsa precision. El payload distingue `ready`, `provisional` y
  `blocked` con razones trazables.

## Completion Criteria

- [ ] Migraciones aplicadas y verificadas.
- [ ] Existing ownerships retain `explicit_split` without behavioral changes.
- [ ] Dynamic preview uses the immediately preceding 12 complete months.
- [ ] Snapshot percentages reconcile to exactly 100.00%.
- [ ] Frozen snapshots remain unchanged after source edits.
- [ ] Cross-user references and reads are rejected.
- [ ] All validation commands pass.
- [ ] All required documentation updates done.
- [ ] Spec moved to `terminados/`.
- [ ] Commit created (Conventional Commits).
