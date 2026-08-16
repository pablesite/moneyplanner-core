# Cartera - Fase 3: QA matematico

## Context
Las formulas financieras pueden producir cifras plausibles aun con signos, fronteras o fechas incorrectos. Este gate valida el motor sin reutilizar sus propios calculos como oraculo.

## Area
`qa`

## Stack
`core`

## Scope
Validar con fixtures independientes: sin flujos, multiples aportaciones, retirada, flujo y valoracion el mismo dia, reinversion interna, dividendos, costes, posicion cerrada, multimoneda, cambio de ownership, valor stale y detalle de unidades parcial.

## Plan
1. Construir resultados esperados fuera del motor.
2. Ejecutar tests de propiedades: reconciliacion, invariancia a transferencias internas y encadenamiento TWR.
3. Comparar una cartera anonimizada real desde 2018 y documentar diferencias.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio.tests.test_performance
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio.tests.test_performance_properties
```

## Required Documentation Updates
- [ ] `core/docs/architecture/architecture.md` - evidencia y tolerancias de calculo.
- [ ] `core/docs/project-status.md` y `docs/project-status.md` - cierre del gate.

## Risks
TWR y XIRR pueden parecer plausibles aun siendo incorrectos. No cerrar con tests que se calculen mediante el mismo codigo productivo.

## Completion Criteria
- [ ] Casos dorados y propiedades pasan.
- [ ] Diferencias Modified Dietz/TWR exacta estan declaradas.
- [ ] Evidencia de validacion real y commit completados.
- [ ] Spec movida a `terminados/`.
