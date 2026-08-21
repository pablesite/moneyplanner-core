from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from core.models import InflationIndex
from core.services import build_fx_cache, convert_currency_cached
from memberships.models import Ownership, OwnershipLink
from net_worth.models import Asset, InvestmentAssetEvent

from .models import (
    ContainerCashAccount,
    InstrumentPrice,
    Portfolio,
    PortfolioPosition,
    PositionValuation,
)
from .performance_math import (
    DatedAmount,
    DatedValue,
    annualized,
    chained_twr,
    decompose_result,
    linked_dietz,
    modified_dietz,
    monetary_result,
    real_return,
    xirr,
)
from .lots import OwnershipPockets, UnitMovement, build_pockets, member_share_at
from .valuations import stale_days_for_position

ZERO = Decimal("0")
# La categoria contable que marca un gasto como coste de invertir. Cualquier otra cosa
# pagada desde el efectivo de un contenedor es dinero que sale de la cartera.
INVESTMENT_EXPENSE_CATEGORY = "financial_investments"
MAX_TIMELINE_DAYS = 366 * 20


@dataclass(frozen=True)
class FlowRecord:
    position_id: int | None
    on_date: date
    amount: Decimal
    currency: str
    kind: str
    source: str
    external: bool
    position_external: bool = False
    cost: Decimal = ZERO
    income: Decimal = ZERO
    realized_pnl: Decimal | None = None
    # Solo en flujos de efectivo de contenedor: la cuenta que lo movio, para poder
    # repartirlo por titularidad igual que se reparte su saldo.
    cash_account_id: int | None = None


@dataclass(frozen=True)
class ResolvedValue:
    value: Decimal
    currency: str
    observed_on: date
    exact: bool
    source: str


@dataclass
class PerformanceContext:
    portfolio: Portfolio
    positions: list[PortfolioPosition]
    cash_accounts: list[ContainerCashAccount]
    valuations: dict[int, list[PositionValuation]]
    prices: dict[int, list[InstrumentPrice]]
    # Claves paralelas a las dos listas de arriba, ya ordenadas, para resolver "la última
    # antes de esta fecha" por búsqueda binaria. Escanear la lista entera costaba la mitad
    # del tiempo de la petición: se llama decenas de miles de veces por carga.
    valuation_dates: dict[int, list[date]]
    price_dates: dict[int, list[date]]
    balance_dates: dict[int, list[date]]
    balance_values: dict[int, list[Decimal]]
    flows: list[FlowRecord]
    ownership_periods: dict[int, list[Any]]
    # Reparto del efectivo de contenedor por miembro, resuelto desde el OwnershipLink del
    # activo de Patrimonio que respalda cada cuenta. Una cuenta ausente de este mapa es
    # efectivo que no se puede atribuir, no efectivo de nadie.
    cash_ownership: dict[int, dict[int, Decimal]]
    # Solo para posiciones mezcladas: cuantas unidades tiene cada titularidad dentro del
    # bote, dia a dia. Una posicion ausente se reparte por sus tramos, como siempre.
    pockets: dict[int, OwnershipPockets]
    ownership_shares: dict[int, dict[int, Decimal]]
    fx_cache: dict[tuple[str, str], list[tuple[date, Decimal]]]
    inflation_rows: list[tuple[date, Decimal]]
    fx_issues: set[str] = field(default_factory=set)


def _quantize(value: Decimal | None, places: str = "0.00000001") -> str | None:
    return str(value.quantize(Decimal(places))) if value is not None else None


def _month_end(day: date) -> date:
    next_month = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month - timedelta(days=1)


def timeline_dates(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        raise ValidationError("date_to debe ser igual o posterior a date_from.")
    if (end_date - start_date).days > MAX_TIMELINE_DAYS:
        raise ValidationError("El timeline admite un máximo de 20 años por petición.")
    rows = [start_date]
    cursor = _month_end(start_date)
    while cursor < end_date:
        if cursor > start_date:
            rows.append(cursor)
        cursor = _month_end(cursor + timedelta(days=1))
    if rows[-1] != end_date:
        rows.append(end_date)
    return rows


def _load_balances(
    *, account_ids: list[int], end_date: date
) -> tuple[dict[int, list[date]], dict[int, list[Decimal]]]:
    dates: dict[int, list[date]] = {account_id: [] for account_id in account_ids}
    values: dict[int, list[Decimal]] = {account_id: [] for account_id in account_ids}
    balances: dict[int, Decimal] = {account_id: ZERO for account_id in account_ids}
    entries = (
        LedgerEntry.objects.filter(
            account_id__in=account_ids,
            transaction__status=cast(str, LedgerTransaction.Status.POSTED),
            transaction__booking_date__lte=end_date,
        )
        .select_related("transaction")
        .order_by("transaction__booking_date", "transaction_id", "id")
    )
    current_transaction_id = None
    touched: set[int] = set()
    current_date = None
    for entry in entries:
        if current_transaction_id is not None and entry.transaction_id != current_transaction_id:
            for account_id in touched:
                dates[account_id].append(current_date)
                values[account_id].append(balances[account_id])
            touched.clear()
        current_transaction_id = entry.transaction_id
        current_date = entry.transaction.booking_date
        account_id = int(entry.account_id)
        balances[account_id] += (
            entry.amount if entry.side == LedgerEntry.Side.DEBIT else -entry.amount
        )
        touched.add(account_id)
    for account_id in touched:
        dates[account_id].append(current_date)
        values[account_id].append(balances[account_id])
    return dates, values


def _first_entry_by_account(entries: list) -> dict[int, Any]:
    """Primera anotación de cada cuenta del asiento.

    Antes se recorrían todas las anotaciones una vez por posición de la cartera, así que
    el coste crecía con el producto de ambas. Recorriéndolas una sola vez el emparejamiento
    sale de un diccionario.
    """
    by_account: dict[int, Any] = {}
    for entry in entries:
        by_account.setdefault(entry.account_id, entry)
    return by_account


def _counterpart_entry(entries: list, account_id: int, side: str):
    return next(
        (entry for entry in entries if entry.account_id != account_id and entry.side == side),
        None,
    )


def _load_ledger_flows(
    *,
    positions: list[PortfolioPosition],
    cash_account_ids: set[int],
    start_date: date,
    end_date: date,
) -> tuple[list[FlowRecord], set[tuple[int, date]]]:
    account_to_position = {
        int(position.ledger_account_id): position
        for position in positions
        if position.ledger_account_id
    }
    transactions = (
        LedgerTransaction.objects.filter(
            status=cast(str, LedgerTransaction.Status.POSTED),
            booking_date__gte=start_date,
            booking_date__lte=end_date,
            entries__account_id__in=set(account_to_position) | cash_account_ids,
        )
        .prefetch_related("entries__account")
        .order_by("booking_date", "id")
        .distinct()
    )
    rows: list[FlowRecord] = []
    covered_dates: set[tuple[int, date]] = set()
    portfolio_account_ids = set(account_to_position) | cash_account_ids
    for transaction in transactions:
        entries = list(transaction.entries.all())
        by_account = _first_entry_by_account(entries)
        # Un asiento que toca dos posiciones es una mudanza entre ellas. La direccion vive
        # en el asiento, asi que ambas patas la leian igual y la de salida se perdia por no
        # encontrar contrapartida: el traspaso entraba dos veces como aportacion y nunca
        # salia. Con dos posiciones implicadas manda el lado de cada anotacion.
        moves_between_positions = sum(1 for key in account_to_position if key in by_account) > 1
        for account_id, position in account_to_position.items():
            position_entry = by_account.get(account_id)
            if position_entry is None:
                continue
            if transaction.quick_entry_kind == LedgerTransaction.QuickEntryKind.INVESTMENT:
                covered_dates.add((position.id, transaction.booking_date))
                if (
                    transaction.investment_direction
                    == LedgerTransaction.InvestmentDirection.REINVESTMENT
                ):
                    signed_amount = (
                        position_entry.amount
                        if position_entry.side == LedgerEntry.Side.DEBIT
                        else -position_entry.amount
                    )
                    rows.append(
                        FlowRecord(
                            position.id,
                            transaction.booking_date,
                            signed_amount,
                            position_entry.currency,
                            "internal_reinvestment",
                            "ledger",
                            False,
                            position_external=True,
                            realized_pnl=transaction.realized_gain_loss,
                        )
                    )
                    continue
                is_inflow = (
                    position_entry.side == LedgerEntry.Side.DEBIT
                    if moves_between_positions
                    else (
                        transaction.investment_direction
                        == LedgerTransaction.InvestmentDirection.INFLOW
                        or (
                            not transaction.investment_direction
                            and position_entry.side == LedgerEntry.Side.DEBIT
                        )
                    )
                )
                counterpart = _counterpart_entry(
                    entries,
                    account_id,
                    cast(
                        str,
                        LedgerEntry.Side.CREDIT if is_inflow else LedgerEntry.Side.DEBIT,
                    ),
                )
                if counterpart is None:
                    continue
                is_return_income = (
                    is_inflow
                    and counterpart.account.account_type == LedgerAccount.AccountType.INCOME
                )
                is_return_cost = (
                    not is_inflow
                    and counterpart.account.account_type == LedgerAccount.AccountType.EXPENSE
                )
                is_inside_portfolio = counterpart.account_id in portfolio_account_ids
                rows.append(
                    FlowRecord(
                        position.id,
                        transaction.booking_date,
                        counterpart.amount if is_inflow else -counterpart.amount,
                        counterpart.currency,
                        "income_reinvested"
                        if is_return_income
                        else "cost"
                        if is_return_cost
                        else ("funded_purchase" if is_inflow else "funded_sale")
                        if is_inside_portfolio
                        else ("contribution" if is_inflow else "withdrawal"),
                        "ledger",
                        not is_inside_portfolio and not is_return_income and not is_return_cost,
                        position_external=not is_return_income and not is_return_cost,
                        cost=counterpart.amount if is_return_cost else ZERO,
                        income=counterpart.amount if is_return_income else ZERO,
                        realized_pnl=transaction.realized_gain_loss,
                    )
                )
            elif transaction.quick_entry_kind == LedgerTransaction.QuickEntryKind.EXPENSE:
                expense = next(
                    (
                        entry
                        for entry in entries
                        if entry.flow_family == LedgerEntry.FlowFamily.EXPENSE
                    ),
                    None,
                )
                if expense:
                    rows.append(
                        FlowRecord(
                            position.id,
                            transaction.booking_date,
                            ZERO,
                            expense.currency,
                            "cost",
                            "ledger",
                            False,
                            position_external=False,
                            cost=expense.amount,
                        )
                    )
            elif transaction.quick_entry_kind == LedgerTransaction.QuickEntryKind.INCOME:
                income = next(
                    (
                        entry
                        for entry in entries
                        if entry.flow_family == LedgerEntry.FlowFamily.INCOME
                    ),
                    None,
                )
                if income:
                    rows.append(
                        FlowRecord(
                            position.id,
                            transaction.booking_date,
                            ZERO,
                            income.currency,
                            "income",
                            "ledger",
                            False,
                            position_external=False,
                            income=income.amount,
                        )
                    )
        if transaction.quick_entry_kind == LedgerTransaction.QuickEntryKind.INVESTMENT:
            continue
        for cash_account_id in cash_account_ids:
            cash_entry = by_account.get(cash_account_id)
            if cash_entry is None:
                continue
            if transaction.quick_entry_kind == LedgerTransaction.QuickEntryKind.TRANSFER:
                counterpart = next(
                    (entry for entry in entries if entry.account_id != cash_account_id),
                    None,
                )
                if counterpart is None or counterpart.account_id in cash_account_ids:
                    continue
                is_inflow = cash_entry.side == LedgerEntry.Side.DEBIT
                rows.append(
                    FlowRecord(
                        None,
                        transaction.booking_date,
                        counterpart.amount if is_inflow else -cash_entry.amount,
                        counterpart.currency if is_inflow else cash_entry.currency,
                        "cash_contribution" if is_inflow else "cash_withdrawal",
                        "ledger",
                        True,
                        cash_account_id=cash_account_id,
                    )
                )
            elif transaction.quick_entry_kind == LedgerTransaction.QuickEntryKind.INCOME:
                rows.append(
                    FlowRecord(
                        None,
                        transaction.booking_date,
                        ZERO,
                        cash_entry.currency,
                        "cash_income",
                        "ledger",
                        False,
                        income=cash_entry.amount,
                        cash_account_id=cash_account_id,
                    )
                )
            elif transaction.quick_entry_kind == LedgerTransaction.QuickEntryKind.EXPENSE:
                # Un gasto pagado desde el efectivo de un contenedor solo es coste de la
                # cartera si es un coste de invertir —una comision de custodia lo es—. La
                # compra del supermercado pagada desde esa cuenta es dinero que sale de la
                # cartera, y contarla como coste hundia la rentabilidad con gasto
                # corriente: sobre datos reales, 3.349 EUR de gastos personales figuraban
                # como costes de inversion. La categoria contable ya distingue una cosa de
                # la otra, asi que se le pregunta a ella.
                expense_entry = next(
                    (row for row in entries if row.flow_family == LedgerEntry.FlowFamily.EXPENSE),
                    None,
                )
                is_investment_cost = (
                    expense_entry is not None
                    and expense_entry.category_key == INVESTMENT_EXPENSE_CATEGORY
                )
                rows.append(
                    FlowRecord(
                        None,
                        transaction.booking_date,
                        ZERO if is_investment_cost else -cash_entry.amount,
                        cash_entry.currency,
                        "cash_cost" if is_investment_cost else "cash_withdrawal",
                        "ledger",
                        not is_investment_cost,
                        cost=cash_entry.amount if is_investment_cost else ZERO,
                        cash_account_id=cash_account_id,
                    )
                )
    return rows, covered_dates


def _load_legacy_flows(
    *,
    positions: list[PortfolioPosition],
    ledger_covered_dates: set[tuple[int, date]],
    start_date: date,
    end_date: date,
) -> list[FlowRecord]:
    asset_to_position = {position.asset_id: position for position in positions}
    events = InvestmentAssetEvent.objects.filter(
        asset_id__in=asset_to_position,
        event_date__gte=start_date,
        event_date__lte=end_date,
    ).order_by("event_date", "id")
    rows: list[FlowRecord] = []
    for event in events:
        position = asset_to_position[event.asset_id]
        if (position.id, event.event_date) in ledger_covered_dates:
            continue
        external_amount = ZERO
        cost = ZERO
        income = ZERO
        external = False
        if event.event_type == InvestmentAssetEvent.EventType.CONTRIBUTION:
            external_amount = event.amount
            external = True
            kind = "contribution"
        elif event.event_type == InvestmentAssetEvent.EventType.WITHDRAWAL:
            external_amount = -event.amount
            external = True
            kind = "withdrawal"
        elif event.event_type == InvestmentAssetEvent.EventType.FEE:
            cost = event.amount
            kind = "cost"
        else:
            income = event.amount
            external = not event.is_reinvested
            external_amount = -event.amount if external else ZERO
            kind = "income_distribution" if external else "income_reinvested"
        rows.append(
            FlowRecord(
                position.id,
                event.event_date,
                external_amount,
                position.asset.currency,
                kind,
                "legacy_event",
                external,
                cost=cost,
                income=income,
            )
        )
    return rows


def load_performance_context(
    *, portfolio: Portfolio, start_date: date, end_date: date
) -> PerformanceContext:
    positions = list(
        PortfolioPosition.objects.filter(portfolio=portfolio, opened_on__lte=end_date)
        .filter(Q(closed_on__isnull=True) | Q(closed_on__gte=start_date))
        .select_related("asset", "instrument", "container", "ledger_account")
        .prefetch_related("ownership_periods__shares__member", "class_breakdown")
        .order_by("id")
    )
    cash_accounts = list(
        ContainerCashAccount.objects.filter(container__portfolio=portfolio)
        .select_related("ledger_account", "container")
        .order_by("id")
    )
    position_ids = [position.id for position in positions]
    instrument_ids = [position.instrument_id for position in positions]
    valuation_rows: dict[int, list[PositionValuation]] = {pk: [] for pk in position_ids}
    for row in PositionValuation.objects.filter(
        position_id__in=position_ids, valuation_date__lte=end_date
    ).order_by("valuation_date", "id"):
        valuation_rows[row.position_id].append(row)
    price_rows: dict[int, list[InstrumentPrice]] = {pk: [] for pk in instrument_ids}
    for row in InstrumentPrice.objects.filter(
        instrument_id__in=instrument_ids, price_date__lte=end_date
    ).order_by("price_date", "fetched_at", "id"):
        price_rows[row.instrument_id].append(row)
    account_ids = {
        int(position.ledger_account_id) for position in positions if position.ledger_account_id
    }
    cash_account_ids = {row.ledger_account_id for row in cash_accounts}
    account_ids.update(cash_account_ids)
    balance_dates, balance_values = _load_balances(
        account_ids=sorted(account_ids), end_date=end_date
    )
    ledger_flows, ledger_covered_dates = _load_ledger_flows(
        positions=positions,
        cash_account_ids=cash_account_ids,
        start_date=start_date,
        end_date=end_date,
    )
    flows = ledger_flows + _load_legacy_flows(
        positions=positions,
        ledger_covered_dates=ledger_covered_dates,
        start_date=start_date,
        end_date=end_date,
    )
    currencies = {portfolio.base_currency, "USD"}
    currencies.update(position.asset.currency for position in positions)
    currencies.update(position.instrument.quote_currency for position in positions)
    currencies.update(row.currency for row in cash_accounts)
    currencies.update(row.currency for row in flows)
    ownership_periods = {
        position.id: list(position.ownership_periods.all()) for position in positions
    }
    cash_ownership = _load_cash_ownership(portfolio=portfolio, cash_accounts=cash_accounts)
    pockets, ownership_shares = _load_position_pockets(portfolio=portfolio, positions=positions)
    inflation_rows = list(
        InflationIndex.objects.filter(region=InflationIndex.Region.ES, period__lte=end_date)
        .order_by("period")
        .values_list("period", "index")
    )
    return PerformanceContext(
        portfolio=portfolio,
        positions=positions,
        cash_accounts=cash_accounts,
        valuations=valuation_rows,
        prices=price_rows,
        valuation_dates={
            pk: [row.valuation_date for row in rows] for pk, rows in valuation_rows.items()
        },
        price_dates={pk: [row.price_date for row in rows] for pk, rows in price_rows.items()},
        balance_dates=balance_dates,
        balance_values=balance_values,
        flows=flows,
        ownership_periods=ownership_periods,
        cash_ownership=cash_ownership,
        pockets=pockets,
        ownership_shares=ownership_shares,
        fx_cache=build_fx_cache(currencies),
        inflation_rows=[(row_date, Decimal(index)) for row_date, index in inflation_rows],
    )


def _load_cash_ownership(
    *, portfolio: Portfolio, cash_accounts: list[ContainerCashAccount]
) -> dict[int, dict[int, Decimal]]:
    """Quien es dueno del efectivo de cada contenedor, segun Patrimonio.

    Una cuenta de efectivo no lleva titularidad propia, pero el activo que la respalda si:
    es el mismo `OwnershipLink` que ya usa `_bootstrap_ownership` para las posiciones. Leer
    de ahi evita pedir al usuario que declare dos veces la misma titularidad.

    Una cuenta sin activo, sin enlace o con titularidad dinamica se queda fuera del mapa:
    su reparto no se puede fijar sin congelar participaciones historicas, y publicarla como
    reparto exacto seria inventarlo.
    """
    account_ids = [row.ledger_account_id for row in cash_accounts]
    if not account_ids:
        return {}
    asset_by_account = {
        asset.accounting_account_id: asset
        for asset in Asset.objects.filter(
            user=portfolio.user, accounting_account_id__in=account_ids
        )
    }
    links = {
        link.target_id: link
        for link in OwnershipLink.objects.filter(
            user=portfolio.user,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id__in=[asset.id for asset in asset_by_account.values()],
        )
        .select_related("ownership__member")
        .prefetch_related("ownership__splits")
    }
    resolved: dict[int, dict[int, Decimal]] = {}
    for account_id in account_ids:
        asset = asset_by_account.get(account_id)
        link = links.get(asset.id) if asset else None
        if link is None:
            continue
        resolved_shares = _shares_of_ownership(link.ownership)
        if resolved_shares is None:
            continue
        resolved[account_id] = resolved_shares
    return resolved


def _load_position_pockets(
    *, portfolio: Portfolio, positions: list[PortfolioPosition]
) -> tuple[dict[int, OwnershipPockets], dict[int, dict[int, Decimal]]]:
    """Reconstruye el bote de las posiciones que mezclan titularidades.

    Solo se molesta con las que de verdad estan mezcladas: si todas las entradas de una
    posicion vienen de la misma titularidad, sus tramos ya la describen y contarla por
    unidades no cambiaria nada mientras si podria introducir diferencias de redondeo.
    """
    account_to_position = {
        int(position.ledger_account_id): position.id
        for position in positions
        if position.ledger_account_id
    }
    if not account_to_position:
        return {}, {}
    rows = (
        LedgerEntry.objects.filter(
            account_id__in=list(account_to_position),
            transaction__status=cast(str, LedgerTransaction.Status.POSTED),
        )
        .values_list(
            "account_id",
            "transaction__booking_date",
            "transaction__ownership_id",
            "side",
            "amount",
        )
        .order_by("transaction__booking_date", "transaction_id", "id")
    )
    movements: dict[int, list[UnitMovement]] = {}
    owners_seen: dict[int, set[int | None]] = {}
    for account_id, booking_date, ownership_id, side, amount in rows:
        position_id = account_to_position[int(account_id)]
        signed = amount if side == LedgerEntry.Side.DEBIT else -amount
        movements.setdefault(position_id, []).append(
            UnitMovement(on_date=booking_date, units=signed, ownership_id=ownership_id)
        )
        if signed > ZERO:
            owners_seen.setdefault(position_id, set()).add(ownership_id)
    mixed = {
        position_id
        for position_id, owners in owners_seen.items()
        if len({owner for owner in owners if owner is not None}) > 1
    }
    if not mixed:
        return {}, {}
    ownership_ids = {
        movement.ownership_id
        for position_id in mixed
        for movement in movements[position_id]
        if movement.ownership_id is not None
    }
    shares: dict[int, dict[int, Decimal]] = {}
    for ownership in Ownership.objects.filter(id__in=ownership_ids).prefetch_related(
        "splits", "member"
    ):
        resolved = _shares_of_ownership(ownership)
        if resolved is not None:
            shares[ownership.id] = resolved
    return {position_id: build_pockets(movements[position_id]) for position_id in mixed}, shares


def _shares_of_ownership(ownership: Ownership) -> dict[int, Decimal] | None:
    """Que fraccion toca a cada miembro en esta titularidad, o None si no se puede fijar.

    Una titularidad dinamica se queda fuera: su reparto depende de los ingresos de cada mes
    y publicarlo como fraccion exacta seria inventarlo.
    """
    if ownership.allocation_basis == Ownership.AllocationBasis.RECURRING_INCOME_12M:
        return None
    if ownership.kind == Ownership.Kind.INDIVIDUAL and ownership.member_id:
        shares = [(ownership.member_id, Decimal("100"))]
    else:
        shares = [(row.member_id, row.percent) for row in ownership.splits.all()]
    if not shares or sum(percent for _, percent in shares) != Decimal("100"):
        return None
    return {member_id: percent / Decimal("100") for member_id, percent in shares}


def _cash_ownership_factor(
    *, context: PerformanceContext, account_id: int, member_id: int | None
) -> Decimal | None:
    """La parte del efectivo de esta cuenta que toca a este miembro, o None si no consta."""
    if member_id is None:
        return Decimal("1")
    shares = context.cash_ownership.get(account_id)
    if shares is None:
        return None
    return shares.get(member_id, ZERO)


def _latest_before(rows: list, keys: list[date], target: date):
    index = bisect_right(keys, target) - 1
    return rows[index] if index >= 0 else None


def _balance_at(context: PerformanceContext, account_id: int, target: date) -> Decimal:
    dates = context.balance_dates.get(account_id, [])
    index = bisect_right(dates, target) - 1
    return context.balance_values[account_id][index] if index >= 0 else ZERO


def _fresher_fx_close(
    *, context: PerformanceContext, position: PortfolioPosition, price, target: date
) -> tuple[date, Decimal] | None:
    """La misma cotizacion, si llego como tipo de cambio y es mas reciente que el precio.

    Un bitcoin tiene un solo precio, pero entra en Core por dos puertas: el precio de
    instrumento del proveedor de mercado y el tipo de cambio BTC->EUR. Actualizar el
    cambio desde Patrimonio solo escribia la segunda, asi que la misma posicion valia una
    cosa alli y otra en Cartera hasta que pasaba el worker.
    """
    unit = (
        position.ledger_account.currency
        if position.ledger_account is not None
        else position.asset.currency
    )
    if not unit or unit == price.currency:
        return None
    # `build_fx_cache` deja cada par ordenado de mas reciente a mas antiguo.
    for rate_date, rate in context.fx_cache.get((unit, price.currency), []):
        if rate_date <= target:
            return (rate_date, rate) if rate_date > price.price_date else None
    return None


def resolve_preloaded_value(
    *, context: PerformanceContext, position: PortfolioPosition, target: date
) -> ResolvedValue | None:
    rows = context.valuations[position.id]
    keys = context.valuation_dates[position.id]
    end = bisect_right(keys, target)
    total = None
    if end:
        # Varias valoraciones del mismo día conviven (manual y derivada): manda la manual,
        # así que solo hace falta mirar la cola de esa fecha, no toda la historia.
        latest_date = keys[end - 1]
        same_day = rows[bisect_left(keys, latest_date, 0, end) : end]
        total = next(
            (row for row in reversed(same_day) if row.source == PositionValuation.Source.MANUAL),
            same_day[-1],
        )
    price = _latest_before(
        context.prices[position.instrument_id],
        context.price_dates[position.instrument_id],
        target,
    )
    if (
        position.tracking_style == PortfolioPosition.TrackingStyle.UNITS_BASED
        and position.ledger_account_id
        and price is not None
        and (total is None or price.price_date >= total.valuation_date)
    ):
        units = _balance_at(context, int(position.ledger_account_id), target)
        fresher = _fresher_fx_close(context=context, position=position, price=price, target=target)
        close = fresher[1] if fresher is not None else price.close
        observed_on = fresher[0] if fresher is not None else price.price_date
        return ResolvedValue(
            units * close,
            price.currency,
            observed_on,
            observed_on == target,
            "price:fx_rate" if fresher is not None else f"price:{price.source}",
        )
    if total is not None:
        divested = _divested_at(
            context=context,
            position=position,
            target=target,
            valuation_date=total.valuation_date,
        )
        if divested is not None:
            return divested
        return ResolvedValue(
            _anchored_value_at(context=context, position=position, target=target, valuation=total),
            total.currency,
            total.valuation_date,
            total.valuation_date == target,
            f"valuation:{total.source}",
        )
    carrying = _carrying_value_at(context=context, position=position, target=target)
    if carrying is not None:
        return carrying
    if target <= position.opened_on:
        # Nothing recorded yet and the position had not started: it contributed exactly
        # zero, not an unknown amount. Read as unknown, a single position opened
        # mid-period withheld the total and the TWR of the whole portfolio. Real data is
        # resolved first above, so this never masks a value.
        return ResolvedValue(ZERO, context.portfolio.base_currency, target, True, "not_open")
    return None


def _anchored_value_at(
    *,
    context: PerformanceContext,
    position: PortfolioPosition,
    target: date,
    valuation: PositionValuation,
) -> Decimal:
    """A valuation carried forward by the ledger movement booked since it was taken.

    A flat carry-forward is not flow-consistent: money added after the valuation does not
    lift it, so any subperiod that receives a contribution without a fresh valuation reads
    as a loss. Chained over a long history those false negatives compound — they took the
    full-history portfolio TWR to -87%. Anchoring on the valuation and adding the balance
    delta keeps value and flows in step, and mirrors what net worth already does for
    investment assets (`_get_effective_investment_asset_amount`).
    """
    if (
        position.tracking_style != PortfolioPosition.TrackingStyle.VALUE_BASED
        or not position.ledger_account_id
        or position.ledger_account is None
        or position.ledger_account.currency != valuation.currency
    ):
        return valuation.value
    account_id = int(position.ledger_account_id)
    if valuation.source == PositionValuation.Source.LEGACY_LEDGER:
        # A derived valuation *is* the balance, so read the balance and skip the anchor.
        # The stored figure is a mid-day snapshot taken right after its revaluation, while
        # the balance series is end-of-day: anchoring on it loses anything booked later the
        # same day, such as an internal transfer into the position.
        return _balance_at(context, account_id, target)
    return valuation.value + (
        _balance_at(context, account_id, target)
        - _balance_at(context, account_id, valuation.valuation_date)
    )


CARRYING_VALUE_SOURCE = "ledger:balance"


def _value_status(
    *, position: PortfolioPosition, native: ResolvedValue | None, target: date
) -> str:
    """Freshness of a position's value, or `at_cost` when nobody has ever valued it.

    A carrying value is the posted balance: an accounting fact that is current by
    definition and cannot go stale. What the position lacks is a valuation, not a fresh
    one. Ageing it turned two crowdfunding positions into permanent review noise, while an
    identical one read fresh only because it books interest every month.
    """
    if native is None:
        return "missing"
    if native.source == CARRYING_VALUE_SOURCE:
        return "at_cost"
    if (target - native.observed_on).days <= stale_days_for_position(position):
        return "fresh"
    return "stale"


def _observation_dates(
    *,
    context: PerformanceContext,
    positions: list[PortfolioPosition],
    start_date: date,
    end_date: date,
) -> list[date]:
    """Dates strictly inside the period where the scope actually observed a value.

    These are the only defensible subperiod boundaries for a linked return: a boundary
    without a fresh observation just carries the previous value forward and manufactures a
    flat subperiod, which distorts the chain instead of refining it.
    """
    dates: set[date] = set()
    for position in positions:
        for row in context.valuations[position.id]:
            if start_date < row.valuation_date < end_date:
                dates.add(row.valuation_date)
        if position.tracking_style == PortfolioPosition.TrackingStyle.UNITS_BASED:
            for price in context.prices[position.instrument_id]:
                if start_date < price.price_date < end_date:
                    dates.add(price.price_date)
    return sorted(dates)


def _value_series(
    *,
    context: PerformanceContext,
    positions: list[PortfolioPosition] | None,
    dates: list[date],
    member_id: int | None,
) -> list[DatedValue]:
    """Value of a scope at each date. `positions=None` means the whole portfolio.

    The scope has to match the flows the chain is fed, or the two describe different
    things: summing the portfolio while netting a single class's flows reported +37% for
    a class that had in fact lost money.
    """
    series: list[DatedValue] = []
    for target in sorted(set(dates)):
        if positions is not None:
            base_value: Decimal | None = ZERO
            for position in positions:
                part, _ = _position_value_base(
                    context=context, position=position, target=target, member_id=member_id
                )
                if part is None:
                    base_value = None
                    break
                base_value += part
        else:
            base_value, _, _ = _aggregate_value(context=context, target=target, member_id=member_id)
        # An unresolvable boundary is skipped rather than fatal: merging two subperiods
        # keeps the chain valid, while dropping the whole return would not.
        if base_value is not None:
            series.append(DatedValue(target, base_value))
    return series


def _divested_at(
    *,
    context: PerformanceContext,
    position: PortfolioPosition,
    target: date,
    valuation_date: date,
) -> ResolvedValue | None:
    """Zero for a value-based position the ledger reports as fully divested.

    A valuation describes a holding, so once the holding is gone the number stops being
    a stale estimate and becomes plain wrong: funds sold in 2022 kept reporting their
    last value years later and inflated every period long enough to include them. The
    ledger is the monetary source of truth, and it is only trusted over the valuation
    when the balance reached zero after that valuation was taken.
    """
    if (
        position.tracking_style != PortfolioPosition.TrackingStyle.VALUE_BASED
        or not position.ledger_account_id
    ):
        return None
    account_id = int(position.ledger_account_id)
    dates = context.balance_dates.get(account_id, [])
    index = bisect_right(dates, target) - 1
    if index < 0 or context.balance_values[account_id][index] != ZERO:
        return None
    divested_on = dates[index]
    if divested_on < valuation_date:
        return None
    return ResolvedValue(
        ZERO,
        context.portfolio.base_currency,
        divested_on,
        divested_on == target,
        "divested",
    )


def _carrying_value_at(
    *, context: PerformanceContext, position: PortfolioPosition, target: date
) -> ResolvedValue | None:
    """Ledger balance as carrying value of a value-based position with no valuation.

    Mirrors `valuations.resolve_position_valuation` so both read paths agree: a position
    funded only through accounting reports its posted balance instead of dropping out of
    the portfolio total. `observed_on` is the last date the balance moved, so freshness
    stays honest. Units-based positions are excluded, their account holds units.
    """
    if (
        position.tracking_style != PortfolioPosition.TrackingStyle.VALUE_BASED
        or not position.ledger_account_id
        or position.ledger_account is None
    ):
        return None
    account_id = int(position.ledger_account_id)
    dates = context.balance_dates.get(account_id, [])
    index = bisect_right(dates, target) - 1
    if index < 0:
        return None
    observed_on = dates[index]
    return ResolvedValue(
        context.balance_values[account_id][index],
        position.ledger_account.currency,
        observed_on,
        observed_on == target,
        "ledger:balance",
    )


def _ownership_factor(
    *, context: PerformanceContext, position_id: int, target: date, member_id: int | None
) -> Decimal:
    if member_id is None:
        return Decimal("1")
    # Un bote mezclado no se describe con un porcentaje: lo que es de cada uno son unidades,
    # y su peso cambia con cada compra. Donde hay bote manda el bote; el resto sigue con sus
    # tramos, que para una posicion de un solo dueno dicen exactamente lo mismo.
    pockets = context.pockets.get(position_id)
    if pockets is not None:
        share = member_share_at(
            pockets=pockets,
            target=target,
            member_id=member_id,
            shares_by_ownership=context.ownership_shares,
        )
        if share is not None:
            return share
    period = next(
        (
            row
            for row in context.ownership_periods.get(position_id, [])
            if row.start_date <= target and (row.end_date is None or row.end_date >= target)
        ),
        None,
    )
    if period is None:
        return ZERO
    share = next((row for row in period.shares.all() if row.member_id == member_id), None)
    return share.percent / Decimal("100") if share else ZERO


def _to_base(
    *, context: PerformanceContext, amount: Decimal, currency: str, target: date
) -> Decimal | None:
    try:
        return convert_currency_cached(
            amount,
            currency,
            context.portfolio.base_currency,
            rate_date=target,
            fx_cache=context.fx_cache,
        )
    except ValidationError:
        context.fx_issues.add(f"{currency}->{context.portfolio.base_currency}@{target.isoformat()}")
        return None


def _inflation_index(context: PerformanceContext, target: date) -> Decimal | None:
    rows = [row for row in context.inflation_rows if row[0] <= target.replace(day=1)]
    return rows[-1][1] if rows else None


def _position_value_base(
    *,
    context: PerformanceContext,
    position: PortfolioPosition,
    target: date,
    member_id: int | None,
) -> tuple[Decimal | None, ResolvedValue | None]:
    native = resolve_preloaded_value(context=context, position=position, target=target)
    if native is None:
        return None, None
    factor = _ownership_factor(
        context=context, position_id=position.id, target=target, member_id=member_id
    )
    return (
        _to_base(
            context=context,
            amount=native.value * factor,
            currency=native.currency,
            target=target,
        ),
        native,
    )


def _flow_factor(
    *, context: PerformanceContext, flow: FlowRecord, member_id: int | None
) -> Decimal:
    """La parte de este flujo que toca al miembro filtrado.

    Un flujo sin posicion es efectivo de contenedor: se reparte por la titularidad de su
    cuenta. Sin cuenta conocida o sin titularidad resoluble queda fuera del filtro en lugar
    de atribuirse entero a quien mire.
    """
    if flow.position_id is not None:
        return _ownership_factor(
            context=context,
            position_id=flow.position_id,
            target=flow.on_date,
            member_id=member_id,
        )
    if flow.cash_account_id is None:
        return Decimal("1") if member_id is None else ZERO
    factor = _cash_ownership_factor(
        context=context, account_id=flow.cash_account_id, member_id=member_id
    )
    return factor if factor is not None else ZERO


def _flow_base(
    *, context: PerformanceContext, flow: FlowRecord, member_id: int | None
) -> Decimal | None:
    factor = _flow_factor(context=context, flow=flow, member_id=member_id)
    return _to_base(
        context=context,
        amount=flow.amount * factor,
        currency=flow.currency,
        target=flow.on_date,
    )


def _cash_value_base(
    *, context: PerformanceContext, target: date, member_id: int | None
) -> tuple[Decimal | None, bool]:
    total = ZERO
    for link in context.cash_accounts:
        balance = _balance_at(context, link.ledger_account_id, target)
        factor = _cash_ownership_factor(
            context=context, account_id=link.ledger_account_id, member_id=member_id
        )
        if factor is None:
            # Sin titularidad resoluble el efectivo no es de nadie en concreto. Con saldo
            # cero no hay nada que repartir y la lectura sigue siendo exacta.
            if balance != 0:
                return None, False
            continue
        if factor == 0:
            continue
        converted = _to_base(
            context=context,
            amount=balance * factor,
            currency=link.currency,
            target=target,
        )
        if converted is None:
            return None, False
        total += converted
    return total, True


def _aggregate_value(
    *,
    context: PerformanceContext,
    target: date,
    member_id: int | None,
    scope_ids: set[int] | None = None,
) -> tuple[Decimal | None, bool, bool]:
    total = ZERO
    complete = True
    exact = True
    included = 0
    selected = (
        [position for position in context.positions if position.id in scope_ids]
        if scope_ids is not None
        else context.positions
    )
    for position in selected:
        factor = _ownership_factor(
            context=context,
            position_id=position.id,
            target=target,
            member_id=member_id,
        )
        if factor == 0:
            continue
        value, native = _position_value_base(
            context=context,
            position=position,
            target=target,
            member_id=member_id,
        )
        included += 1
        if value is None or native is None:
            complete = False
            continue
        total += value
        exact = exact and native.exact
    # El efectivo del contenedor no es de ninguna clase ni de ninguna posición concreta,
    # así que solo cuenta cuando se mira la cartera entera.
    cash_value, cash_complete = (
        _cash_value_base(context=context, target=target, member_id=member_id)
        if scope_ids is None
        else (ZERO, True)
    )
    complete = complete and cash_complete
    if cash_value is not None:
        total += cash_value
    has_boundary = bool(included or context.cash_accounts)
    return (total if has_boundary and complete else None), complete, exact


def _append_ownership_flows(
    *,
    context: PerformanceContext,
    positions: list[PortfolioPosition],
    start_date: date,
    end_date: date,
    member_id: int | None,
    external: list[DatedAmount],
    flow_rows: list[dict[str, Any]],
) -> bool:
    if member_id is None:
        return True
    complete = True
    for position in positions:
        periods = context.ownership_periods.get(position.id, [])
        for period in periods:
            if not (start_date < period.start_date <= end_date):
                continue
            # Solo un *cambio* de titularidad mueve valor sin mover dinero. El primer tramo
            # de una posicion no cambia nada: la posicion nace, y lo que la trajo ya esta
            # contado como compra. Emitir tambien ahi metia el valor entero de cada
            # posicion abierta dentro de la ventana como si fuese una aportacion nueva, y
            # por eso lo aportado por un miembro llegaba a superar lo aportado a la cartera
            # entera, de la que es una parte.
            has_previous = any(
                row.start_date < period.start_date
                and (row.end_date is None or row.end_date >= period.start_date - timedelta(days=1))
                for row in periods
            )
            if not has_previous:
                continue
            before = _ownership_factor(
                context=context,
                position_id=position.id,
                target=period.start_date - timedelta(days=1),
                member_id=member_id,
            )
            after = _ownership_factor(
                context=context,
                position_id=position.id,
                target=period.start_date,
                member_id=member_id,
            )
            delta = after - before
            if delta == 0:
                continue
            full_value, _ = _position_value_base(
                context=context,
                position=position,
                target=period.start_date,
                member_id=None,
            )
            if full_value is None:
                complete = False
                continue
            ownership_flow = full_value * delta
            external.append(DatedAmount(period.start_date, ownership_flow))
            flow_rows.append(
                {
                    "date": period.start_date.isoformat(),
                    "position_id": position.id,
                    "kind": "ownership_transfer",
                    "source": "ownership_period",
                    "external": True,
                    "amount_native": None,
                    "currency": context.portfolio.base_currency,
                    "amount_base": _quantize(ownership_flow),
                }
            )
    return complete


def _metric_block(
    *,
    context: PerformanceContext,
    start_date: date,
    end_date: date,
    member_id: int | None,
    position_id: int | None = None,
    scope_ids: set[int] | None = None,
) -> dict[str, Any]:
    # A scope can be one position or a set of them (a class, a container). Both read
    # flows as external to the scope rather than to the portfolio, which is what makes a
    # transfer between two members of the same scope net out instead of counting twice.
    scope = {position_id} if position_id else scope_ids
    selected_positions = (
        [position for position in context.positions if position.id in scope]
        if scope is not None
        else context.positions
    )
    position_ids = {position.id for position in selected_positions}
    opening_parts = [
        _position_value_base(
            context=context,
            position=position,
            target=start_date,
            member_id=member_id,
        )[0]
        for position in selected_positions
        if _ownership_factor(
            context=context,
            position_id=position.id,
            target=start_date,
            member_id=member_id,
        )
        > 0
    ]
    closing_parts = [
        _position_value_base(
            context=context,
            position=position,
            target=end_date,
            member_id=member_id,
        )[0]
        for position in selected_positions
        if _ownership_factor(
            context=context,
            position_id=position.id,
            target=end_date,
            member_id=member_id,
        )
        > 0
    ]
    cash_opening = cash_closing = None
    cash_opening_complete = cash_closing_complete = True
    # Container cash belongs to the portfolio, not to any scope inside it: a class holds
    # no cash of its own, so a scoped read must leave it out or it reports the portfolio.
    if scope is None:
        cash_opening, cash_opening_complete = _cash_value_base(
            context=context, target=start_date, member_id=member_id
        )
        cash_closing, cash_closing_complete = _cash_value_base(
            context=context, target=end_date, member_id=member_id
        )
    opening = sum((row for row in opening_parts if row is not None), ZERO)
    closing = sum((row for row in closing_parts if row is not None), ZERO)
    if cash_opening is not None:
        opening += cash_opening
    if cash_closing is not None:
        closing += cash_closing
    value_complete = all(row is not None for row in opening_parts + closing_parts) and bool(
        opening_parts or closing_parts or context.cash_accounts
    )
    value_complete = value_complete and cash_opening_complete and cash_closing_complete
    selected_flows = [
        flow
        for flow in context.flows
        if ((flow.position_id in position_ids) or (scope is None and flow.position_id is None))
        and start_date < flow.on_date <= end_date
    ]
    external: list[DatedAmount] = []
    costs = ZERO
    income = ZERO
    realized = ZERO
    realized_complete = True
    flow_rows = []
    for flow in selected_flows:
        base_amount = _flow_base(context=context, flow=flow, member_id=member_id)
        factor = _flow_factor(context=context, flow=flow, member_id=member_id)
        cost_base = _to_base(
            context=context,
            amount=flow.cost * factor,
            currency=flow.currency,
            target=flow.on_date,
        )
        income_base = _to_base(
            context=context,
            amount=flow.income * factor,
            currency=flow.currency,
            target=flow.on_date,
        )
        is_external = flow.position_external if scope is not None else flow.external
        if is_external and base_amount is not None:
            external.append(DatedAmount(flow.on_date, base_amount))
        if cost_base is not None:
            costs += cost_base
        if income_base is not None:
            income += income_base
        if flow.realized_pnl is None:
            if flow.kind == "withdrawal":
                realized_complete = False
        else:
            realized_base = _to_base(
                context=context,
                amount=flow.realized_pnl * factor,
                currency=flow.currency,
                target=flow.on_date,
            )
            if realized_base is not None:
                realized += realized_base
        flow_rows.append(
            {
                "date": flow.on_date.isoformat(),
                "position_id": flow.position_id,
                "kind": flow.kind,
                "source": flow.source,
                "external": is_external,
                "portfolio_external": flow.external,
                "amount_native": _quantize(flow.amount),
                "currency": flow.currency,
                "amount_base": _quantize(base_amount),
            }
        )
    ownership_flow_complete = _append_ownership_flows(
        context=context,
        positions=selected_positions,
        start_date=start_date,
        end_date=end_date,
        member_id=member_id,
        external=external,
        flow_rows=flow_rows,
    )
    value_complete = value_complete and ownership_flow_complete
    result = (
        monetary_result(opening_value=opening, closing_value=closing, external_flows=external)
        if value_complete
        else None
    )
    flow_dates = sorted({flow.on_date for flow in external})
    twr_values: list[DatedValue] = []
    twr_exact = value_complete
    twr_dates = sorted({start_date, *flow_dates, end_date})
    for target in twr_dates:
        if scope is not None:
            # Sum only the scope: a class or container holds no cash of its own, so the
            # portfolio-wide aggregate would fold in balances that are not part of it.
            base_value = ZERO
            exact = True
            for position in selected_positions:
                part, native = _position_value_base(
                    context=context, position=position, target=target, member_id=member_id
                )
                if part is None:
                    base_value = None
                    break
                base_value += part
                exact = exact and bool(native and native.exact)
        else:
            base_value, complete, exact = _aggregate_value(
                context=context, target=target, member_id=member_id
            )
            twr_exact = twr_exact and complete
        if base_value is None:
            twr_exact = False
            break
        if target in flow_dates and not exact:
            twr_exact = False
        twr_values.append(DatedValue(target, base_value))
    twr = chained_twr(valuations=twr_values, external_flows=external) if twr_exact else None
    method = "twr" if twr is not None else "modified_dietz"
    if twr is None and value_complete:
        # Chain the subperiods the valuations do delimit before giving up on time
        # weighting. Requiring an observation on every flow date means a position funded
        # weekly never gets a TWR, and the whole-period Dietz that replaced it is
        # money-weighted: on the reference position it reported 11.07% against 21.57%.
        linked_series = _value_series(
            context=context,
            positions=selected_positions if scope is not None else None,
            dates=[
                start_date,
                *_observation_dates(
                    context=context,
                    positions=selected_positions,
                    start_date=start_date,
                    end_date=end_date,
                ),
                end_date,
            ],
            member_id=member_id,
        )
        twr = linked_dietz(valuations=linked_series, external_flows=external)
        method = "linked_dietz" if twr is not None else "modified_dietz"
    if twr is None and value_complete:
        twr = modified_dietz(
            opening_value=opening,
            closing_value=closing,
            external_flows=external,
            start_date=start_date,
            end_date=end_date,
        )
    investor_flows = [DatedAmount(start_date, -opening)]
    investor_flows.extend(DatedAmount(row.on_date, -row.amount) for row in external)
    investor_flows.append(DatedAmount(end_date, closing))
    mwr = xirr(investor_flows) if value_complete else None
    nominal = twr
    real = real_return(
        nominal_return=nominal,
        opening_index=_inflation_index(context, start_date),
        closing_index=_inflation_index(context, end_date),
    )
    net_contributed = sum((row.amount for row in external), ZERO)
    return {
        "period": {"from": start_date.isoformat(), "to": end_date.isoformat()},
        "currency": context.portfolio.base_currency,
        "opening_value": _quantize(opening if value_complete else None),
        "closing_value": _quantize(closing if value_complete else None),
        "covered_opening_value": _quantize(opening),
        "covered_closing_value": _quantize(closing),
        "net_contributed": _quantize(net_contributed),
        "monetary_result": _quantize(result),
        "gross_result": _quantize(result + costs if result is not None else None),
        "costs": _quantize(costs),
        "income": _quantize(income),
        "realized_pnl": _quantize(realized) if realized_complete else None,
        "unrealized_pnl": (
            _quantize(result - realized) if result is not None and realized_complete else None
        ),
        "return": {
            "nominal": _quantize(nominal),
            "real": _quantize(real),
            "twr": _quantize(twr),
            "mwr_xirr": _quantize(mwr),
            # MWR/XIRR is already an annual rate; TWR is cumulative, so it needs its own
            # annualized companion before the two can sit next to each other.
            "twr_annualized": _quantize(
                annualized(total_return=twr, days=(end_date - start_date).days)
            ),
            "method": method if twr is not None else "unavailable",
            "estimated": method in {"linked_dietz", "modified_dietz"} and twr is not None,
        },
        "coverage": {
            "value": "complete" if value_complete else "partial",
            "opening_positions": {
                "covered": sum(row is not None for row in opening_parts),
                "total": len(opening_parts),
            },
            "closing_positions": {
                "covered": sum(row is not None for row in closing_parts),
                "total": len(closing_parts),
            },
            "cash": (
                "complete"
                if cash_opening_complete and cash_closing_complete
                else "ownership_unavailable"
                if member_id is not None
                else "partial"
            ),
            "twr": "exact" if method == "twr" else "estimated" if twr else "unavailable",
            "mwr": "available" if mwr is not None else "unavailable",
            "realized_pnl": "complete" if realized_complete else "partial",
            "fx": "complete" if not context.fx_issues else "partial",
        },
        "flows": flow_rows,
    }


def build_portfolio_performance(
    *,
    portfolio: Portfolio,
    start_date: date,
    end_date: date,
    member_id: int | None = None,
    context: PerformanceContext | None = None,
    scope_ids: set[int] | None = None,
) -> dict[str, Any]:
    context = context or load_performance_context(
        portfolio=portfolio, start_date=start_date, end_date=end_date
    )
    result = _metric_block(
        context=context,
        start_date=start_date,
        end_date=end_date,
        member_id=member_id,
        scope_ids=scope_ids,
    )
    result["member_id"] = member_id
    result["fx_issues"] = sorted(context.fx_issues)
    return result


def _build_positions_from_context(
    *,
    context: PerformanceContext,
    start_date: date,
    end_date: date,
    member_id: int | None,
) -> list[dict[str, Any]]:
    rows = []
    for position in context.positions:
        if member_id is not None and not any(
            period.start_date <= end_date
            and (period.end_date is None or period.end_date >= start_date)
            and any(share.member_id == member_id for share in period.shares.all())
            for period in context.ownership_periods.get(position.id, [])
        ):
            continue
        metrics = _metric_block(
            context=context,
            start_date=start_date,
            end_date=end_date,
            member_id=member_id,
            position_id=position.id,
        )
        native = resolve_preloaded_value(context=context, position=position, target=end_date)
        result_base = Decimal(metrics["monetary_result"]) if metrics["monetary_result"] else None
        local_result = None
        closing_fx = None
        if native and result_base is not None:
            position_flows = [
                flow
                for flow in context.flows
                if flow.position_id == position.id
                and start_date < flow.on_date <= end_date
                and flow.position_external
            ]
            opening_native = resolve_preloaded_value(
                context=context, position=position, target=start_date
            )
            same_currency_flows = all(flow.currency == native.currency for flow in position_flows)
            if (
                opening_native
                and opening_native.currency == native.currency
                and same_currency_flows
            ):
                opening_factor = _ownership_factor(
                    context=context,
                    position_id=position.id,
                    target=start_date,
                    member_id=member_id,
                )
                closing_factor = _ownership_factor(
                    context=context,
                    position_id=position.id,
                    target=end_date,
                    member_id=member_id,
                )
                local_result = monetary_result(
                    opening_value=opening_native.value * opening_factor,
                    closing_value=native.value * closing_factor,
                    external_flows=[
                        DatedAmount(
                            flow.on_date,
                            flow.amount
                            * _ownership_factor(
                                context=context,
                                position_id=position.id,
                                target=flow.on_date,
                                member_id=member_id,
                            ),
                        )
                        for flow in position_flows
                    ],
                )
                converted_unit = _to_base(
                    context=context,
                    amount=Decimal("1"),
                    currency=native.currency,
                    target=end_date,
                )
                closing_fx = converted_unit
        asset_result, fx_result = (
            decompose_result(
                total_result_base=result_base,
                local_result=local_result,
                closing_fx_rate=closing_fx,
            )
            if result_base is not None
            else (None, None)
        )
        rows.append(
            {
                "position_id": position.id,
                "instrument_id": position.instrument_id,
                # The asset name is the one the user gave it in Patrimonio; the
                # instrument may be a shared canonical record with a generic name, which
                # made the same holding read differently in the two views.
                "instrument_name": position.asset.name,
                "asset_class": position.effective_asset_class,
                # Reparto interno cuando la posición no es de una sola clase (una cartera
                # de roboadvisor, un fondo mixto). Solo lo usa la composición.
                "class_breakdown": [
                    {"asset_class": row.asset_class, "percent": str(row.percent)}
                    for row in position.class_breakdown.all()
                ],
                "container_id": position.container_id,
                "container_name": position.container.name,
                "status": position.status,
                "tracking_style": position.tracking_style,
                "native_value": (
                    _quantize(
                        native.value
                        * _ownership_factor(
                            context=context,
                            position_id=position.id,
                            target=end_date,
                            member_id=member_id,
                        )
                    )
                    if native
                    else None
                ),
                "native_currency": native.currency if native else None,
                # What the holding is denominated in, which for crypto is the coin
                # itself. The valuation currency above is what it is *worth in*, so
                # filtering by "BTC" needs this one, not that one.
                "holding_currency": (
                    position.ledger_account.currency
                    if position.ledger_account_id and position.ledger_account
                    else position.asset.currency
                ),
                "observed_on": native.observed_on.isoformat() if native else None,
                "value_status": _value_status(position=position, native=native, target=end_date),
                "performance": metrics,
                "attribution": {
                    "asset": _quantize(asset_result),
                    "fx": _quantize(fx_result),
                    "total": _quantize(result_base),
                    "method": "closing_fx_residual" if asset_result is not None else "unavailable",
                },
            }
        )
    return rows


def build_portfolio_positions(
    *,
    portfolio: Portfolio,
    start_date: date,
    end_date: date,
    member_id: int | None = None,
    context: PerformanceContext | None = None,
) -> list[dict[str, Any]]:
    context = context or load_performance_context(
        portfolio=portfolio, start_date=start_date, end_date=end_date
    )
    return _build_positions_from_context(
        context=context,
        start_date=start_date,
        end_date=end_date,
        member_id=member_id,
    )


def timeline_context_start(*, portfolio: Portfolio, start_date: date) -> date:
    """Desde dónde tiene que cargarse el contexto para que el timeline sea correcto.

    Todos los consumidores de `context.flows` acotan por ventana en el punto de uso, así
    que un contexto más ancho es seguro y permite que el workspace cargue uno solo en vez
    de dos: era el mayor coste fijo de cada cambio de filtro.
    """
    inception, _ = default_performance_period(portfolio)
    return min(inception, start_date)


def build_portfolio_timeline(
    *,
    portfolio: Portfolio,
    start_date: date,
    end_date: date,
    member_id: int | None = None,
    context: PerformanceContext | None = None,
    scope_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    dates = timeline_dates(start_date, end_date)
    # The chart puts capital contributed next to value, so the contributed series has to
    # run from inception: over a one-year window it otherwise restarts at zero and the
    # comparison is meaningless, since the value line carries every year of history.
    context = context or load_performance_context(
        portfolio=portfolio,
        start_date=timeline_context_start(portfolio=portfolio, start_date=start_date),
        end_date=end_date,
    )
    rows = []
    # Con un filtro de inventario activo la serie describe ese subconjunto, así que los
    # flujos del efectivo del contenedor —que no es de ninguna clase— quedan fuera.
    external = [
        flow
        for flow in context.flows
        if flow.external and (scope_ids is None or flow.position_id in scope_ids)
    ]
    opening_value, opening_complete, _ = _aggregate_value(
        context=context, target=start_date, member_id=member_id, scope_ids=scope_ids
    )
    contributed_before = sum(
        (
            _flow_base(context=context, flow=flow, member_id=member_id) or ZERO
            for flow in external
            if flow.on_date <= start_date
        ),
        ZERO,
    )
    for target in dates:
        value, complete, _ = _aggregate_value(
            context=context, target=target, member_id=member_id, scope_ids=scope_ids
        )
        cumulative = sum(
            (
                _flow_base(context=context, flow=flow, member_id=member_id) or ZERO
                for flow in external
                if start_date < flow.on_date <= target
            ),
            ZERO,
        )
        rows.append(
            {
                "date": target.isoformat(),
                "value": _quantize(value),
                "net_contributed": _quantize(cumulative),
                "contributed_to_date": _quantize(contributed_before + cumulative),
                "monetary_result": (
                    _quantize(value - (opening_value or ZERO) - cumulative)
                    if complete and opening_complete and value is not None
                    else None
                ),
                "coverage": "complete" if complete else "partial",
            }
        )
    return rows


def build_portfolio_quality(
    *,
    portfolio: Portfolio,
    start_date: date,
    end_date: date,
    member_id: int | None = None,
    context: PerformanceContext | None = None,
    scope_ids: set[int] | None = None,
    performance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or load_performance_context(
        portfolio=portfolio, start_date=start_date, end_date=end_date
    )
    # De todo el bloque de métricas aquí solo se leen el periodo y la cobertura, así que
    # recalcularlo entero para eso costaba tanto como el hero.
    metrics = performance or _metric_block(
        context=context,
        start_date=start_date,
        end_date=end_date,
        member_id=member_id,
        scope_ids=scope_ids,
    )
    # Solo es trabajo del usuario el efectivo con saldo cuya titularidad no consta en
    # Patrimonio. Antes bastaba con tener efectivo para que el aviso saltara en todas las
    # titularidades, que es ruido: la cuenta si tenia dueno, solo que nadie lo miraba.
    cash_ownership_missing = member_id is not None and any(
        link.ledger_account_id not in context.cash_ownership
        and (
            _balance_at(context, link.ledger_account_id, end_date) != 0
            or _balance_at(context, link.ledger_account_id, start_date) != 0
        )
        for link in context.cash_accounts
    )
    # Una posicion sin titularidad no aparece en la vista de nadie, pero su historia sigue
    # dentro del total. Filtrando por titular eso hace que las partes no sumen el todo sin
    # que nada lo explique, y archivada o no da igual: lo que descuadra son sus flujos
    # pasados. Por eso se cuenta aparte de `ownership_missing`, que solo mira lo vivo.
    unattributed = sum(
        1
        for position in context.positions
        if not context.ownership_periods.get(position.id)
        and (scope_ids is None or position.id in scope_ids)
    )
    fresh = stale = missing = at_cost = ownership_missing = scoped_total = 0
    for position in context.positions:
        if scope_ids is not None and position.id not in scope_ids:
            continue
        if position.status == PortfolioPosition.Status.ARCHIVED:
            # An archived position is out of the portfolio: its freshness and its missing
            # ownership are not work the user can act on, and counting them turned the
            # review banner into noise.
            continue
        if not context.ownership_periods.get(position.id):
            ownership_missing += 1
        if (
            member_id is not None
            and _ownership_factor(
                context=context,
                position_id=position.id,
                target=end_date,
                member_id=member_id,
            )
            == 0
        ):
            continue
        scoped_total += 1
        native = resolve_preloaded_value(context=context, position=position, target=end_date)
        status = _value_status(position=position, native=native, target=end_date)
        if status == "missing":
            missing += 1
        elif status == "stale":
            stale += 1
        elif status == "at_cost":
            at_cost += 1
        else:
            fresh += 1
    return {
        "period": metrics["period"],
        "status": (
            "needs_review"
            # Lo no atribuido solo pide revision cuando se esta mirando por titular: es ahi
            # donde descuadra la lectura. Sin filtro no sobra nada y marcarlo seria ruido.
            if missing
            or ownership_missing
            or (member_id is not None and unattributed)
            or cash_ownership_missing
            or context.fx_issues
            else "stale"
            if stale
            else "ready"
        ),
        "positions": {
            "total": scoped_total,
            "fresh": fresh,
            "stale": stale,
            "missing": missing,
            "at_cost": at_cost,
        },
        "ownership_missing": ownership_missing,
        "ownership_unattributed": unattributed,
        "cash_ownership_missing": cash_ownership_missing,
        "metric_coverage": metrics["coverage"],
        "fx_issues": sorted(context.fx_issues),
        "cache": {"strategy": "none", "read_model": "rebuildable"},
    }


def build_holding_threads(
    *, portfolio: Portfolio, start_date: date, end_date: date, context: PerformanceContext | None
) -> list[dict[str, Any]]:
    """El mismo activo bajo la misma titularidad, aunque haya cambiado de custodio.

    Una posicion vive en un solo contenedor, asi que mudar un activo de un exchange a otro
    abre una posicion nueva y parte su historia en dos. Leido por posicion, lo que entra
    desde el custodio anterior es una aportacion y la rentabilidad arranca el dia de la
    mudanza. Agrupar por (instrumento, titularidad) devuelve el hilo entero: el traspaso
    queda dentro del ambito y se anula solo.

    La titularidad forma parte de la clave a proposito. Pasar bitcoin propio a compartido no
    es una mudanza sino una cesion de la mitad, y debe seguir contando como salida del hilo
    de quien lo cede.
    """
    context = context or load_performance_context(
        portfolio=portfolio, start_date=start_date, end_date=end_date
    )
    grouped: dict[tuple[int, int], dict[str, Any]] = {}
    for position in context.positions:
        for period in context.ownership_periods.get(position.id, []):
            key = (position.instrument_id, period.ownership_id)
            thread = grouped.setdefault(
                key,
                {
                    "instrument_id": position.instrument_id,
                    "instrument_name": position.instrument.name,
                    "asset_class": position.effective_asset_class,
                    "ownership_id": period.ownership_id,
                    "position_ids": set(),
                    "containers": {},
                    "since": period.start_date,
                },
            )
            thread["position_ids"].add(position.id)
            thread["containers"][position.container_id] = position.container.name
            thread["since"] = min(thread["since"], period.start_date)
    ownerships = {
        row.id: row
        for row in Ownership.objects.filter(id__in={key[1] for key in grouped}).prefetch_related(
            "splits__member", "member"
        )
    }
    rows = []
    for thread in grouped.values():
        ownership = ownerships.get(thread["ownership_id"])
        scope_ids = cast(set[int], thread["position_ids"])
        value, _, _ = _aggregate_value(
            context=context, target=end_date, member_id=None, scope_ids=scope_ids
        )
        label = ""
        if ownership is not None:
            label = (
                ownership.member.name
                if ownership.kind == Ownership.Kind.INDIVIDUAL and ownership.member
                else " + ".join(
                    f"{row.member.name} {row.percent:g}%" for row in ownership.splits.all()
                )
            )
        containers = cast(dict[int, str], thread["containers"])
        rows.append(
            {
                "instrument_id": thread["instrument_id"],
                "instrument_name": thread["instrument_name"],
                "asset_class": thread["asset_class"],
                "ownership_id": thread["ownership_id"],
                "ownership_kind": ownership.kind if ownership else "",
                "ownership_label": label,
                "position_ids": sorted(scope_ids),
                "containers": [containers[key] for key in sorted(containers)],
                # Un hilo repartido entre custodios es justo el que se leia mal por
                # posicion, asi que la interfaz necesita distinguirlo de un vistazo.
                "spans_custodians": len(containers) > 1,
                "since": cast(date, thread["since"]).isoformat(),
                "value_base": _quantize(value) if value is not None else None,
                "currency": portfolio.base_currency,
            }
        )
    rows.sort(key=lambda row: (row["instrument_name"], row["ownership_label"]))
    return rows


def build_portfolio_overview(
    *,
    portfolio: Portfolio,
    start_date: date,
    end_date: date,
    member_id: int | None = None,
    context: PerformanceContext | None = None,
    scope_ids: set[int] | None = None,
    performance: dict[str, Any] | None = None,
    position_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    context = context or load_performance_context(
        portfolio=portfolio, start_date=start_date, end_date=end_date
    )
    # El hero es una proyección de las mismas dos cosas que ya calcula el workspace, así
    # que se aceptan hechas: recalcularlas costaba tanto como todo lo demás junto.
    performance = performance or _metric_block(
        context=context,
        start_date=start_date,
        end_date=end_date,
        member_id=member_id,
        scope_ids=scope_ids,
    )
    rows = (
        position_rows
        if position_rows is not None
        else _build_positions_from_context(
            context=context,
            start_date=start_date,
            end_date=end_date,
            member_id=member_id,
        )
    )
    positions = [row for row in rows if scope_ids is None or row["position_id"] in scope_ids]
    return {
        "period": performance["period"],
        "member_id": member_id,
        "currency": portfolio.base_currency,
        "value": performance["closing_value"],
        "covered_value": performance["covered_closing_value"],
        "net_contributed": performance["net_contributed"],
        "monetary_result": performance["monetary_result"],
        "return": performance["return"],
        "coverage": performance["coverage"],
        "position_count": len(positions),
        "fresh_position_count": sum(row["value_status"] == "fresh" for row in positions),
    }


def default_performance_period(portfolio: Portfolio) -> tuple[date, date]:
    end_date = timezone.localdate()
    first = portfolio.positions.order_by("opened_on").values_list("opened_on", flat=True).first()
    return first or end_date, end_date
