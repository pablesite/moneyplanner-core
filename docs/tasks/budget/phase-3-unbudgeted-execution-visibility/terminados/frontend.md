# Title
Hacer visible en Presupuesto el gasto real fuera de presupuesto

## Context
La UX actual de `Presupuesto` comunica bien el previsto y el ejecutado de las líneas que ya existen en el balance anual, pero no explica de forma clara cuándo el usuario ha gastado en subcategorías o categorías que todavía no ha presupuestado. En ese escenario el usuario puede interpretar que “ha gastado poco” cuando en realidad el sistema solo está mostrando la parte modelada del presupuesto.

La mejora objetivo es que la pantalla enseñe el presupuesto como una herramienta iterativa: puede haber plan parcial, pero el producto debe mostrar siempre el gasto real completo y señalar qué parte está fuera de presupuesto.

## Area
`frontend`

## Stack
`both`

## Scope
1. In scope
   Rediseñar la lectura de `Presupuesto` para distinguir visualmente:
   - previsto
   - ejecutado sobre partidas presupuestadas
   - ejecutado fuera de presupuesto
   Mostrar categorías/subcategorías con gasto real no presupuestado dentro del detalle, con CTA contextual tipo `Añadir al presupuesto` o equivalente.
   Ajustar copy/KPIs para que “completitud” no se interprete como “gasto real total”.
   Aplicar espejo Core en la misma fase.
2. Out of scope
   Refactor amplio no relacionado de `domains/budget`.
   Automatización avanzada de sugerencias presupuestarias multi-paso.
   Cambios cosméticos fuera del flujo de presupuesto.

## Plan
1. Diagnosis
   Auditar `BudgetDashboardView`, `BudgetAnnualSection` y `useBudgetDashboardPage` para separar claramente qué bloques comunican plan, ejecución cubierta y ejecución fuera de presupuesto.
   Identificar dónde la UI actual usa “completitud” para expresar una mezcla de cobertura y ejecución.
2. Change implementation
   Añadir en la cabecera de gastos KPIs explícitos para `Ejecutado real`, `Ejecutado fuera de presupuesto` y/o el equivalente que mejor reduzca ambigüedad.
   En el detalle por categoría, mostrar:
   - subcategorías presupuestadas como hoy
   - un bloque adicional `Detectado en movimientos pero no presupuestado` cuando aplique
   - CTA de alta contextual para convertir una subcategoría detectada en línea anual
   Ajustar barras/captions para que el usuario vea cuándo el ejecutado total supera lo previsto porque hay gasto no modelado, no solo desviación de partidas existentes.
   Replicar el comportamiento equivalente en `frontend/` (Core).
3. Validation
   Añadir tests de frontend que cubran:
   - categoría con líneas presupuestadas y subcategorías ejecutadas no presupuestadas
   - categoría completamente no presupuestada con gasto real
   - visibilidad de CTA contextual
   - coherencia entre Core

## Validation
- `docker compose -f core/docker-compose.yml exec frontend npm run lint`
- `docker compose -f core/docker-compose.yml exec frontend npm run format:check`
- `docker compose -f core/docker-compose.yml exec frontend npm run typecheck`
- `docker compose -f core/docker-compose.yml exec frontend npm run test:unit`
- `docker compose exec frontend npm run lint`
- `docker compose exec frontend npm run format:check`
- `docker compose exec frontend npm run typecheck`
- `docker compose exec frontend npm run test:unit`
- Validación manual:
  El usuario puede identificar claramente el gasto real no presupuestado sin expandir lógica mental adicional.
  Las categorías no presupuestadas pero con gasto ejecutado no desaparecen de la lectura analítica.
  Existe una acción contextual clara para convertir gasto detectado en presupuesto anual.

## Required Documentation Updates
- [ ] `core/docs/project-status.md` — actualizar estado de la fase 3 de Presupuesto
- [ ] `docs/project-status.md` — reflejar el avance del espejo Core
- [ ] `docs/frontend/domain-map.md` — actualizar la descripción del flujo principal de `budget` si se amplía la interacción contextual
- [ ] `core/docs/tasks/budget/phase-3-unbudgeted-execution-visibility/terminados/frontend.md` — mover la spec al cerrar

## Risks
1. Sobrecargar la tarjeta de categoría con demasiados KPIs. Mitigación: priorizar una jerarquía simple y progresiva.
2. Confundir `desviación` con `gasto fuera de presupuesto`. Mitigación: separar copy y métricas explícitamente.
3. Divergencia Core en comportamiento de UI. Mitigación: espejar el mismo contrato y la misma interacción en ambas apps.

## Completion Criteria
- [ ] Presupuesto muestra de forma explícita el gasto real fuera de presupuesto
- [ ] Las categorías/subcategorías con gasto ejecutado pero sin línea anual son visibles en la UI
- [ ] Existe CTA contextual para presupuestar gasto detectado
- [ ] Mirror Core aplicado o excepción documentada
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
