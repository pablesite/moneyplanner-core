# Cartera - Fase 6: asignacion y rebalanceo

## Context
La cartera necesita traducir una estrategia versionada a una aportacion ejecutable, sin ventas ni mutaciones silenciosas del presupuesto.

## Area
`backend`

## Stack
`core`

## Scope
1. Estrategias versionadas con targets por clase y posicion.
2. Restricciones por posicion: fraccionable, unidad, minimo, redondeo, exclusion y efectivo residual.
3. Resolver desviaciones para cartera consolidada y filtro de titularidad.
4. Sugerir importe desde Budget/Mi Plan como default editable, sin mutarlos.
5. Optimizar solo nuevas aportaciones; no proponer ventas ni productos.
6. Persistir cesta pendiente, confirmacion parcial y descarte; solo confirmar crea operaciones de fase 5.
7. Exponer explicacion reproducible del reparto.

## Plan
1. Implementar estrategia/targets y restricciones con vigencia temporal.
2. Construir solver determinista y casos de redondeo/minimos.
3. Anadir lifecycle de cestas y materializacion sobre operaciones de fase 5.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio budget plan
```

## Required Documentation Updates
- [ ] Arquitectura Core de portfolio y frontera Budget/Plan.
- [ ] `docs/architecture/api-registry.md`.
- [ ] Project status de Core y SaaS.

## Risks
Redondeos y minimos pueden impedir el optimo. El algoritmo debe terminar, conservar el importe y explicar sobrantes/exclusiones.

## Completion Criteria
- [ ] Targets historicos no cambian al editar estrategia.
- [ ] Reparto respeta restricciones y conserva suma.
- [ ] Una cesta no afecta ledger hasta confirmar.
- [ ] Tests, docs y commit completados.
