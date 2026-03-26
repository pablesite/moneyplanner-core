# Movimientos - Tracker de Revision por Cuenta (Usuario 1)

Ultima actualizacion: 2026-03-27 (sesion 8)

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
- `Revisadas`: 16.
- `Pendientes`: 90.

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

## Limpieza Pendiente En Cuentas Revisadas
- `FIV IVI`: sin limpieza adicional pendiente detectada.
- `Iphone 16 Pro`: sin limpieza adicional pendiente detectada.
- `Master Matematicas (Deuda)`: sin limpieza estructural pendiente detectada.
- `Reserva Atrio` (deuda): sin limpieza adicional pendiente detectada.
- `Reserva Atrio Residencial` (activo): sin limpieza adicional pendiente detectada.
- `Cartera Metal`: limpio. 27 aportes (investment_purchase inflow desde MyInvestor), 172 revalorizaciones, 1 transferencia de traspaso desde Fondo ING PIMCO.
- `Fondo ING PIMCO GIS Commodity` (id=470): revisado y consolidado. Activo creado (asset_id=147). Cuenta duplicada obsoleta (id=458) eliminada. 2 revalorizaciones limpias ("Intereses"). âš ï¸ Pendiente: 2 "Fondos" (50â‚¬ ago-22 y 80â‚¬ sep-22) con contrapartida virtual â€” origen probable en cuenta ING de fondos aÃºn no incorporada al sistema. Revisar cuando se cree esa cuenta.
- `ING 10/90` (id=425): revisado. Aportes con `ownership_id=1 (Pablo)`. Cuenta obsoleta sin movimientos `id=473` eliminada.
- `ING Health Care` (id=424): revisado. Ingresos reclasificados a revalorizacion/aporte segun caso; revalorizaciones sin categoria ni ownership; aportes con concepto `Inversion` y `ownership_id=1`. Cuenta obsoleta sin movimientos `id=472` eliminada.
- `ING Renta Fija` (id=459): revisado. Ingresos convertidos a aportes de inversion desde `ING (id=5)`; conceptos normalizados (`Inversion` / `Revalorizacion`) y aportes con `ownership_id=1`. Cuenta obsoleta sin movimientos `id=474` eliminada.
- `ING S&P` (id=460): revisado. Ingresos convertidos a aportes de inversion; conceptos normalizados (`Inversion` / `Revalorizacion`) y aportes con `ownership_id=1`. Cuenta obsoleta sin movimientos `id=475` eliminada.
- `Fondo Monetario ING` (id=477): revisado. Movimientos migrados desde cuenta obsoleta `id=450`; ingresos convertidos a revalorizacion; revalorizaciones y transferencias sin ownership; concepto canonico `Revalorizacion`.
- `ETF MSCI World` (id=479): revisado. Movimientos migrados desde cuenta obsoleta `id=441`; cashback mensual normalizado a aporte de inversion desde `TradeRepublic (id=25)` con espejo de ingreso `Cashback` en TradeRepublic; conceptos normalizados (`Inversion`, `Inversion (Cashback)`, `Revalorizacion`). Conteo aplicado con patron habitual: `Revalorizacion=24`, `Inversion=29`, `Inversion (Cashback)=7`, y `ownership_id=1 (Pablo)` en las 36 aportaciones.
- `ETF REIT Real Global Real State` (id=480): revisado. Movimientos migrados desde cuenta obsoleta `id=440` (15 movimientos) y cuenta obsoleta eliminada. Activo vinculado en la cuenta nueva (`asset_id=157`). Conceptos normalizados: `Inversion=9` (8 inflow + 1 outflow) y `Revalorizacion=6`. Ownership ajustado: revalorizaciones sin ownership; el resto se mantiene.
- `Cartera Ahorro MyInvestor` (id=482): revisado. Movimientos migrados desde cuenta obsoleta `id=435` (70 movimientos) y cuenta obsoleta eliminada. Ingresos/gastos reclasificados a `Revalorizacion`; revalorizaciones sin categoria ni subcategoria.
- `Cartera Ahorro MyInvestor (Compartida)` (id=483): revisado. Movimientos migrados desde cuenta obsoleta `id=464` (72 movimientos) y cuenta obsoleta eliminada. Ingresos/gastos reclasificados a `Revalorizacion`; revalorizaciones sin categoria ni subcategoria.

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
| 110 | 26 | Bitcoin | asset |
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
- ⚠️ **Bitcoin (id=26) a medio curar**: avance aplicado en sesion 8:
  - conversion de alta/edicion rapida de inversion para soportar multimoneda en Core y espejo SaaS;
  - cuenta `Spot Binance (id=22)` convertida de EUR a USD y conversion historica de importes legacy a USD por fecha FX (manteniendo intactos los aportes fijos de `25.00 USD`);
  - varios movimientos `ST Criptos` reclasificados de `income` legacy a `investment inflow` (`Spot Binance -> Bitcoin`) y eliminacion de duplicados `gasto` asociados.
  Pendiente chequeo integral de coherencia final (saldo BTC, timeline completo y duplicados residuales) antes de cerrarlo como revisado.
- âš ï¸ **Cuenta ING de fondos sin monitorizar**: Fondo ING PIMCO tiene 2 aportes (50â‚¬ ago-22 y 80â‚¬ sep-22) cuyo origen es probablemente una cuenta ING de gestiÃ³n de fondos que aÃºn no estÃ¡ en el sistema. Crear ese activo/cuenta cuando se pueda y vincular esas transacciones.

## Como continuar manana
1. Seguir los grupos en orden: Inversion -> Cripto (terminar primero el chequeo de Bitcoin) -> Pasivos satelite -> Cuentas corrientes -> MoneyWiz virtuales (al final).
2. Por cada cuenta revisar:
   - coherencia de contrapartidas en liquidez,
   - movimientos duplicados (manual/import),
   - cuentas tecnicas o espejo que queden sin uso.
3. Marcar como revisada una cuenta solo cuando su historico quede consistente.
4. Las cuentas corrientes (Grupo 4) no empezar hasta tener los grupos 1-3 razonablemente limpios.

## Comando de regeneracion de listado completo (usuario 1)
Usar para obtener el inventario completo actualizado:

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py shell -c "
from accounting.models import LedgerAccount
for a in LedgerAccount.objects.filter(user_id=1).order_by('account_type','name','id'):
    print(a.id, a.name, a.account_type, a.currency)
"
```
