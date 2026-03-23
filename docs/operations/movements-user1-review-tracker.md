# Movimientos - Tracker de Revision por Cuenta (Usuario 1)

Ultima actualizacion: 2026-03-24

## Objetivo
Checklist operativo para cerrar la tarea manual de "afinar Movimientos" revisando cuentas y contrapartidas de `user_id=1`.

## Alcance
- `A revisar`: todas las cuentas contables de `user_id=1`.
- `Total cuentas`: 110.
- `Revisadas`: 5.
- `Pendientes`: 105.

## Cuentas Revisadas
- `42` - `FIV IVI` (pasivo / Prestamo FIV IVI)
- `46` - `Iphone 16 Pro` (pasivo / Prestamo iPhone 16 Pro)
- `468` - `Master Matematicas (Deuda)` (pasivo)
- `89` - `Reserva Atrio` (pasivo / deuda)
- `36` - `Reserva Atrio Residencial` (activo de inversion)

## Limpieza Pendiente En Cuentas Revisadas
- `FIV IVI`: sin limpieza adicional pendiente detectada (contrapartida liquidez consistente en `Kutxa`).
- `Iphone 16 Pro`: sin limpieza adicional pendiente detectada (contrapartida liquidez consistente en `ING`).
- `Master Matematicas (Deuda)`: sin limpieza estructural pendiente detectada.
- `Reserva Atrio` (deuda): sin limpieza adicional pendiente detectada (contrapartida en `MyInvestor` consistente).
- `Reserva Atrio Residencial` (activo): sin limpieza adicional pendiente detectada.

## Cuentas Pendientes De Revisar (Cola Priorizada)
Ordenadas por volumen de movimientos para maximizar impacto en cada sesion de revision.

| Movs | id | Cuenta | Tipo |
|---:|---:|---|---|
| 2119 | 44 | Kutxa Bank Pablo | liability |
| 2012 | 405 | MoneyWiz expense: consumption_expenses/leisure_lifestyle | expense |
| 1986 | 16 | Monedero compartido | asset |
| 1956 | 5 | ING | asset |
| 1374 | 6 | Kutxa | asset |
| 1058 | 17 | Monedero Pablo | asset |
| 901 | 409 | MoneyWiz expense: consumption_expenses/other_consumption_expenses | expense |
| 885 | 406 | MoneyWiz expense: consumption_expenses/living_expenses | expense |
| 702 | 43 | Kutxa Bank Ana | liability |
| 700 | 404 | MoneyWiz expense: consumption_expenses/transport_mobility | expense |
| 582 | 400 | MoneyWiz expense: consumption_expenses/housing_home | expense |
| 552 | 417 | MoneyWiz income: capital_gains/sale_financial_assets | income |
| 468 | 19 | MyInvestor | asset |
| 451 | 401 | MoneyWiz income: other_income/misc | income |
| 414 | 21 | Santander | asset |
| 409 | 25 | TradeRepublic | asset |
| 369 | 403 | MoneyWiz expense: consumption_expenses/health_wellbeing | expense |
| 328 | 399 | MoneyWiz expense: consumption_expenses/family_childcare | expense |
| 324 | 33 | MyInv. Indexado Global (MSCI) | asset |
| 305 | 407 | MoneyWiz expense: consumption_expenses/gifts_donations | expense |
| 301 | 14 | Cartera Metal | asset |
| 277 | 421 | ST Criptos | asset |
| 250 | 427 | MoneyWiz income: salary/employee_salary | income |
| 246 | 22 | Spot Binance | asset |
| 213 | 15 | Monedero Ana | asset |
| 182 | 448 | MoneyWiz income: passive_income/other_passive | income |
| 174 | 445 | DT Bots Cripto | asset |
| 149 | 416 | Cuenta NARANJA | asset |
| 138 | 418 | MoneyWiz income: transfers_support/other_transfers_support | income |
| 137 | 18 | MyInvestor | asset |
| 135 | 415 | MoneyWiz expense: tangible_assets/other_tangible_assets | expense |
| 133 | 433 | MoneyWiz income: passive_income/interest_income | income |
| 129 | 447 | ST Stocks | asset |
| 128 | 45 | Hipoteca Palmito | liability |
| 126 | 402 | MoneyWiz expense: consumption_expenses/education_growth | expense |
| 111 | 408 | MoneyWiz income: transfers_support/gifts_received | income |
| 107 | 41 | Tarjeta ECI | liability |
| 98 | 455 | MoneyWiz revaluation: Pasivos > Activos financieros > ST Criptos | expense |
| 90 | 436 | MoneyWiz expense: financial_investments/roboadvisor | expense |
| 81 | 40 | ViaInvest | asset |

## Como continuar manana
1. Seguir la cola priorizada de arriba.
2. Por cada cuenta revisar:
   - coherencia de contrapartidas en liquidez,
   - movimientos duplicados (manual/import),
   - cuentas tecnicas o espejo que queden sin uso.
3. Marcar como revisada una cuenta solo cuando su historico quede consistente.

## Comando de regeneracion de listado completo (usuario 1)
Usar para obtener el inventario completo actualizado:

```bash
docker compose -f core/docker-compose.yml exec backend python manage.py shell -c "
from accounting.models import LedgerAccount
for a in LedgerAccount.objects.filter(user_id=1).order_by('account_type','name','id'):
    print(a.id, a.name, a.account_type, a.currency)
"
```
