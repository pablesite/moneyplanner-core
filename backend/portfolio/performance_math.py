from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True)
class DatedAmount:
    on_date: date
    amount: Decimal


@dataclass(frozen=True)
class DatedValue:
    on_date: date
    value: Decimal


def monetary_result(
    *, opening_value: Decimal, closing_value: Decimal, external_flows: list[DatedAmount]
) -> Decimal:
    """Return portfolio gain; positive flows are contributions into the portfolio."""
    return closing_value - opening_value - sum((row.amount for row in external_flows), ZERO)


def modified_dietz(
    *,
    opening_value: Decimal,
    closing_value: Decimal,
    external_flows: list[DatedAmount],
    start_date: date,
    end_date: date,
) -> Decimal | None:
    days = (end_date - start_date).days
    if days <= 0:
        return None
    weighted_flows = ZERO
    for flow in external_flows:
        remaining_days = Decimal((end_date - flow.on_date).days)
        weighted_flows += flow.amount * remaining_days / Decimal(days)
    denominator = opening_value + weighted_flows
    if denominator == 0:
        return None
    return (
        monetary_result(
            opening_value=opening_value,
            closing_value=closing_value,
            external_flows=external_flows,
        )
        / denominator
    )


def chained_twr(
    *, valuations: list[DatedValue], external_flows: list[DatedAmount]
) -> Decimal | None:
    """Chain valuation-to-valuation returns, neutralizing flows on each valuation date."""
    if len(valuations) < 2:
        return None
    values = sorted(valuations, key=lambda row: row.on_date)
    flow_by_date: dict[date, Decimal] = {}
    for flow in external_flows:
        flow_by_date[flow.on_date] = flow_by_date.get(flow.on_date, ZERO) + flow.amount
    value_dates = {row.on_date for row in values}
    if any(flow.on_date not in value_dates for flow in external_flows):
        return None
    factor = ONE
    for previous, current in zip(values, values[1:], strict=False):
        if previous.value == 0:
            return None
        period_flow = flow_by_date.get(current.on_date, ZERO)
        factor *= (current.value - period_flow) / previous.value
    return factor - ONE


def xirr(cash_flows: list[DatedAmount]) -> Decimal | None:
    """Solve annualized IRR with bounded bisection; investor outflows are negative."""
    if len(cash_flows) < 2:
        return None
    flows = sorted(cash_flows, key=lambda row: row.on_date)
    if not any(row.amount < 0 for row in flows) or not any(row.amount > 0 for row in flows):
        return None
    origin = flows[0].on_date

    def npv(rate: Decimal) -> Decimal:
        total = ZERO
        for row in flows:
            years = Decimal((row.on_date - origin).days) / Decimal("365")
            try:
                discount = Decimal(float(ONE + rate) ** float(years))
            except (InvalidOperation, OverflowError, ValueError):
                return Decimal("Infinity")
            total += row.amount / discount
        return total

    low = Decimal("-0.999999")
    high = Decimal("10")
    low_value = npv(low)
    high_value = npv(high)
    while low_value * high_value > 0 and high < Decimal("1000000"):
        high *= Decimal("10")
        high_value = npv(high)
    if low_value * high_value > 0:
        return None
    for _ in range(160):
        middle = (low + high) / Decimal("2")
        middle_value = npv(middle)
        if abs(middle_value) < Decimal("0.00000001"):
            return middle
        if low_value * middle_value <= 0:
            high = middle
        else:
            low = middle
            low_value = middle_value
    return (low + high) / Decimal("2")


def real_return(
    *, nominal_return: Decimal | None, opening_index: Decimal | None, closing_index: Decimal | None
) -> Decimal | None:
    if (
        nominal_return is None
        or opening_index is None
        or closing_index is None
        or opening_index <= 0
    ):
        return None
    inflation_factor = closing_index / opening_index
    if inflation_factor == 0:
        return None
    return (ONE + nominal_return) / inflation_factor - ONE


def decompose_result(
    *, total_result_base: Decimal, local_result: Decimal | None, closing_fx_rate: Decimal | None
) -> tuple[Decimal | None, Decimal | None]:
    if local_result is None or closing_fx_rate is None:
        return None, None
    asset_result = local_result * closing_fx_rate
    return asset_result, total_result_base - asset_result
