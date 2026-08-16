# Cartera - Fase 3: motor de rendimiento y APIs

## Context
Con flujos y valoraciones disponibles, Core debe producir rendimiento reproducible sin confundir aportaciones con ganancia ni fingir precision por unidades.

## Area
`backend`

## Stack
`core`

## Scope
1. Clasificar flujos externos, internos, ingresos, costes, compras, ventas y revalorizaciones.
2. Calcular valor, aportacion neta, resultado monetario, TWR, MWR/XIRR, P&L analitico y costes.
3. Usar TWR por subperiodos cuando haya valoracion en flujos; Modified Dietz como fallback declarado.
4. Calcular en moneda base, conservar moneda nativa y atribuir activo/FX/total.
5. Ofrecer nominal principal y real por IPC.
6. Aplicar titularidad historica y mantener cobertura de rendimiento separada del detalle por unidades.
7. Exponer overview, positions, timeline, performance y quality bajo `/api/portfolio/`.
8. Cachear solo read models reconstruibles e invalidarlos por cambios de flujo/precio/ownership.

## Plan
1. Especificar signos, frontera de cartera y formulas con fixtures dorados.
2. Implementar servicios puros y despues serializers/endpoints.
3. Comparar resultados con calculos externos controlados y datos reales.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio accounting net_worth core
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend ruff format --check .
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend mypy .
```

## Required Documentation Updates
- [x] `core/docs/architecture/architecture.md` - formulas, cash-flow perimeter y cache.
- [x] `docs/architecture/api-registry.md` - contratos de lectura.
- [x] Project status de Core y SaaS.

## Risks
Un signo o flujo interno mal clasificado invalida toda la serie. Los invariantes de reconciliacion y el QA de esta fase son gate obligatorio.

## Completion Criteria
- [x] Resultados reconciliados y cobertura explicita por metrica.
- [x] No hay N+1 ni consultas sin limite en timeline.
- [x] Quality, tests, docs y commit completados.
