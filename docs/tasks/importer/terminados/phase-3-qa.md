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
- Functional E2E testing of the MoneyWiz import flow.
- Basic accounting regression on movements, accounts and monthly summary.
- Core frontend mirror verification for the import flow.
2. Out of scope
   - Pruebas de packaging de pago o controles de pago.
   - Auditorias de seguridad completas fuera del alcance del bloque.

## Plan
1. Diagnosis
   - Preparar dataset de prueba representativo (CSV MoneyWiz real o anonimizable).
   - Definir baseline de cuentas/saldos antes de importar.
2. Change implementation
- Execute complete preview/commit flow with evidence.
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
8. `docker compose exec frontend npm run lint`
9. `docker compose exec frontend npm run format:check`
10. `docker compose exec frontend npm run typecheck`

Expected outcome: todos los comandos en verde y sin regresiones funcionales relevantes.

## Required Documentation Updates
- [ ] `core/docs/project-status.md` — close QA status of the importing block.
- [ ] `core/docs/roadmap/product-roadmap.md` — reflejar progreso real del importador.
- [ ] `core/docs/architecture/architecture.md` — actualizar si durante QA se ajusta el contrato publico de API.

## Risks
1. Casos borde del CSV (filas incompletas, monedas vacias, transferencias ambiguas) no cubiertos.
2. Falsos positivos de idempotencia en movimientos parecidos.
3. Divergencia Core en UX de resultado del import.

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
1. MoneyWiz is the canonical source of the v1 stream.
2. Excel queda para contraste/validacion.
3. Idempotencia por huella obligatoria.
4. Fallback seguro de categorias es el comportamiento esperado, no error bloqueante por defecto.

## Follow-up abierto (2026-03-18)
1. With the user's actual CSV, the importer preview shows 682 rows with `La fecha no es valida o falta en la fila.` error.
2. The same case generates provisional counts `MoneyWiz source ...`, indicating that the field `Account` of the actual export is not being normalized as we expected.
3. The preview classifies all the rows as `income` and with amount `0.00 EUR`, so tomorrow we have to debug the parser together against that real export before continuing to use the flow in personal production.
