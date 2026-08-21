# Titularidad por lotes — traspaso de contexto

Estado a 2026-08-21. Lo que sigue abierto está en `spec.md`; esto es lo que hace falta
saber para entenderlo sin haber estado en la conversación.

## El problema que resolvió esta tanda

Una posición declaraba su titularidad en tramos: un porcentaje del valor entre dos fechas
(`PositionOwnershipPeriod`). Eso describe bien algo que es de alguien y punto, pero no sabe
contar un bote común. El caso real: bitcoin comprado durante dos años desde cuentas
compartidas 50/50, y a partir de marzo de 2023 desde cuentas individuales, sin separar nunca
las monedas. Ningún porcentaje fijo describe ese bote —la proporción cambia con cada compra,
y se mueve sola con el precio aunque no compres nada, porque un porcentaje del valor no es
una cantidad de monedas.

La pieza clave que lo hizo tratable: **los asientos ya llevan titularidad**
(`LedgerTransaction.ownership_id`), tanto en entradas como en salidas. No hubo que inventar
ninguna regla de reparto; se le pregunta al dato.

## Qué se construyó

`backend/portfolio/lots.py` — bolsillos de unidades por titularidad. Cada entrada va al
bolsillo que la pagó, cada salida sale del que la retiró. Se engancha en
`_ownership_factor`, así que valores, flujos y TWR se corrigen solos sin tocar ninguna
métrica. Solo se activa en posiciones cuyas entradas traen más de una titularidad (3 de 27
en los datos reales); el resto sigue con sus tramos.

Lo que no cuadra no se disimula: una retirada que saca más de lo que su bolsillo tenía se
reparte a prorrata y el sobrante queda en `unreconciled`.

`backend/portfolio/management/commands/split_commingled_ownership.py` — corrige el libro
cuando el asiento dice algo que no pasó. Es un comando y **no una migración** a propósito:
edita el histórico contable de una persona, y una migración correría en cada instalación,
donde esos ids son otras filas. Imprime el plan y no escribe sin `--apply`.

## Bugs que aparecieron por el camino y ya están arreglados

1. **Flujo fantasma al nacer una posición.** El movimiento sintético de cambio de
   titularidad se emitía también en el *primer* tramo, que no es un cambio. Cada posición
   abierta dentro de la ventana sumaba su valor entero como aportación al filtrar por
   miembro: lo aportado por una persona llegaba a superar lo aportado a la cartera entera.
2. **El efectivo de contenedor no tenía dueño.** `cash_ownership_missing` no miraba la
   titularidad, solo si había saldo, así que saltaba en todas. Ahora se resuelve desde el
   `OwnershipLink` del activo. Los flujos de las ramas income/expense no llevaban cuenta y
   caían a cero al filtrar.
3. **Traspaso entre posiciones perdía la pata de salida.** Un asiento con una sola
   dirección hacía que ambas patas se leyeran como entrada.
4. **Comparaciones de patrimonio disparadas** (`frontend`): la serie filtrada por titular se
   componía pidiendo una timeline por posición y sumaba solo las que habían llegado,
   mientras el valor de hoy estaba completo. Media serie no es media verdad.

## Cómo se verifica que el reparto es correcto

La propiedad que lo fija: **la suma de los miembros tiene que dar el total**. Con los datos
reales cuadra al céntimo en lo aportado. Si alguna vez deja de cuadrar, el reparto está
inventando o perdiendo dinero.

Lo que no cuadra por diseño es lo que no es de nadie: una posición sin tramo de titularidad
no sale en la vista de ningún miembro pero sigue dentro del total. Por eso `quality` publica
`ownership_unattributed` y la interfaz lo dice al filtrar.

## Commits de esta tanda

Core: `3c7dda5`, `e06b25e`, `7dc88d9`, `0edfeca`, `00fde7d`
SaaS: `ad430d3`, `a876ad4`, `91ed1de`

## Detalles operativos que ahorran tiempo

- El login por `localStorage` **ya no funciona** para validación en navegador: la sesión
  migró a token en memoria + cookie `HttpOnly` (`arkenstone_refresh`, path `/api/auth/`).
  Sembrar la cookie con `context.addCookies` tampoco bastó. Presupuestar tiempo real si hace
  falta navegador, o validar sobre el composable.
- `./scripts/pre-push-check.sh` es el gate canónico y tarda ~10 min (levanta las dos suites).
- Push: siempre `core` antes que la raíz, porque el puntero del submódulo solo es válido si
  el commit de Core ya existe en GitHub.
