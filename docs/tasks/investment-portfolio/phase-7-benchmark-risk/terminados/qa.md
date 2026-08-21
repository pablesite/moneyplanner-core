# Cartera - Fase 7: QA de benchmark y riesgo

## Context
El riesgo depende de calendarios, frecuencia y calidad de precios. Este gate contrasta el resultado con calculos independientes.

## Area
`qa`

## Stack
`both`

## Scope
Contrastar benchmark con cambios de target, calendarios dispares, fines de semana, FX, series stale, volatilidad anualizada, drawdown y Sharpe contra calculos independientes.

## Plan
1. Preparar series doradas con cambios de estrategia y gaps controlados.
2. Comparar backend y UI con resultados externos.
3. Verificar que cobertura insuficiente degrada a `insufficient`.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio.tests.test_benchmark portfolio.tests.test_risk
docker compose -f docker-compose.dev.yml --env-file .env.dev exec saas_frontend npm run test
```

## Required Documentation Updates
- [x] Arquitectura Core - convenciones validadas.
- [x] Project status de Core y SaaS.

## Risks
Comparar contra una libreria con convenciones distintas puede generar falsos fallos; fijar frecuencia, anualizacion y calendario antes de crear fixtures.

## Completion Criteria
- [x] Fixtures externos y tests de borde pasan.
- [x] La UI no dibuja continuidad donde faltan datos.
- [x] Limitaciones y cobertura quedan documentadas.
- [x] Commit y estado de fase completados.
- [x] Spec movida a `terminados/`.
