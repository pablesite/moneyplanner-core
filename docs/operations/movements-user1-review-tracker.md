# Movimientos - Tracker de Revision por Cuenta (Usuario 1)

Ultima actualizacion: 2026-04-02 (sesion 16)

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
- `Revisadas`: 19.
- `Pendientes`: 87.

## Cuentas Revisadas
- `42` - `FIV IVI` (pasivo / Prestamo FIV IVI)
- `46` - `Iphone 16 Pro` (pasivo / Prestamo iPhone 16 Pro)
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
- `26` - `Bitcoin` (activo de inversion / cripto)
- `486` - `Cripto - ETH (Metamask)` (activo de inversion / cripto)
- `27` - `ETH` (activo de inversion / cripto; Binance)

## Estado De Categorizacion Final (ultima pasada)
- ✅ Cuentas con categorizacion final cerrada:
  - `42` - `FIV IVI`
  - `46` - `Iphone 16 Pro`
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
  - `486` - `Cripto - ETH (Metamask)`
- ✅ Todas las cuentas revisadas tienen ya cierre final de categorizacion.

## Limpieza Pendiente En Cuentas Revisadas
- `FIV IVI`: sin limpieza adicional pendiente detectada.
- `Iphone 16 Pro`: sin limpieza adicional pendiente detectada.
- `Master Matematicas (Deuda)`: sin limpieza estructural pendiente detectada.
- `Reserva Atrio` (deuda): revision final cerrada. Pagos de deuda normalizados a `Deuda - Nueva vivienda`, clasificacion `real_estate_assets/property_purchase` y ownership compartido `Pablo/Ana 50%` (`ownership_id=4`).
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
- `Bitcoin` (id=26): revisado. Spot Binance migrado a USD, deduplicacion aplicada y clasificacion normalizada en aportes (`financial_investments -> crypto`) y retiradas (`capital_gains -> sale_financial_assets`). Coherencia de saldo/timeline validada.
- `Cripto - ETH (Metamask)` (id=486): revision final cerrada. Cuenta satelite de inversion con ownership de activo y movimientos alineado a `Lucas` (`ownership_id=11`).
- `ETH` (id=27, Binance): revision final cerrada. Aportes de inversion (`investment/inflow`) normalizados con concepto `Inversion en ETH` y ownership de movimientos alineado a `Lucas` (`ownership_id=11`).

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
SatÃ©lites de inversiÃ³n. Contrapartidas suelen ser MyInvestor/TradeRepublic â†” liquidez.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| 468 | 19 | MyInvestor | asset |
| 430 | 25 | TradeRepublic | asset |
| 324 | 33 | MyInv. Indexado Global (MSCI) | asset |
| 152 | 476 | Cuenta Naranja | asset |
| 138 | 18 | MyInvestor | asset |
| 129 | 447 | ST Stocks | asset |
| 81 | 40 | ViaInvest | asset |

### Grupo 2 â€” Cripto
SatÃ©lites cripto. Contrapartidas suelen ser Spot Binance â†” liquidez.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| 246 | 22 | Spot Binance | asset |
| 174 | 445 | DT Bots Cripto | asset |

### Grupo 3 â€” Pasivos satÃ©lite (prÃ©stamos y tarjeta)
PequeÃ±os pasivos independientes. Contrapartidas ya conocidas.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| 71 | 481 | Tarjeta ING | liability |
| 128 | 45 | Hipoteca Palmito | liability |
| 107 | 41 | Tarjeta ECI | liability |

### Grupo 4 â€” Cuentas corrientes (dejar para el final)
Las mÃ¡s gordas y con mÃ¡s dependencias cruzadas. Revisar una vez que los grupos anteriores estÃ©n limpios.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| 2119 | 44 | Kutxa Bank Pablo | liability |
| 1986 | 16 | Monedero compartido | asset |
| 1956 | 5 | ING | asset |
| 1374 | 6 | Kutxa | asset |
| 1058 | 17 | Monedero Pablo | asset |
| 702 | 43 | Kutxa Bank Ana | liability |
| 414 | 21 | Santander | asset |
| 213 | 15 | Monedero Ana | asset |

## Pendientes Transversales
- (sin pendientes transversales nuevos tras el cierre de `Fondo ING PIMCO GIS Commodity`).

## Como continuar manana
1. Seguir los grupos en orden: Inversion -> Cripto -> Pasivos satelite -> Cuentas corrientes -> MoneyWiz virtuales (al final).
2. Por cada cuenta revisar:
   - coherencia de contrapartidas en liquidez,
   - movimientos duplicados (manual/import),
   - cuentas tecnicas o espejo que queden sin uso.
3. Marcar como revisada una cuenta solo cuando su historico quede consistente.
4. Las cuentas corrientes (Grupo 4) no empezar hasta tener los grupos 1-3 razonablemente limpios.

## Proximo dia - Inversiones pendientes (lista acordada)
Listado acordado manualmente para la siguiente sesion de revision de inversiones:

1. `485` - `Cripto - Bots de Grids (Pionex)` (antes duplicada con `32 Grids Pionex`, ya eliminada)
2. `38` - `Urbanitae` (Crowfunding Inm)
3. `40` - `ViaInvest` (Crowdlending)
4. `31` - `Healthcare` (ETF - Healthcare)
5. `28` - `ETF Physical Gold USD (Acc)`
6. `35` - `Small Caps` (ETF - Small Caps)
7. `39` - `Water` (ETF - Water)
8. `33` - `MyInv. Indexado Global (MSCI)` (Plan Pensiones)
9. `34` - `Quantfury` + `447` - `ST Stocks` (revisar conjuntamente; `ST Stocks` concentra movimientos importados)
10. `37` - `Trade Republic` (Stocks - Trade Republic)
11. `446` - `Trading Automático` (cuenta en "otros")

## Comando de regeneracion de listado completo (usuario 1)
Usar para obtener el inventario completo actualizado:

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py shell -c "
from accounting.models import LedgerAccount
for a in LedgerAccount.objects.filter(user_id=1).order_by('account_type','name','id'):
    print(a.id, a.name, a.account_type, a.currency)
"
```
