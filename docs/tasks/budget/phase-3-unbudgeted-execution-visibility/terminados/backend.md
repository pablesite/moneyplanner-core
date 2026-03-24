# Title
Exponer cobertura presupuestaria y gasto fuera de presupuesto en Presupuesto

## Context
La vista de `Presupuesto` ya combina plan anual y ejecución real desde `accounting`, pero hoy el sistema solo representa con claridad lo que tiene una línea anual explícita en `budget`. Si el usuario gasta en una subcategoría real que no ha presupuestado todavía, ese gasto queda fuera del detalle de categoría/subcategoría y la UX puede inducir a pensar que el ejecutado real es menor de lo que realmente fue.

Este comportamiento rompe la lectura del producto en una situación muy habitual: presupuesto parcial o iterativo. La lógica de “qué parte del gasto real está cubierta por presupuesto” pertenece al dominio Core y debe estar disponible de forma reutilizable para Core frontend y espejo SaaS.

## Area
`backend`

## Stack
`core`

## Scope
1. In scope
   Definir y exponer un resumen canónico de cobertura presupuestaria para gastos, distinguiendo entre:
   - ejecución sobre líneas presupuestadas
   - ejecución real fuera de presupuesto
   - cobertura por categoría y subcategoría
   Reutilizar la taxonomía existente de `budget` y `accounting` sin introducir una taxonomía paralela.
   Hacer que el contrato permita a frontend mostrar categorías/subcategorías con gasto real aunque no exista `AnnualExpenseEntry` para ellas.
   Diseñar el payload para que el espejo SaaS pueda consumirlo sin recalcular reglas de dominio en el frontend.
2. Out of scope
   Cambios de capabilities o packaging.
   Replantear la taxonomía funcional de ingresos/gastos.
   Automatizar creación masiva de presupuesto desde el backend en esta fase.

## Plan
1. Diagnosis
   Auditar los helpers actuales de `budget/services.py` y el uso cruzado de `accounting` para identificar qué parte de la agregación ya existe y qué parte sigue implícita en frontend.
   Confirmar precedencia entre ledger categorizado, fallback legacy y líneas anuales inexistentes.
2. Change implementation
   Introducir un summary orientado a UX de cobertura presupuestaria por mes/YTD para gastos, incluyendo:
   - categorías con presupuesto
   - categorías con gasto real sin presupuesto
   - subcategorías con gasto real sin presupuesto dentro de una categoría existente
   - totales diferenciados de `planned`, `executed_budgeted`, `executed_unbudgeted` y `executed_total`
   Exponer el contrato mediante endpoint o ampliar el summary existente de budget si encaja mejor en la API actual.
   Mantener el cálculo centralizado en backend para evitar divergencia Core/SaaS.
3. Validation
   Añadir tests de servicio/API que cubran:
   - gasto ejecutado en subcategoría no presupuestada dentro de categoría ya planificada
   - gasto ejecutado en categoría completa no presupuestada
   - convivencia de ledger categorizado y fallback legacy
   - ausencia de doble conteo entre gasto presupuestado y no presupuestado

## Validation
- `docker compose -f core/docker-compose.yml exec backend ruff check .`
- `docker compose -f core/docker-compose.yml exec backend ruff format --check .`
- `docker compose -f core/docker-compose.yml exec backend mypy .`
- `docker compose -f core/docker-compose.yml exec backend python manage.py test budget accounting`
- Validación manual:
  El payload distingue explícitamente entre gasto ejecutado presupuestado y no presupuestado.
  Una subcategoría con gasto real pero sin línea anual aparece en el summary sin requerir cálculo derivado en frontend.

## Required Documentation Updates
- [ ] `core/docs/project-status.md` — actualizar la fase 3 de Presupuesto al cerrarla
- [ ] `core/docs/architecture/architecture.md` — reflejar el contrato canónico si se añade o cambia API/summaries de budget
- [ ] `docs/architecture/api-registry.md` — documentar el endpoint/summary consumido por SaaS si cambia el contrato público
- [ ] `docs/project-status.md` — reflejar el avance del espejo SaaS cuando se cierre la tarea
- [ ] `core/docs/tasks/budget/phase-3-unbudgeted-execution-visibility/terminados/backend.md` — mover la spec al cerrar

## Risks
1. Doble conteo entre ledger categorizado y fallback legacy. Mitigación: mantener precedencia explícita y tests de regresión.
2. Inflar demasiado el payload con detalle innecesario. Mitigación: enviar solo los campos que el frontend necesita para explicar cobertura y CTA de presupuestación.
3. Reproducir lógica de frontend en backend de forma acoplada a la UI actual. Mitigación: definir el contrato en términos de dominio (`budgeted` vs `unbudgeted`), no de componentes concretos.

## Completion Criteria
- [ ] Existe contrato backend canónico para cobertura presupuestaria y gasto fuera de presupuesto
- [ ] El contrato distingue `executed_budgeted`, `executed_unbudgeted` y `executed_total`
- [ ] Tests de `budget/accounting` cubren los casos de presupuesto parcial sin doble conteo
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
