# Modulo `investment-portfolio` - Cartera de inversion

Plan canonico aprobado el 2026-08-16 para convertir los activos y movimientos de inversion existentes en una cartera familiar profesional. Las fases son secuenciales y verticales: dominio y calculos en Core; primera UI completa en el frontend SaaS.

## Objetivo

Responder, con trazabilidad y calidad explicita, a cuatro preguntas:

1. Cuanto vale la cartera y cuanto se ha aportado.
2. Que rentabilidad ha obtenido, separando flujos, costes, ingresos y divisa.
3. Como esta distribuida frente a la estrategia familiar.
4. Como repartir una nueva aportacion para acercarse al objetivo sin recomendar ventas.

## Base existente auditada

1. El usuario principal dispone de 23 activos de inversion, 905 movimientos de aporte/retirada/reinversion desde 2018 y 1.023 revalorizaciones.
2. Cada posicion existente esta enlazada a `Asset` y `LedgerAccount`; el ledger sigue siendo la fuente de verdad monetaria.
3. Los flujos historicos conservan fecha e importe, pero muchos fondos/ETF no conservan participaciones. BTC/ETH si contienen cantidades.
4. La rentabilidad historica puede aprovechar flujos y valoraciones aunque el detalle por unidades empiece mas tarde.
5. Las compras historicas banco -> activo no se reescriben: Cartera las interpreta como `funded_purchase` atomicas.

## Decisiones vinculantes

### Perimetro y ownership

1. Existe una sola cartera familiar global por usuario, con contenedores (broker, banco, exchange, wallet, pension, plataforma) como agrupaciones y filtros.
2. Incluye todas las inversiones financieras y el efectivo asociado; excluye inmuebles directos y bienes tangibles.
3. La vista admite filtro por titularidad. Los cambios de titularidad se versionan por fecha y no reescriben el pasado.
4. Las posiciones cerradas se archivan, siguen computando en el historico y pueden reabrirse.

### Datos, operaciones y valoracion

1. Una posicion puede ser `value_based` o `units_based`. No se inventan unidades historicas.
2. Se mantienen dos ejes de calidad: `performance_coverage` para flujos/valoraciones y `position_detail_coverage` para unidades/precios/operaciones.
3. Los precios son hibridos: cierre diario automatico para instrumentos confirmados y valoracion manual para productos no cotizados o agregados.
4. Las valoraciones antiguas se conservan con fecha y umbrales de obsolescencia por producto; nunca se excluyen silenciosamente del total.
5. Las operaciones nuevas siguen transferencia a efectivo del contenedor y compra posterior. Dividendos/intereses aumentan efectivo y forman parte de la rentabilidad total.
6. Compras/ventas guardan unidades, precio, divisa y costes. Coste y P&L son analiticos, no fiscales.
7. El CSV generico usa staging, mapeo, preview, idempotencia y conciliacion asistida. Solo un identificador externo exacto permite deduplicacion automatica.
8. Eventos corporativos iniciales: split/contrasplit, cambio de identificador, traspaso entre posiciones y ajuste manual auditado.

### Rendimiento, estrategia y riesgo

1. El hero muestra valor y TWR al mismo nivel; resultado monetario y aportaciones netas son contexto secundario.
2. TWR neutraliza flujos externos; MWR/XIRR refleja importe y momento de los flujos. Si falta valoracion en un flujo, se usa Modified Dietz y se declara la estimacion.
3. La rentabilidad principal es nominal, en moneda base y neta de costes explicitos. Se ofrecen vista real por IPC, resultado local y atribucion FX.
4. Rentabilidad bruta y costes aparecen en detalle. Gastos ya embebidos en un valor liquidativo no se descuentan dos veces.
5. La asignacion objetivo tiene dos niveles: clase de activo y posicion. Toda estrategia se versiona por fecha.
6. El rebalanceo usa solo nuevas aportaciones, respeta unidades/minimos/exclusiones y deja el sobrante en efectivo.
7. Aceptar una propuesta crea una cesta pendiente. Solo la confirmacion de ejecucion crea operaciones contables reales.
8. El benchmark principal es estrategico y compuesto segun la asignacion vigente. Un indice global secundario queda preparado.
9. Riesgo inicial: volatilidad, drawdown, mejor/peor periodo y Sharpe solo con cobertura suficiente. Beta, correlaciones, VaR y contribucion al riesgo quedan preparados, no implementados.

### UX y limites

1. Ruta SaaS independiente `/cartera`, perteneciente a la familia Patrimonio. No se anade una sexta opcion movil.
2. Debe existir retorno persistente a Patrimonio, conservar contexto y respetar el historial del navegador.
3. Desktop usa tablas; movil usa listas compactas y sheets sin scroll horizontal a 360 px.
4. Alertas iniciales viven dentro de Cartera y cubren calidad, concentracion, desviacion, exceso de efectivo y cestas pendientes.
5. Fuera de alcance: trading, recomendaciones de productos, ventas de rebalanceo, fiscalidad/FIFO, conectores de broker y riesgo avanzado.
6. Matiz sobre fiscalidad: el motor fiscal sigue fuera, pero desde la fase 6 cada posicion
   declara si admite traspaso sin peaje. Sin ese dato una recomendacion de reduccion puede
   costar dinero, porque los traspasos entre fondos y planes son neutros y el resto no.
7. Matiz sobre ventas: se mantienen fuera mientras dirigir la aportacion baste para
   sostener las bandas. Cuando entren, seran disparadas por banda y conscientes del peaje,
   nunca por calendario.

## Modelo conceptual objetivo

1. `Portfolio`: uno-a-uno con usuario y moneda base.
2. `InvestmentContainer`: agrupador operativo; enlaza uno o varios `LedgerAccount` de efectivo por divisa.
3. `Instrument`: identidad confirmada (ISIN/ticker/mercado) o instrumento custom; clase, tipo y divisa de cotizacion.
4. `PortfolioPosition`: contenedor + instrumento + `Asset` existente, estilo de tracking, fechas de cobertura y estado.
5. `PositionOwnershipPeriod` + shares inmutables: titularidad historica efectiva.
6. `PortfolioTrade`: metadata de ejecucion enlazada a `LedgerTransaction`, nunca segundo ledger.
7. `InstrumentPrice` y valoracion manual: fuentes de mercado con procedencia y calidad.
8. `AllocationStrategyVersion`, targets y restricciones: estrategia fechada y rebalanceo reproducible.
9. Snapshots/agregados son caches reconstruibles, no fuentes de verdad.

## Fases

| Fase | Resultado utilizable | Specs |
|------|----------------------|-------|
| 1 | Dominio, migracion segura y calidad base | `phase-1-domain-foundation/backend.md` |
| 2 | Valoracion hibrida y precios diarios | `phase-2-hybrid-valuations/backend.md` |
| 3 | Motor TWR/MWR/P&L/FX y APIs de lectura | `phase-3-performance-engine/backend.md` + `qa.md` |
| 4 | `/cartera` de lectura mobile-first | raiz `docs/tasks/investment-portfolio/phase-4-portfolio-workspace/frontend.md` |
| 5 | Operaciones completas, historico e importador | ✅ `phase-5-operations-import/terminados/backend.md` + raiz `terminados/frontend.md` + `terminados/qa.md` |
| 6 | Estrategia y rebalanceo con aportaciones | `phase-6-allocation-rebalancing/backend.md` + raiz `frontend.md` |
| 7 | Benchmark compuesto y riesgo progresivo | ✅ `phase-7-benchmark-risk/terminados/backend.md` + raiz `terminados/frontend.md` + `terminados/qa.md` |
| 8 | ✅ Alertas, Mi Plan y cierre funcional | `phase-8-product-integration/terminados/backend.md` + raiz `terminados/frontend.md` |

## Orden y gate

Las fases se ejecutan en orden. Cada una debe migrar, validar y documentar su contrato antes de empezar la siguiente. La fase 4 es el primer release visible; las fases 1-3 deben probarse antes con fixtures representativos del historico real.

## Backlog no planificado

Ideas capturadas para valorar en su fase natural, sin comprometerse a alcance ni diseño todavia.

1. **Rentabilidad historica comparable entre periodos.** Hoy el usuario ve la TWR/MWR del periodo seleccionado, pero no si la cartera esta mejorando o empeorando frente a periodos anteriores equivalentes (p.ej. este trimestre vs el anterior, este año vs el año pasado a la misma fecha). Encaja con la fase 7 (benchmark y riesgo), que ya calcula "mejor/peor periodo"; una serie de TWR movil (rolling) por ventana fija seria la extension natural, y es distinta de un unico mejor/peor periodo puntual. Candidata a dibujarse en el propio grafico de evolucion como una segunda capa (linea o banda) junto a valor/aportado, no como grafico aparte — a validar cuando se disene la fase 7 si compite visualmente con las dos series ya presentes. Anotado 2026-08-17, antes de empezar la fase 6.
