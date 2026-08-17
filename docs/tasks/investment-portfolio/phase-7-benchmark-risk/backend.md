# Cartera - Fase 7: benchmark y riesgo progresivo

## Context
Benchmark y riesgo requieren series comparables, convenciones estables y cobertura suficiente; no deben convertir gaps de precios manuales en precision falsa.

## Area
`backend`

## Stack
`core`

## Scope
1. Benchmark estrategico compuesto por targets/clases y version vigente en cada fecha.
2. Preparar benchmark secundario por indice sin hacerlo obligatorio en UI.
3. Calcular exceso de rentabilidad, volatilidad, max drawdown, mejor/peor periodo y Sharpe.
4. Resolver tasa libre de riesgo y frecuencia en un servicio configurable y documentado.
5. Emitir `insufficient` en vez de cifras con cobertura/precios inadecuados.
6. Definir interfaces futuras para beta, correlacion, VaR y contribucion al riesgo sin implementarlas.

## Plan
1. Definir calendario, frecuencia, tasa libre de riesgo y reglas de cobertura.
2. Implementar benchmark versionado y servicios de riesgo puros.
3. Validar contra fixtures externos y exponer contratos quality-aware.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio.tests.test_benchmark portfolio.tests.test_risk
```

## Required Documentation Updates
- [ ] Arquitectura Core: benchmark, convenciones y limites.
- [ ] `docs/architecture/api-registry.md`.
- [ ] Project status de Core y SaaS.

## Risks
Series manuales o asincronas pueden falsear riesgo. Aplicar cobertura minima, calendario comun y disclosure por metrica.

## Backlog relacionado
Rentabilidad historica movil (rolling TWR) para comparar si la cartera mejora o empeora entre periodos equivalentes, con posible capa visual en el grafico de evolucion. Ver `../README.md#backlog-no-planificado`.

## Completion Criteria
- [ ] Benchmark respeta cambios historicos de estrategia.
- [ ] Metricas coinciden con fixtures independientes.
- [ ] Riesgo avanzado puede anadirse sin romper API.
- [ ] Tests, docs y commit completados.
