# Cartera como sistema de decisión

Plan solicitado el 2026-09-10. Tarea 1 completada y validada; las tareas 2–7 quedan pendientes. Continúa [investment-portfolio](../investment-portfolio/README.md).

## Objetivo
Conectar exposición real, política, decisiones, ejecución y evaluación con el patrimonio completo. La mejora de rentabilidad ajustada a riesgo se debe medir; no es un resultado garantizado.

## Orden y entregables

| Tarea | Resultado | Core | SaaS | Estado |
| --- | --- | --- | --- | --- |
| 1 | Composición coherente | [backend](phase-1-class-composition/terminados/backend.md) | [frontend](../../../../docs/tasks/portfolio-decision-system/phase-1-class-composition/terminados/frontend.md) | ✅ |
| 2 | Liquidez y calidad de decisión | [backend](phase-2-cash-data-quality/backend.md) | [frontend](../../../../docs/tasks/portfolio-decision-system/phase-2-cash-data-quality/frontend.md) | ⚪ |
| 3 | Revisión y contexto UX | [backend](phase-3-decision-review-ux/backend.md) | [frontend](../../../../docs/tasks/portfolio-decision-system/phase-3-decision-review-ux/frontend.md) | ⚪ |
| 4 | Aportaciones por exposición real | [backend](phase-4-exposure-contributions/backend.md) | [frontend](../../../../docs/tasks/portfolio-decision-system/phase-4-exposure-contributions/frontend.md) | ⚪ |
| 5 | Rebalanceo y reducciones | [backend](phase-5-rebalancing-actions/backend.md) | [frontend](../../../../docs/tasks/portfolio-decision-system/phase-5-rebalancing-actions/frontend.md) | ⚪ |
| 6 | Evaluación DCA y buy & hold | [backend](phase-6-strategy-evaluation/backend.md) | [frontend](../../../../docs/tasks/portfolio-decision-system/phase-6-strategy-evaluation/frontend.md) | ⚪ |
| 7 | Decisiones sobre todo el patrimonio | [backend](phase-7-whole-wealth/backend.md) | [frontend](../../../../docs/tasks/portfolio-decision-system/phase-7-whole-wealth/frontend.md) | ⚪ |

## Contrato de la primera entrega
La composición por clases usa tenencias vigentes > desglose manual > clase efectiva. Sus porcentajes usan el valor completo de las posiciones, con `unclassified` para lo no declarado. Geografía/sector/vehículo mantienen su base declarada y cobertura actuales. Se comparan lecturas con la misma fecha y conjunto de posiciones: efectivo y filtros se cierran en las tareas 2 y 3. No se infieren compras correctas de productos mixtos: el algoritmo corresponde a la tarea 4.

## Decisiones de alcance
Los límites anteriores de solo aportaciones y sin comparación DCA describen el MVP, no el objetivo de este plan: las tareas 5 y 6 los amplían por petición del usuario. No hay ejecución automática de broker, motor fiscal ni garantía de rentabilidad. No se rellenan tenencias con estimaciones ni se modifican datos de producción. No incluye refactors generales.

## Validación
Cada entrega requiere pruebas matemáticas y de contrato, calidad Docker de ambos stacks cuando cambia integración, documentación y commits Core/raíz. Las comparaciones requieren cobertura, reglas y ventanas equivalentes antes de interpretar resultados.
