# Monthly Close Settlement

Plan canonico para incorporar al cierre mensual una liquidacion opcional por titularidad.

## Objetivo

Al cerrar un mes, explicar y recomendar cuanto dinero debe:

1. permanecer en cada cuenta operativa para cubrir compromisos recurrentes;
2. transferirse a cuentas compartidas con otro reparto, por ejemplo una inversion 50/50;
3. devolverse a las cuentas personales;
4. aportarse desde una cuenta personal cuando un miembro no cubre su parte.

El motor usa el ownership de cada cuenta, movimiento y partida. No introduce una bolsa comun
implícita ni reasigna una nomina individual al ownership de la cuenta donde se cobra.

## Decisiones vinculantes

1. `Ownership` individual sigue representando el 100% de un miembro.
2. Un ownership compartido usa una base de reparto:
   - `explicit_split`: reparto pactado e invariable, como 50/50.
   - `recurring_income_12m`: porcentaje derivado de ingresos recurrentes reales de los doce meses
     completos anteriores al mes calculado.
3. Los splits dinamicos se resuelven por periodo y se congelan al finalizar el cierre. Nunca se
   reescriben porcentajes historicos mutando `OwnershipSplit`.
4. La nomina conserva el ownership individual con independencia de la cuenta receptora.
5. Cada obligacion se reparte con su propio ownership. No se calcula un porcentaje medio entre
   partidas 61/39, 50/50 o individuales.
6. El dinero reservado o aportado termina en una cuenta con ownership compatible con la obligacion.
7. Los gastos puntuales futuros con `mes objetivo` entran en la reserva de ese mes; los que no
   tienen fecha siguen fuera para no inventar una provisión.
8. El usuario puede aplicar un ajuste manual firmado sobre la reserva operativa calculada. Es una
   decisión visible del cierre, no una modificación del presupuesto, y se reparte con la
   titularidad de la cuenta operativa.
9. Los monederos de efectivo siguen siendo activos reales. Las compensaciones ficticias dejan de
   modelarse como liquidez y se incorporan mediante un saldo de apertura o ajuste de liquidacion.
10. La liquidacion esta desactivada por defecto. Un usuario individual, sin ownership, 50/50 para
   todo o con bolsa comun conserva exactamente el cierre actual mientras no la active.
11. La primera version calcula porcentajes dinamicos desde el historico disponible y recomienda
    transferencias; la segunda las crea o concilia en el ledger de forma idempotente y auditable.

## Boundaries

1. Core posee modelos, resolucion de ownership, motor, snapshots, validaciones y API.
2. El frontend SaaS implementa primero la configuracion y la experiencia Direction A.
3. No se crea logica equivalente en el backend SaaS.
4. `core/frontend/` no se replica como espejo; una superficie OSS futura consumira el mismo contrato.
5. No hay gating comercial ni capability nueva: es comportamiento de producto opt-in.

## Version 1 - utilizable con transferencias manuales

| Fase | Objetivo | Specs |
|------|----------|-------|
| 1 | Ownership dinamico y snapshots mensuales | `phase-1-dynamic-ownership/terminados/backend.md` (completada) |
| 2 | Configuracion, ownership presupuestario, destinos y apertura | `phase-2-settlement-inputs/terminados/backend.md` (completada) |
| 3 | Motor de preview, reservas, compensaciones y recomendaciones | `phase-3-settlement-preview/terminados/backend.md` + `phase-3-settlement-preview/terminados/qa.md` (completada) |
| 4 | UX de configuracion y readiness en SaaS | `../../../../docs/tasks/monthly-close-settlement/phase-4-configuration-ux/terminados/frontend.md` (completada) |
| 5 | Resultado de liquidacion dentro del paso Resultado | `../../../../docs/tasks/monthly-close-settlement/phase-5-close-result-ux/terminados/frontend.md` + `qa.md` (completada) |

## Version 2 - ejecucion automatizada

| Fase | Objetivo | Specs |
|------|----------|-------|
| 6 | Crear, enlazar y conciliar transferencias | `phase-6-settlement-execution/terminados/backend.md` + specs SaaS de la misma fase (completada) |

## Orden de ejecucion

Las fases son secuenciales. Las fases 4 y 5 pueden empezar cuando el contrato API de su dependencia
backend este estable, pero no se cierran hasta validar contra Core real en Docker.

## Definition of done del modulo

1. Un ownership dinamico calcula el porcentaje del primer cierre desde el historico previo, sin fase
   transitoria fija.
2. Un caso combinado de gastos ordinarios dinamicos e inversion 50/50 reconcilia por miembro y cuenta.
3. El saldo reservado queda en cuentas con ownership compatible.
4. Los pagos cruzados generan compensaciones explicables sin crear liquidez ficticia.
5. La suma de reservas, asignaciones y transferencias reconcilia al centimo con los saldos observados.
6. Con liquidacion desactivada, payload, lifecycle y UX actuales no sufren regresiones funcionales.
7. Aplicar o reintentar una ruta crea exactamente una transferencia neutral; las aplicaciones
   parciales, conciliaciones y reversos conservan remanente y trazabilidad.

## Reparacion puntual de reinversiones historicas

Una reinversion entre posiciones de inversion no mueve caja ni admite clasificacion funcional.
Si un asiento historico conserva por error la clasificacion de una venta, el cierre tratara el
traspaso interno como ingreso. Revisar primero y escribir solo tras comprobar el resultado:

```bash
python manage.py repair_reinvestment_classification --transaction-id N
python manage.py repair_reinvestment_classification --transaction-id N --apply
```

El comando no modifica importe, cuentas, fechas ni titularidad; borra exclusivamente
`flow_family`, categoria y subcategoria de un asiento que ya sea una `reinversion`.
