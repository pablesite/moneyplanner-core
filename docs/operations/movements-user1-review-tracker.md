# Movimientos - Tracker de Revision por Cuenta (Usuario 1)

Ultima actualizacion: 2026-03-25 (sesion 3)

## Objetivo
Checklist operativo para cerrar la tarea manual de "afinar Movimientos" revisando cuentas y contrapartidas de `user_id=1`.

## Alcance
- `A revisar`: todas las cuentas contables de `user_id=1`.
- `Total cuentas`: 110.
- `Revisadas`: 11.
- `Pendientes`: 99.

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

## Limpieza Pendiente En Cuentas Revisadas
- `FIV IVI`: sin limpieza adicional pendiente detectada.
- `Iphone 16 Pro`: sin limpieza adicional pendiente detectada.
- `Master Matematicas (Deuda)`: sin limpieza estructural pendiente detectada.
- `Reserva Atrio` (deuda): sin limpieza adicional pendiente detectada.
- `Reserva Atrio Residencial` (activo): sin limpieza adicional pendiente detectada.
- `Cartera Metal`: limpio. 27 aportes (investment_purchase inflow desde MyInvestor), 172 revalorizaciones, 1 transferencia de traspaso desde Fondo ING PIMCO.
- `Fondo ING PIMCO GIS Commodity` (id=470): revisado y consolidado. Activo creado (asset_id=147). Cuenta duplicada obsoleta (id=458) eliminada. 2 revalorizaciones limpias ("Intereses"). ⚠️ Pendiente: 2 "Fondos" (50€ ago-22 y 80€ sep-22) con contrapartida virtual — origen probable en cuenta ING de fondos aún no incorporada al sistema. Revisar cuando se cree esa cuenta.
- `ING 10/90` (id=425): revisado. Aportes con `ownership_id=1 (Pablo)`. Cuenta obsoleta sin movimientos `id=473` eliminada.
- `ING Health Care` (id=424): revisado. Ingresos reclasificados a revalorizacion/aporte segun caso; revalorizaciones sin categoria ni ownership; aportes con concepto `Inversion` y `ownership_id=1`. Cuenta obsoleta sin movimientos `id=472` eliminada.
- `ING Renta Fija` (id=459): revisado. Ingresos convertidos a aportes de inversion desde `ING (id=5)`; conceptos normalizados (`Inversion` / `Revalorizacion`) y aportes con `ownership_id=1`. Cuenta obsoleta sin movimientos `id=474` eliminada.
- `ING S&P` (id=460): revisado. Ingresos convertidos a aportes de inversion; conceptos normalizados (`Inversion` / `Revalorizacion`) y aportes con `ownership_id=1`. Cuenta obsoleta sin movimientos `id=475` eliminada.

## Cuentas Pendientes De Revisar (Cola Priorizada)
Estrategia: primero cuentas satélite (más independientes), al final las cuentas corrientes gordas (dependen de que el resto esté limpio).

### Grupo 6 — MoneyWiz (cuentas virtuales, revisión final)
`origin=system`. Invisibles en la app. Revisar al final, una vez que todas las cuentas reales estén limpias.

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

### Grupo 1 — Inversión (fondos, brokers, roboadvisors)
Satélites de inversión. Contrapartidas suelen ser MyInvestor/TradeRepublic ↔ liquidez.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| 468 | 19 | MyInvestor | asset |
| 409 | 25 | TradeRepublic | asset |
| 324 | 33 | MyInv. Indexado Global (MSCI) | asset |
| 149 | 416 | Cuenta NARANJA | asset |
| 137 | 18 | MyInvestor | asset |
| 129 | 447 | ST Stocks | asset |
| 81 | 40 | ViaInvest | asset |

### Grupo 2 — Cripto
Satélites cripto. Contrapartidas suelen ser Spot Binance ↔ liquidez.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| 277 | 421 | ST Criptos | asset |
| 246 | 22 | Spot Binance | asset |
| 174 | 445 | DT Bots Cripto | asset |

### Grupo 3 — Pasivos satélite (préstamos y tarjeta)
Pequeños pasivos independientes. Contrapartidas ya conocidas.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| 128 | 45 | Hipoteca Palmito | liability |
| 107 | 41 | Tarjeta ECI | liability |

### Grupo 4 — Cuentas corrientes (dejar para el final)
Las más gordas y con más dependencias cruzadas. Revisar una vez que los grupos anteriores estén limpios.

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
- ⚠️ **Cuenta ING de fondos sin monitorizar**: Fondo ING PIMCO tiene 2 aportes (50€ ago-22 y 80€ sep-22) cuyo origen es probablemente una cuenta ING de gestión de fondos que aún no está en el sistema. Crear ese activo/cuenta cuando se pueda y vincular esas transacciones.

## Como continuar manana
1. Seguir los grupos en orden: Inversión → Cripto → Pasivos satélite → Cuentas corrientes → MoneyWiz virtuales (al final).
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
