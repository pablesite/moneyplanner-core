## Title
QA importador MoneyWiz v1

## Context
La importacion impacta contabilidad, balances y resumenes mensuales. Esta fase define la validacion funcional y tecnica minima para cerrar el bloque con trazabilidad y evidencia.

## Area
`qa`

## Stack
`both`

## Scope
1. In scope
   - Pruebas E2E funcionales del flujo de importacion MoneyWiz.
   - Regresion contable basica sobre movimientos, cuentas y resumen mensual.
   - Verificacion de espejo frontend Core/SaaS para el flujo de importacion.
2. Out of scope
   - Pruebas de billing o capacidades de pago.
   - Auditorias de seguridad completas fuera del alcance del bloque.

## Plan
1. Diagnosis
   - Preparar dataset de prueba representativo (CSV MoneyWiz real o anonimizable).
   - Definir baseline de cuentas/saldos antes de importar.
2. Change implementation
   - Ejecutar flujo completo preview/commit con evidencias.
   - Verificar clasificacion, cuentas creadas y no duplicacion por reimport.
   - Validar impacto en resumenes contables del periodo.
3. Validation
   - Ejecutar comandos de calidad y tests backend/frontend en contenedores de ambos stacks.

## Validation
1. `docker compose -f core/docker-compose.yml exec backend ruff check .`
2. `docker compose -f core/docker-compose.yml exec backend ruff format --check .`
3. `docker compose -f core/docker-compose.yml exec backend mypy .`
4. `docker compose -f core/docker-compose.yml exec backend python manage.py test accounting`
5. `docker compose -f core/docker-compose.yml exec frontend npm run lint`
6. `docker compose -f core/docker-compose.yml exec frontend npm run format:check`
7. `docker compose -f core/docker-compose.yml exec frontend npm run typecheck`
8. `docker compose exec saas_frontend npm run lint`
9. `docker compose exec saas_frontend npm run format:check`
10. `docker compose exec saas_frontend npm run typecheck`

Expected outcome: todos los comandos en verde y sin regresiones funcionales relevantes.

## Required Documentation Updates
- [ ] `core/docs/project-status.md` — cerrar estado de QA del bloque importador.
- [ ] `core/docs/roadmap/product-roadmap.md` — reflejar progreso real del importador.
- [ ] `core/docs/architecture/architecture.md` — actualizar si durante QA se ajusta el contrato publico de API.

## Risks
1. Casos borde del CSV (filas incompletas, monedas vacias, transferencias ambiguas) no cubiertos.
2. Falsos positivos de idempotencia en movimientos parecidos.
3. Divergencia Core/SaaS en UX de resultado del import.

## Completion Criteria
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)

## Minimum Functional Cases
1. Parseo real de CSV MoneyWiz.
2. Tipos de movimiento: ingreso, gasto, transferencia, inversion y deuda.
3. Categorias no mapeadas con fallback seguro.
4. Reimport idempotente sin duplicados.
5. Cuentas faltantes auto-creadas.
6. Verificacion de impacto en resumenes mensuales.

## Assumptions (Locked)
1. MoneyWiz es la fuente canonica del flujo v1.
2. Excel queda para contraste/validacion.
3. Idempotencia por huella obligatoria.
4. Fallback seguro de categorias es el comportamiento esperado, no error bloqueante por defecto.
