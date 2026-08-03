# Monthly Close Settlement - Spec de producto y dominio

## Problema

Una cuenta compartida puede recibir ingresos con ownership individual y pagar movimientos con
ownership individual o compartido. Hasta el cierre, el saldo fisico no indica cuanto pertenece a
cada miembro ni que parte debe conservarse para obligaciones futuras. El cierre actual reconcilia
liquidez, ingresos y gastos a nivel familiar, pero no calcula la distribucion entre cuentas.

## Resultado esperado

Para cada cierre activado, Core devuelve:

1. el reparto efectivo de cada ownership usado;
2. el saldo economico de apertura y cierre por miembro;
3. las compensaciones derivadas de pagos desde cuentas con ownership distinto al movimiento;
4. la reserva recurrente por partida, ownership y cuenta destino;
5. las transferencias recomendadas entre cuentas;
6. bloqueos y calidad de datos suficientes para explicar por que no puede calcularse una cifra.

## Terminologia

- **Saldo fisico:** saldo observado en una cuenta real.
- **Saldo economico:** parte atribuible a un miembro tras aplicar ownership a los flujos.
- **Cuenta operativa:** cuenta compartida que recibe ingresos y conserva reservas ordinarias.
- **Cuenta destino:** cuenta que debe recibir una reserva o aportacion prevista.
- **Cuenta personal destino:** cuenta que absorbe el excedente de un miembro.
- **Compensacion:** diferencia entre quien adelanto fisicamente un pago y quien debia soportarlo.
- **Reserva:** importe recurrente futuro que debe permanecer o trasladarse antes de repartir excedente.

## Resolucion de ownership

Para un ownership `o`, miembro `m` y mes `t`:

```text
share(o, m, t) =
  1 o 0                                      si o es individual
  OwnershipSplit.percent                    si o usa explicit_split
  income(m, t-12..t-1) / total_income       si o usa recurring_income_12m
```

La ventana dinamica contiene doce meses naturales completos anteriores. Usa movimientos `posted`,
partidas de ingreso en la taxonomia configurada, ownership individual y conversion a moneda base en
la fecha del movimiento. El conjunto inicial incluye `salary`; otras fuentes se habilitan de forma
explicita. Ingresos compartidos, ventas, ganancias de capital y entradas puntuales no se infieren como
ponderables.

## Motor economico

El motor parte del snapshot finalizado anterior o del baseline aceptado durante la activacion. Para
cada miembro:

```text
economic_close = economic_open
               + income_allocated_by_movement_ownership
               - expense_allocated_by_movement_ownership
               + manual_or_opening_adjustments
```

Las transferencias internas no crean ingreso ni gasto. Cambian la localizacion fisica y sirven para
comparar saldos observados con saldos objetivo. Las diferencias por pagos cruzados se presentan con
la transaccion origen siempre que pueda identificarse.

## Reserva y routing

Cada partida recurrente efectiva del siguiente mes aporta:

```text
member_requirement = planned_amount * share(entry.ownership, member, target_month)
```

Se incluyen gastos operativos y compromisos temporales activos. Ahorro e inversion se tratan como
asignaciones a su cuenta destino. Transferencias y partidas puntuales se excluyen por defecto.

La cuenta destino debe tener el mismo vector efectivo de ownership que la obligacion para el mes
objetivo. Una incompatibilidad genera un bloqueo explicito; no se corrige promediando porcentajes.

El solver construye saldos objetivo:

1. reserva ordinaria en la cuenta operativa compatible;
2. aportaciones 50/50 u otros repartos en sus cuentas destino;
3. excedente restante en la cuenta personal configurada de cada miembro;
4. aportacion inversa desde la cuenta personal si el miembro no cubre sus obligaciones.

## Monederos

`Asset.Subcategory.WALLET` representa solo efectivo fisico. En la activacion, el usuario informa el
efectivo real de cada monedero mixto. La diferencia frente al saldo previamente modelado se registra
como ajuste economico de apertura, no como activo. El historico previo permanece intacto y el motor
empieza desde una fecha de corte explicita.

## Lifecycle

1. `disabled`: el endpoint de cierre indica liquidacion inactiva y no exige configuracion.
2. `draft`: el preview se recalcula mientras cambian movimientos, presupuesto o saldos.
3. `finalized`: porcentajes, inputs y resultado se congelan junto al cierre.
4. `locked`: el snapshot es inmutable.
5. `applied` se incorpora en v2 para recomendaciones materializadas como transferencias ledger.

Un fallo o falta de readiness del settlement no rompe el cierre dual existente. El usuario puede
finalizar el cierre familiar sin liquidacion, pero la API y la UI deben indicarlo sin presentar cifras
parciales como exactas.

## Modos no avanzados

1. Usuario individual: liquidacion desactivada, cierre actual.
2. Familia con bolsa comun: liquidacion desactivada, ownership disponible para otros modulos.
3. Familia 50/50: puede permanecer desactivada o activar routing fijo si quiere separar cuentas.
4. Familia con reparto dinamico: activa el perfil y configura ownership, cuentas y fuentes de ingreso.

## Invariantes

1. Todo vector de ownership resuelto suma 100.00% con ajuste determinista de centimos.
2. Los importes monetarios se calculan con `Decimal`; el ultimo miembro estable absorbe redondeos.
3. La suma de saldos economicos de miembros reconcilia con el perimetro fisico mas ajustes explicitos.
4. La suma de recomendaciones netas es igual al saldo distribuible menos saldos objetivo retenidos.
5. Una transferencia interna nunca altera el total economico familiar.
6. Un snapshot finalizado no cambia por movimientos o configuracion editados posteriormente.
7. Ningun usuario puede referenciar ownership, miembros o cuentas de otro usuario.
8. El modo desactivado no introduce requisitos ni cambia resultados actuales.

## Contrato UX

La liquidacion se presenta dentro del paso 4 `Resultado` de `/cierre-mensual`. No se añade otro paso
ni otra ruta principal. La lectura sigue una superficie continua: disponible, reservas/asignaciones,
compensaciones y transferencias. La configuracion avanzada usa un sheet contextual y revelacion
progresiva, componiendo primitivas Direction A y los patrones consolidados de Patrimonio y
Movimientos.

## Fuera de alcance inicial

1. Ejecucion bancaria real.
2. Optimizacion fiscal o juridica entre miembros.
3. Prestamos con interes entre miembros.
4. Conversion automatica entre divisas para ejecutar una recomendacion.
5. Inferir ingresos recurrentes con ML o heuristicas no explicables.
6. Reservar automaticamente gastos puntuales futuros.
