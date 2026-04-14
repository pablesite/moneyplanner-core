# Movimientos - Tracker de Revision por Cuenta (Usuario 1)

Ultima actualizacion: 2026-04-14 (sesion 44)

## Objetivo
Checklist operativo para cerrar la tarea manual de "afinar Movimientos" revisando cuentas y contrapartidas de `user_id=1`.

## Patron preferido para cuentas de inversion
- Revalorizaciones: concepto `Revalorizacion`.
- Aportaciones normales: concepto `Inversion`.
- Aportaciones de cashback: concepto `Inversion (Cashback)`.
- Ownership en aportaciones: usar `ownership_id=1 (Pablo)` cuando aplique.

## Alcance
- `A revisar`: todas las cuentas contables de `user_id=1`.
- `Total cuentas`: 106.
- `Revisadas`: 45.
- `Pendientes`: 61.

## Cuentas Revisadas
- `42` - `FIV IVI` (pasivo / Prestamo FIV IVI)
- `46` - `Iphone 16 Pro` (pasivo / Prestamo iPhone 16 Pro)
- `492` - `Préstamo - Iphone 15 Pro` (pasivo / consolidada desde cuenta obsoleta `465`)
- `45` - `Hipoteca Palmito` (pasivo / hipoteca vivienda)
- `468` - `Master Matematicas (Deuda)` (pasivo)
- `89` - `Reserva Atrio` (pasivo / deuda)
- `36` - `Reserva Atrio Residencial` (activo de inversion)
- `14` - `Cartera Metal` (activo de inversion / roboadvisor)
- `470` - `Fondo ING PIMCO GIS Commodity` (activo de inversion)
- `425` - `ING 10/90` (activo de inversion / fondo ING)
- `424` - `ING Health Care` (activo de inversion / fondo ING)
- `459` - `ING Renta Fija` (activo de inversion / fondo ING)
- `460` - `ING S&P` (activo de inversion / fondo ING)
- `477` - `Fondo Monetario ING` (activo de inversion / fondo)
- `479` - `ETF MSCI World` (activo de inversion / ETF)
- `480` - `ETF REIT Real Global Real State` (activo de inversion / ETF REIT)
- `482` - `Cartera Ahorro MyInvestor` (activo de inversion / roboadvisor)
- `483` - `Cartera Ahorro MyInvestor (Compartida)` (activo de inversion / roboadvisor)
- `24` - `MyInvestor Depósito 1 mes` (activo de inversion / deposito; revision final cerrada)
- `23` - `MyInvestor 3 meses` (activo de inversion / deposito; revision final cerrada)
- `22` - `Spot Binance` (activo de inversion / cripto; revision final cerrada)
- `445` - `DT Bots Cripto` (activo de inversion / cripto; revision final cerrada)
- `6` - `Kutxa` (activo de liquidez / hucha; revision final cerrada)
- `15` - `Monedero Ana` (activo de liquidez; revision final cerrada)
- `16` - `Monedero compartido` (activo de liquidez; revision final cerrada)
- `17` - `Monedero Pablo` (activo de liquidez; revision final cerrada)
- `26` - `Bitcoin` (activo de inversion / cripto)
- `486` - `Cripto - ETH (Metamask)` (activo de inversion / cripto)
- `27` - `ETH` (activo de inversion / cripto; Binance)
- `485` - `Cripto - Bots de Grids (Pionex)` (activo de inversion / cripto; cierre final completado)
- `38` - `Urbanitae` (activo de inversion / crowdfunding inmobiliario; cierre final completado)
- `40` - `ViaInvest` (activo de inversion / crowdlending; cierre final completado)
- `31` - `Healthcare` (activo de inversion / ETF; cierre final completado)
- `28` - `ETF Physical Gold USD (Acc)` (activo de inversion / ETF; cierre final completado)
- `35` - `Small Caps` (activo de inversion / ETF - Small Caps; cierre final completado)
- `39` - `Water` (activo de inversion / ETF - Water; cierre final completado)
- `33` - `MyInv. Indexado Global (MSCI)` (activo de inversion / plan pensiones; cierre final completado)
- `34` - `Quantfury` (activo de inversion / stocks; cierre final completado, integra movimientos de `447 ST Stocks`)
- `37` - `Trade Republic` (activo de inversion / stocks; cierre final completado)
- `490` - `Trading Automático` (activo de inversion / otros; cierre final completado)
- `481` - `Tarjeta ING` (pasivo / tarjeta; cierre final completado)
- `41` - `Tarjeta ECI` (pasivo / tarjeta; cierre final completado)
- `43` - `Kutxa Bank Ana` (pasivo / tarjeta; cierre final completado)
- `44` - `Kutxa Bank Pablo` (pasivo / tarjeta; cierre final completado)
- `21` - `Santander` (activo de liquidez; cierre final completado)

## Estado De Categorizacion Final (ultima pasada)
- ✅ Cuentas con categorizacion final cerrada:
  - `42` - `FIV IVI`
  - `46` - `Iphone 16 Pro`
  - `492` - `Préstamo - Iphone 15 Pro`
  - `45` - `Hipoteca Palmito`
  - `468` - `Master Matematicas (Deuda)`
  - `26` - `Bitcoin`
  - `470` - `Fondo ING PIMCO GIS Commodity`
  - `89` - `Reserva Atrio`
  - `36` - `Reserva Atrio Residencial`
  - `424` - `ING Health Care`
  - `425` - `ING 10/90`
  - `459` - `ING Renta Fija`
  - `14` - `Cartera Metal`
  - `27` - `ETH`
  - `460` - `ING S&P`
  - `477` - `Fondo Monetario ING`
  - `479` - `ETF MSCI World`
  - `480` - `ETF REIT Real Global Real State`
  - `482` - `Cartera Ahorro MyInvestor`
  - `483` - `Cartera Ahorro MyInvestor (Compartida)`
  - `24` - `MyInvestor Depósito 1 mes`
  - `23` - `MyInvestor 3 meses`
  - `22` - `Spot Binance`
  - `445` - `DT Bots Cripto`
  - `6` - `Kutxa`
  - `15` - `Monedero Ana`
  - `16` - `Monedero compartido`
  - `17` - `Monedero Pablo`
  - `486` - `Cripto - ETH (Metamask)`
  - `485` - `Cripto - Bots de Grids (Pionex)`
  - `38` - `Urbanitae`
  - `40` - `ViaInvest`
  - `31` - `Healthcare`
  - `28` - `ETF Physical Gold USD (Acc)`
  - `35` - `Small Caps`
  - `39` - `Water`
  - `33` - `MyInv. Indexado Global (MSCI)`
  - `34` - `Quantfury`
  - `37` - `Trade Republic`
  - `490` - `Trading Automático`
  - `481` - `Tarjeta ING`
  - `41` - `Tarjeta ECI`
  - `43` - `Kutxa Bank Ana`
  - `44` - `Kutxa Bank Pablo`
  - `21` - `Santander`
- ✅ Todas las cuentas revisadas tienen ya cierre final de categorizacion.

## Limpieza Pendiente En Cuentas Revisadas
- `FIV IVI`: sin limpieza adicional pendiente detectada.
- `Iphone 16 Pro` (id=46): revision final cerrada. Pagos de deuda con concepto unificado a `Préstamo - Iphone 16 pro`.
- `Préstamo - Iphone 15 Pro` (id=492): revision final cerrada. Cuenta consolidada con 12 cuotas trasladadas desde `iPhone 15 Ana` (id=465), cuenta obsoleta eliminada y concepto de pagos de deuda unificado a `Préstamo -  Iphone 15 Pro`.
- `Hipoteca Palmito` (id=45): revision final cerrada y completada al 100%. Concepto unificado en todos los pagos de deuda a `Hipoteca Vivienda Palmito`; principal normalizado a `real_estate_assets/mortgage_principal`, intereses normalizados a `consumption_expenses/financial_commitments` y ownership de todos los pagos de deuda unificado a compartido 50/50 (`ownership_id=4`).
- `Master Matematicas (Deuda)`: sin limpieza estructural pendiente detectada.
- `Reserva Atrio` (deuda): revision final cerrada. Pagos de deuda con concepto unificado a `Préstamo - Reserva Atrio`, clasificacion `real_estate_assets/property_purchase` y ownership compartido `Pablo/Ana 50%` (`ownership_id=4`).
- `Reserva Atrio Residencial` (activo): revision final cerrada. Movimientos de compra y mejoras inmobiliarias revisados en su historico.
- `Cartera Metal`: revision final cerrada. Aportes de inversion normalizados a `Inversion en Roboadvisor` con clasificacion `financial_investments/roboadvisor`; movimientos legacy `investment_purchase` convertidos a `investment`.
- `Fondo ING PIMCO GIS Commodity` (id=470): revisado y consolidado. Activo creado (asset_id=147). Cuenta duplicada obsoleta (id=458) eliminada. 2 revalorizaciones limpias ("Intereses"). Revision final completada y cerrada para esta cuenta.
- `ING 10/90` (id=425): revision final cerrada. Aportes con `ownership_id=1 (Pablo)`. Cuenta obsoleta sin movimientos `id=473` eliminada.
- `ING Health Care` (id=424): revision final cerrada. Ingresos reclasificados a revalorizacion/aporte segun caso; revalorizaciones sin categoria ni ownership; aportes normalizados y cuenta obsoleta sin movimientos `id=472` eliminada.
- `ING Renta Fija` (id=459): revision final cerrada. Aportes de inversion normalizados con concepto `Inversion en Fondo ING Renta Fija` y clasificacion `financial_investments/index_funds`; cuenta obsoleta sin movimientos `id=474` eliminada.
- `ING S&P` (id=460): revision final cerrada. Aportes de inversion normalizados con concepto `Inversion en Fondo ING S&P` y clasificacion `financial_investments/index_funds`; cuenta obsoleta sin movimientos `id=475` eliminada.
- `Fondo Monetario ING` (id=477): revision final cerrada. Revalorizaciones sin categoria/subcategoria ni ownership.
- `ETF MSCI World` (id=479): revision final cerrada. Aportes normalizados con concepto `Inversion en ETF MSCI World` y clasificacion `financial_investments/etf_indexed`; revalorizaciones sin categoria/subcategoria; etiqueta de cuenta ajustada a `ETF MSCI World`.
- `ETF REIT Real Global Real State` (id=480): revision final cerrada. Aportes normalizados con concepto `Inversion en ETF REIT Real Global Real State` y clasificacion `financial_investments/etf_indexed`; revalorizaciones sin categoria/subcategoria.
- `Cartera Ahorro MyInvestor` (id=482): revision final cerrada. Revalorizaciones con tilde (`Revalorizacion` -> `Revalorización`) y sin ownership.
- `Cartera Ahorro MyInvestor (Compartida)` (id=483): revision final cerrada. Revalorizaciones con tilde (`Revalorizacion` -> `Revalorización`) y sin ownership.
- `MyInvestor Depósito 1 mes` (id=24): revision final cerrada. Ingresos unificados con concepto `Intereses de depósitos`. Retiradas de inversion (`investment/outflow`) normalizadas con concepto `Retirada de inversión en depósitos` y ownership compartido `Pablo/Ana 50%` (`ownership_id=4`).
- `MyInvestor 3 meses` (id=23): revision final cerrada. Deposito marcado como revisado en la pasada de cuentas de liquidez/depositos MyInvestor.
- `Spot Binance` (id=22): revision final cerrada. Correccion de metadatos de direccion en aportes a Bots (`investment_direction` coherente con el asiento), normalizacion de conceptos en aportes a BTC (`Inversión en BTC`) y en ingresos por ajuste manual Euro/USD (`Ajuste cambio manual Euro/Dolar`) con categoria `other_income/other`. Añadido en UI el saldo contable tras movimiento para facilitar auditoria del timeline por cuenta. Eliminada cuenta obsoleta `Earn Binance` (id=10) tras validacion manual.
- `DT Bots Cripto` (id=445): revision final cerrada. Cuenta marcada como lista tras validacion manual de historico y coherencia de contrapartidas con Spot Binance.
- `Kutxa` (id=6): revision final cerrada (Hucha lista). Cuenta marcada como cerrada por validacion manual del historico de liquidez.
- `Monedero Ana` (id=15): revision final cerrada. Cuenta de liquidez marcada como lista tras validacion manual.
- `Monedero compartido` (id=16): revision final cerrada (revision a fondo completada). Validado historico de transferencias/movimientos relevantes, incluyendo el ajuste manual del movimiento faltante del `2020-11-26` por `600 EUR`.
- `Monedero Pablo` (id=17): revision final cerrada. Recategorizacion aplicada en movimientos de `Limpieza*`: base a `consumption_expenses/housing_home`, con excepciones `Limpieza Bici`, `Limpieza Bicicleta` y `Limpieza Boca` en `consumption_expenses/health_wellbeing`.
- `Bitcoin` (id=26): revisado. Spot Binance migrado a USD, deduplicacion aplicada y clasificacion normalizada en aportes (`financial_investments -> crypto`) y retiradas (`capital_gains -> sale_financial_assets`). Coherencia de saldo/timeline validada.
- `Cripto - ETH (Metamask)` (id=486): revision final cerrada. Cuenta satelite de inversion con ownership de activo y movimientos alineado a `Lucas` (`ownership_id=11`).
- `ETH` (id=27, Binance): revision final cerrada. Aportes de inversion (`investment/inflow`) normalizados con concepto `Inversion en ETH` y ownership de movimientos alineado a `Lucas` (`ownership_id=11`).
- `Cripto - Bots de Grids (Pionex)` (id=485): revision final cerrada. Limpieza de saldo inicial legacy duplicado (`tx 25`) y de movimientos espejo duplicados en Spot Binance. `DT Criptos` reclasificados de ingreso pasivo a inversion con contrapartida correcta en Spot, revalorizaciones normalizadas (tipo + concepto `Revalorización`) y conceptos finales unificados: aportes `Inversión a Cripto - Bots de Grids`, retiradas `Retirada de inversión de Cripto - Bots de Grids a Spot Binance`. Aportes con clasificacion `financial_investments/crypto`.
- `Urbanitae` (id=38): revision final cerrada. Aportes de inversion normalizados con concepto `Inversión en Crowdfunding`; caso puntual de ingreso mal tipado (`Crowdfunding Inm.`) convertido a aporte de inversion contra `TradeRepublic` y eliminacion de gasto espejo duplicado en Trade (`tx 45128`). Reembolsos/movimientos de retorno mantenidos como retirada/ganancia de capital segun corresponda.
- `ViaInvest` (id=40): revision final cerrada. Aportes de inversion normalizados con concepto `Inversión en Crowdlending` y clasificacion `financial_investments/crowdlending_p2p` en toda la cuenta.
- `Healthcare` (id=31): revision final cerrada. Revalorizaciones con concepto `Revalorización`. Aportes de inversion normalizados con concepto `Inversión en ETF Healthcare` y clasificacion `financial_investments/etf_indexed`.
- `ETF Physical Gold USD (Acc)` (id=28): revision final cerrada. Revalorizaciones con concepto `Revalorización`. Aportes de inversion normalizados con concepto `Inversión en ETF Physycial Gold` y clasificacion `financial_investments/etf_indexed`. Excepcion acordada: los aportes de cashback mantienen concepto `Inversión en ETF Physical Gold (Cashback)`.
- `Small Caps` (id=35): revision final cerrada. Revalorizaciones con concepto `Revalorización` (tilde correcta) y sin categoria/subcategoria. Aportes de inversion normalizados con concepto `Inversión en ETF - Small Caps` y clasificacion `financial_investments/etf_indexed`.
- `Water` (id=39): revision final cerrada. Revalorizaciones normalizadas con concepto `Revalorización` y sin categoria/subcategoria. Aportes de inversion normalizados con concepto `Inversión en ETF - Water` y clasificacion `financial_investments/etf_indexed`.
- `MyInv. Indexado Global (MSCI)` (id=33): revision final cerrada. Movimientos legacy `income/expense` reclasificados como `revaluation`, concepto unificado a `Revalorización` y sin categoria/subcategoria. Aportes de inversion normalizados con concepto `Inversión en Plan de Pensiones - Indexado Global (MSCI)` y clasificacion `financial_investments/pension_plan`.
- `Quantfury` (id=34): revision final cerrada. Movimientos trasladados desde `ST Stocks` (id=447) y convertidos de EUR a USD por fecha de apunte; cuenta `447` eliminada tras el traslado. Ingresos `St Stocks` con clasificacion legacy `capital_gains/sale_financial_assets` reclasificados a `revaluation` y concepto unificado a `Revalorización`.
- `Trade Republic` (id=37): revision final cerrada. Todos los movimientos `income` reclasificados a `revaluation`; limpieza de clasificacion legacy `capital_gains/sale_financial_assets` aplicada en esos ingresos y concepto de revalorizaciones unificado a `Revalorización`. Se mantienen sin cambios las retiradas de inversion (`investment/outflow`) con ganancia de capital.
- `Trading Automático` (id=490): revision final cerrada. Movimientos migrados desde cuenta obsoleta `id=446` (eliminada). Conversion EUR->USD aplicada en revalorizaciones y normalizacion de clasificacion: `income` reclasificado a `revaluation`, concepto unificado a `Revalorización` y categorias de revalorizacion limpiadas. Permanece un caso de retirada de inversion (`investment/outflow`) con clasificacion `capital_gains/sale_financial_assets`.
- `Tarjeta ING` (id=481): revision final cerrada. Recategorizacion masiva en `consumption_expenses`: 31 movimientos migrados desde `other_consumption_expenses` a subcategorias especificas (`transport_mobility`=12, `living_expenses`=9, `leisure_lifestyle`=7, `gifts_donations`=2, `housing_home`=1). Se mantienen 3 casos ambiguos sin cambio (`Retirada Cajero LGW N79 IDL COLUMN ACC`, `Nuevo saldo`, `Compras Materiales`).
- `Tarjeta ECI` (id=41): revision final cerrada. Recategorizacion aplicada en gastos de consumo (`Cejas De ana` -> `health_wellbeing`, `Traje Boda Celia` y `Northface Para Pablo` -> `leisure_lifestyle`), eliminacion de asiento obsoleto de saldo inicial (`tx 35`) y normalizacion de concepto en transferencias con ING (`Transferencia a Tarjeta ECI desde ING`, 38 movimientos). Permanecen 3 movimientos `Nuevo saldo` en `other_consumption_expenses` al no aportar señal suficiente para reclasificacion automatica.
- `Kutxa Bank Ana` (id=43): revision final cerrada. Reclasificacion acordada de 17 gastos desde `tangible_assets/other_tangible_assets` a `consumption_expenses/housing_home` y refinado de `other_consumption_expenses` con 5 reclasificaciones claras (`transport_mobility`, `health_wellbeing`, `leisure_lifestyle`, `gifts_donations`). Se mantienen 16 casos ambiguos sin cambio por falta de señal semantica.
- `Kutxa Bank Pablo` (id=44): revision final cerrada. Recategorizacion de `other_consumption_expenses` con criterio conservador en 127 movimientos (`financial_commitments`=52, `leisure_lifestyle`=55, `transport_mobility`=11, `living_expenses`=4, `gifts_donations`=3, `health_wellbeing`=1, `housing_home`=1) y criterio manual adicional para `iCloud` a `housing_home` (53 movimientos en total). Quedan 36 movimientos ambiguos mantenidos en `other_consumption_expenses` por falta de contexto.
- `Santander` (id=21): revision final cerrada. Cuenta de liquidez marcada como lista tras actualizacion manual del historico y validacion de coherencia de contrapartidas.

## Cuentas Pendientes De Revisar (Cola Priorizada)
Estrategia: primero cuentas satÃ©lite (mÃ¡s independientes), al final las cuentas corrientes gordas (dependen de que el resto estÃ© limpio).

### Grupo 6 â€” MoneyWiz (cuentas virtuales, revisiÃ³n final)
`origin=system`. Invisibles en la app. Revisar al final, una vez que todas las cuentas reales estÃ©n limpias.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| 2012 | 405 | MoneyWiz expense: consumption_expenses/leisure_lifestyle | expense |
| 901 | 409 | MoneyWiz expense: consumption_expenses/other_consumption_expenses | expense |
| 885 | 406 | MoneyWiz expense: consumption_expenses/living_expenses | expense |
| 700 | 404 | MoneyWiz expense: consumption_expenses/transport_mobility | expense |
| 582 | 400 | MoneyWiz expense: consumption_expenses/housing_home | expense |
| 552 | 417 | MoneyWiz income: capital_gains/sale_financial_assets | income |
| 451 | 401 | MoneyWiz income: other_income/misc | income |
| 369 | 403 | MoneyWiz expense: consumption_expenses/health_wellbeing | expense |
| 328 | 399 | MoneyWiz expense: consumption_expenses/family_childcare | expense |
| 305 | 407 | MoneyWiz expense: consumption_expenses/gifts_donations | expense |
| 250 | 427 | MoneyWiz income: salary/employee_salary | income |
| 182 | 448 | MoneyWiz income: passive_income/other_passive | income |
| 138 | 418 | MoneyWiz income: transfers_support/other_transfers_support | income |
| 135 | 415 | MoneyWiz expense: tangible_assets/other_tangible_assets | expense |
| 133 | 433 | MoneyWiz income: passive_income/interest_income | income |
| 126 | 402 | MoneyWiz expense: consumption_expenses/education_growth | expense |
| 111 | 408 | MoneyWiz income: transfers_support/gifts_received | income |
| 98 | 455 | MoneyWiz revaluation: Pasivos > Activos financieros > ST Criptos | expense |
| 90 | 436 | MoneyWiz expense: financial_investments/roboadvisor | expense |

### Grupo 1 â€” InversiÃ³n (fondos, brokers, roboadvisors)
Pendientes actuales de inversion (lista depurada). `Quantfury (34)`, `Trade Republic (37)` y `Trading Automático (490)` ya revisadas y cerradas.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| - | - | (sin pendientes de inversion en este grupo) | - |

### Grupo 2 â€” Cripto
SatÃ©lites cripto. Contrapartidas suelen ser Spot Binance â†” liquidez.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| - | - | (sin pendientes en cripto satelite) | - |

### Grupo 3 â€” Pasivos satÃ©lite (prÃ©stamos y tarjeta)
PequeÃ±os pasivos independientes. Contrapartidas ya conocidas.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| - | - | (sin pendientes en pasivos satélite) | - |

### Grupo 4 â€” Cuentas corrientes (dejar para el final)
Las mÃ¡s gordas y con mÃ¡s dependencias cruzadas. Revisar una vez que los grupos anteriores estÃ©n limpios.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| 1956 | 5 | ING | asset |

## Pendientes Transversales
- Sin pendientes transversales nuevos en esta sesion.
- Revisiones transversales de hipoteca cerradas: criterio unico de contabilizacion deuda (principal vs interes) validado y aplicado en `Hipoteca Palmito`.
- Revision de `Monedero compartido` (id=16) cerrada. Movimiento faltante del `2020-11-26` (`600 EUR`) ya integrado en el cierre de la revision.

## Como continuar manana
1. Nuevo orden acordado: liquidez/depositos pendientes -> resto de grupos -> cuentas virtuales MoneyWiz al final.
2. Revision de `Spot Binance`, `Trade Republic`, `Kutxa`, `DT Bots Cripto`, `Monedero Pablo` y `Santander` cerradas; continuar con la cuenta de liquidez pendiente segun prioridad acordada.
3. Por cada cuenta revisar:
   - coherencia de contrapartidas en liquidez,
   - movimientos duplicados (manual/import),
   - cuentas tecnicas o espejo que queden sin uso.
4. Marcar como revisada una cuenta solo cuando su historico quede consistente.
5. Para "depositos dentro de liquidez", priorizar en Grupo 4 las cuentas de liquidez (`ING`, `Kutxa`, `Santander`, `Monederos`) antes de seguir con otras cuentas corrientes.

## Proximo dia - Prioridad acordada
Listado acordado manualmente para la siguiente sesion de revision:

1. Depositos dentro de liquidez: `5` (ING).
2. Al cerrar liquidez, pasar a cuentas virtuales `MoneyWiz (origin=system)` para revision final.

## Comando de regeneracion de listado completo (usuario 1)
Usar para obtener el inventario completo actualizado:

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py shell -c "
from accounting.models import LedgerAccount
for a in LedgerAccount.objects.filter(user_id=1).order_by('account_type','name','id'):
    print(a.id, a.name, a.account_type, a.currency)
"
```
