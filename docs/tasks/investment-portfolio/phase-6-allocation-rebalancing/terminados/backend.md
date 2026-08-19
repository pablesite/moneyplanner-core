# Cartera - Fase 6: asignacion y rebalanceo

## Context
La cartera necesita traducir una estrategia versionada a una aportacion ejecutable, sin ventas ni mutaciones silenciosas del presupuesto.

## Area
`backend`

## Stack
`core`

## Scope
1. Estrategias versionadas con targets por clase y posicion.
2. Bandas de tolerancia por clase y posicion (minimo/maximo), que son lo que dispara una
   recomendacion. Una banda relativa evita rebalanceos por ruido mejor que un calendario.
3. Restricciones por posicion: fraccionable, unidad, minimo, redondeo, exclusion y efectivo residual.
4. Objetivo de liquidez tactica como linea de la politica, con su banda. El efectivo deja de
   ser el resto de la operacion y pasa a ser una decision con objetivo declarado.
5. Marcar por posicion si admite traspaso sin peaje fiscal. En Espana los traspasos entre
   fondos y planes de pensiones son neutros y el resto tributa al 19-28%, asi que el
   solver debe preferir la bolsa libre antes que la que cuesta dinero. No es el motor
   fiscal completo —eso sigue fuera de alcance— sino el unico dato sin el cual una
   recomendacion puede ser cara.
6. Resolver desviaciones para cartera consolidada y filtro de titularidad.
7. Sugerir importe desde Budget/Mi Plan como default editable, sin mutarlos.
8. Optimizar solo nuevas aportaciones; no proponer ventas ni productos. Se mantiene la
   decision: dirigir la aportacion sostiene las bandas sin peaje fiscal mientras la
   cartera siga creciendo por aportacion, que es el caso hoy.
9. Persistir cesta pendiente, confirmacion parcial y descarte; solo confirmar crea operaciones de fase 5.
10. Exponer explicacion reproducible del reparto.

## Plan
1. Implementar estrategia/targets/bandas y restricciones con vigencia temporal.
2. Construir solver determinista y casos de redondeo/minimos.
3. Anadir lifecycle de cestas y materializacion sobre operaciones de fase 5.

## Nota de producto
Esta fase es la que convierte el seguimiento en un sistema de decision: es donde aterriza
el grueso del objetivo. Las fases siguientes miden si funciona y lo integran, pero no
hacen falta para decidir. Nada de esto sirve, sin embargo, hasta que existan los numeros
objetivo, y esos los escribe el usuario: el sistema dice cuanto te desvias, no de que.

## Validation
```bash
docker compose -f docker-compose.dev.yml --env-file .env.dev exec core_backend python manage.py test portfolio budget plan
```

## Required Documentation Updates
- [x] Arquitectura Core de portfolio y frontera Budget/Plan. Seccion "Investment Portfolio Allocation and Contribution Baskets" en `core/docs/architecture/architecture.md`, con la frontera Budget/Plan como bloque propio: la sugerencia se lee y nunca se escribe.
- [x] `docs/architecture/api-registry.md`.
- [x] Project status de Core y SaaS.

## Risks
Redondeos y minimos pueden impedir el optimo. El algoritmo debe terminar, conservar el importe y explicar sobrantes/exclusiones.

## Completion Criteria
- [x] Targets historicos no cambian al editar estrategia. Editar la version vigente la reescribe; una fecha efectiva nueva crea version, y la cesta guarda contra cual se resolvio.
- [x] Reparto respeta restricciones y conserva suma. Minimos, redondeos, exclusiones, coste sobre `max_cost_share` y `min_line_amount`; lo que no cabe se explica en vez de desaparecer.
- [x] El reparto prefiere posiciones traspasables cuando dos opciones empatan.
- [x] El objetivo de liquidez se respeta como linea de politica, no como sobrante. El efectivo compite como candidato mas, y el enlazado a contenedor cuenta como liquidez real de la cartera.
- [x] Una cesta no afecta ledger hasta confirmar.
- [x] Tests, docs y commit completados. 898 tests de Core en verde.

## Cierre

El punto 7 del scope —sugerir importe desde Budget/Mi Plan— se resuelve leyendo el
presupuesto: `suggested_contribution` suma lo planificado como inversion financiera para
ese mes y abre el simulador con esa cifra. Es de solo lectura por decision de frontera:
Budget decide cuanto puedes invertir y la cartera decide donde va. Si una cesta
reescribiera el presupuesto, el plan describiria lo que paso en vez de lo que se decidio.

Fuera de la spec, la fase dejo dos correcciones que la bloqueaban en datos reales: un
gasto personal pagado desde efectivo enlazado se contaba como coste de invertir (hundia
la rentabilidad con la compra del supermercado) y el `ValidationError` de Django llegaba
al cliente como un 500 sin mensaje, asi que "falta decir de donde sale el dinero" se leia
como una averia.
