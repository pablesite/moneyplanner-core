from __future__ import annotations

import calendar
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import cast

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from accounting.models import LedgerEntry, LedgerTransaction
from core.services import build_fx_cache, convert_currency_cached
from memberships.models import Ownership, OwnershipAllocationSnapshot, OwnershipLink
from memberships.services_allocations import resolve_ownership_allocation
from net_worth.services_assets_core import get_effective_asset_amount
from net_worth.services_liabilities_core import get_effective_liability_amount
from net_worth.models import Asset, Liability

from .models import (
    AnnualExpenseEntry,
    MonthlyClose,
    SettlementAccount,
    SettlementProfile,
    SettlementSnapshot,
    SettlementTransferRecommendation,
    SettlementWalletNormalization,
)
from .services import effective_annual_expense_entries, planned_expense_monthly_distribution
from .services_settlement import (
    _wallet_normalization_deltas,
    build_settlement_readiness,
    expected_expense_settlement_role,
    resolve_expense_settlement_destination,
)

ZERO = Decimal("0")
HUNDRED = Decimal("100")
MONEY_STEP = Decimal("0.01")


@dataclass(frozen=True)
class SettlementCreditCard:
    """Automatic settlement participant for an accounting-backed credit card."""

    liability: Liability

    @property
    def id(self) -> int:
        # Snapshot IDs must not collide with configured SettlementAccount IDs.
        return -self.liability.id

    @property
    def asset_id(self) -> None:
        return None

    @property
    def liability_id(self) -> int:
        return self.liability.id

    @property
    def name(self) -> str:
        return self.liability.name

    @property
    def role(self) -> str:
        return "credit_card"

    @property
    def currency(self) -> str:
        return self.liability.currency

    @property
    def member_id(self) -> None:
        return None

    @property
    def accounting_account_id(self) -> int | None:
        return self.liability.accounting_account_id


@dataclass(frozen=True)
class SettlementInvestmentPosition:
    """Automatic non-routable investment or broker-cash settlement participant."""

    asset: Asset
    role: str

    @property
    def id(self) -> int:
        namespace = 1_000_000 if self.role == "investment_position" else 2_000_000
        return -(namespace + self.asset.id)

    @property
    def asset_id(self) -> int:
        return self.asset.id

    @property
    def liability_id(self) -> None:
        return None

    @property
    def name(self) -> str:
        return self.asset.name

    @property
    def currency(self) -> str:
        return self.asset.currency

    @property
    def member_id(self) -> None:
        return None

    @property
    def accounting_account_id(self) -> int | None:
        return self.asset.accounting_account_id


SettlementParticipant = SettlementAccount | SettlementCreditCard | SettlementInvestmentPosition


def _participant_ledger_account_id(account: SettlementParticipant) -> int | None:
    if isinstance(account, (SettlementCreditCard, SettlementInvestmentPosition)):
        return account.accounting_account_id
    return account.asset.accounting_account_id


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def _money_string(value: Decimal) -> str:
    return str(_money(value))


def _next_period(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _allocation(
    *,
    ownership: Ownership,
    year: int,
    month: int,
    cache: dict[tuple[int, int, int], tuple[dict[int, Decimal] | None, dict]],
) -> tuple[dict[int, Decimal] | None, dict]:
    key = (ownership.id, year, month)
    if key not in cache:
        result = resolve_ownership_allocation(
            ownership=ownership,
            fiscal_year=year,
            month=month,
            persist=False,
        )
        vector = None
        if result["status"] != "blocked":
            vector = {
                int(row["member_id"]): Decimal(str(row["percent"])) for row in result["shares"]
            }
        cache[key] = vector, result
    return cache[key]


def _allocate(
    amount: Decimal,
    vector: dict[int, Decimal],
) -> dict[int, Decimal]:
    rows = sorted(vector.items())
    allocated = ZERO
    result: dict[int, Decimal] = {}
    for index, (member_id, percent) in enumerate(rows):
        share = amount - allocated if index == len(rows) - 1 else _money(amount * percent / HUNDRED)
        result[member_id] = share
        allocated += share
    return result


def _serialized_allocations(
    cache: dict[tuple[int, int, int], tuple[dict[int, Decimal] | None, dict]],
) -> list[dict]:
    rows = []
    for (_ownership_id, _year, _month), (_vector, result) in sorted(cache.items()):
        rows.append(result)
    return rows


def _opening_position(
    *,
    profile: SettlementProfile,
    close_start: date,
) -> tuple[
    str, date, dict[tuple[int, int], Decimal], dict[int, Decimal], SettlementSnapshot | None
]:
    previous = (
        SettlementSnapshot.objects.filter(
            profile=profile,
            status=SettlementSnapshot.Status.READY,
            monthly_close__status__in=[MonthlyClose.Status.FINALIZED, MonthlyClose.Status.LOCKED],
            period_end__lt=close_start,
        )
        .select_related("monthly_close")
        .order_by("-period_end", "-id")
        .first()
    )
    account_members: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
    member_totals: dict[int, Decimal] = defaultdict(Decimal)
    if previous is not None:
        for row in previous.account_balances:
            for share in row.get("closing_by_member", []):
                amount = Decimal(str(share["amount"]))
                key = (int(row["account_id"]), int(share["member_id"]))
                account_members[key] += amount
                member_totals[key[1]] += amount
        return (
            "previous_close",
            previous.period_end + timedelta(days=1),
            account_members,
            member_totals,
            previous,
        )

    if profile.activation_date is None:
        return "activation", close_start, account_members, member_totals, None
    for row in profile.opening_balances.all():
        amount = Decimal(row.amount)
        key = (row.account_id, row.member_id)
        account_members[key] += amount
        member_totals[row.member_id] += amount
    for adjustment in profile.opening_adjustments.all():
        amount = Decimal(adjustment.amount)
        key = (adjustment.account_id, adjustment.member_id)
        account_members[key] += amount
        member_totals[adjustment.member_id] += amount
    return (
        "activation",
        profile.activation_date + timedelta(days=1),
        account_members,
        member_totals,
        None,
    )


def _account_ownerships(*, user, accounts: list[SettlementParticipant]) -> dict[int, Ownership]:
    asset_ids = [row.asset_id for row in accounts if row.asset_id is not None]
    liability_ids = [row.liability_id for row in accounts if isinstance(row, SettlementCreditCard)]
    links = (
        OwnershipLink.objects.filter(
            user=user,
            target_type=OwnershipLink.TargetType.ASSET,
            target_id__in=asset_ids,
        )
        .select_related("ownership", "ownership__member")
        .prefetch_related("ownership__splits", "ownership__splits__member")
    )
    by_asset = {row.target_id: row.ownership for row in links}
    liability_links = (
        OwnershipLink.objects.filter(
            user=user,
            target_type=OwnershipLink.TargetType.LIABILITY,
            target_id__in=liability_ids,
        )
        .select_related("ownership", "ownership__member")
        .prefetch_related("ownership__splits", "ownership__splits__member")
    )
    by_liability = {row.target_id: row.ownership for row in liability_links}
    ownerships = {
        row.id: by_asset[row.asset_id]
        for row in accounts
        if row.asset_id is not None and row.asset_id in by_asset
    }
    ownerships.update(
        {
            row.id: by_liability[row.liability_id]
            for row in accounts
            if isinstance(row, SettlementCreditCard) and row.liability_id in by_liability
        }
    )
    return ownerships


def _credit_card_participants(
    *,
    user,
    profile: SettlementProfile,
    movement_start: date,
    close_end: date,
    previous: SettlementSnapshot | None,
) -> list[SettlementCreditCard]:
    """Return cards that carry debt or have participated since the last baseline."""

    liabilities = list(
        Liability.objects.filter(
            user=user,
            category=Liability.Category.CREDIT_CARD,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id__isnull=False,
        ).order_by("id")
    )
    if not liabilities:
        return []
    active_ledger_ids = set(
        LedgerEntry.objects.filter(
            transaction__user=user,
            transaction__status=LedgerTransaction.Status.POSTED,
            transaction__booking_date__gte=movement_start,
            transaction__booking_date__lte=close_end,
            account_id__in=[row.accounting_account_id for row in liabilities],
        ).values_list("account_id", flat=True)
    )
    previous_ids = {
        -int(row["account_id"])
        for row in (previous.account_balances if previous is not None else [])
        if int(row.get("account_id", 0)) < 0 and row.get("liability_id") is not None
    }
    baseline_date = profile.activation_date or movement_start - timedelta(days=1)
    return [
        SettlementCreditCard(liability=row)
        for row in liabilities
        if row.id in previous_ids
        or row.accounting_account_id in active_ledger_ids
        or get_effective_liability_amount(liability=row, as_of_date=baseline_date) != ZERO
    ]


def _investment_participants(
    *,
    user,
    profile: SettlementProfile,
    movement_start: date,
    close_end: date,
    previous: SettlementSnapshot | None,
    configured_asset_ids: set[int],
) -> list[SettlementInvestmentPosition]:
    """Include portfolio assets and the broker cash accounts that fund them."""

    investment_asset_ids = set(
        Asset.objects.filter(user=user, category=Asset.Category.INVESTMENTS).values_list(
            "id", flat=True
        )
    )
    broker_asset_ids = set(
        LedgerEntry.objects.filter(
            transaction__user=user,
            transaction__status=LedgerTransaction.Status.POSTED,
            transaction__booking_date__lte=close_end,
            transaction__quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            account__asset_id__isnull=False,
        )
        .exclude(account__asset__category=Asset.Category.INVESTMENTS)
        .values_list("account__asset_id", flat=True)
    )
    role_by_asset = {
        **{asset_id: "investment_position" for asset_id in investment_asset_ids},
        **{asset_id: "investment_cash" for asset_id in broker_asset_ids},
    }
    assets = list(
        Asset.objects.filter(
            user=user,
            id__in=set(role_by_asset) - configured_asset_ids,
            accounting_account_id__isnull=False,
            currency=profile.base_currency,
        ).order_by("id")
    )
    if not assets:
        return []
    active_ledger_ids = set(
        LedgerEntry.objects.filter(
            transaction__user=user,
            transaction__status=LedgerTransaction.Status.POSTED,
            transaction__booking_date__gte=movement_start,
            transaction__booking_date__lte=close_end,
            account_id__in=[asset.accounting_account_id for asset in assets],
        ).values_list("account_id", flat=True)
    )
    previous_asset_ids = {
        int(row["asset_id"])
        for row in (previous.account_balances if previous is not None else [])
        if row.get("role") in {"investment_position", "investment_cash"}
        and row.get("asset_id") is not None
    }
    baseline_date = profile.activation_date or movement_start - timedelta(days=1)
    return [
        SettlementInvestmentPosition(asset=asset, role=role_by_asset[asset.id])
        for asset in assets
        if asset.id in previous_asset_ids
        or asset.accounting_account_id in active_ledger_ids
        or get_effective_asset_amount(asset=asset, as_of_date=baseline_date) != ZERO
    ]


def _add_credit_card_opening(
    *,
    cards: list[SettlementCreditCard],
    baseline_date: date,
    allocation_cache,
    account_ownerships: dict[int, Ownership],
    account_members: dict[tuple[int, int], Decimal],
    member_totals: dict[int, Decimal],
    blockers: list[dict],
) -> None:
    for card in cards:
        ownership = account_ownerships.get(card.id)
        if ownership is None:
            _append_unique(blockers, {"code": "account_missing_ownership", "account_id": card.id})
            continue
        vector, allocation_result = _allocation(
            ownership=ownership,
            year=baseline_date.year,
            month=baseline_date.month,
            cache=allocation_cache,
        )
        if vector is None:
            _append_unique(
                blockers,
                {
                    "code": "allocation_blocked",
                    "ownership_id": ownership.id,
                    "quality_reasons": allocation_result["quality_reasons"],
                },
            )
            continue
        balance = -get_effective_liability_amount(
            liability=card.liability, as_of_date=baseline_date
        )
        for member_id, amount in _allocate(balance, vector).items():
            account_members[(card.id, member_id)] += amount
            member_totals[member_id] += amount


def _add_investment_opening(
    *,
    positions: list[SettlementInvestmentPosition],
    baseline_date: date,
    allocation_cache,
    account_ownerships: dict[int, Ownership],
    account_members: dict[tuple[int, int], Decimal],
    member_totals: dict[int, Decimal],
    blockers: list[dict],
) -> None:
    for position in positions:
        ownership = account_ownerships.get(position.id)
        if ownership is None:
            _append_unique(
                blockers, {"code": "account_missing_ownership", "account_id": position.id}
            )
            continue
        vector, allocation_result = _allocation(
            ownership=ownership,
            year=baseline_date.year,
            month=baseline_date.month,
            cache=allocation_cache,
        )
        if vector is None:
            _append_unique(
                blockers,
                {
                    "code": "allocation_blocked",
                    "ownership_id": ownership.id,
                    "quality_reasons": allocation_result["quality_reasons"],
                },
            )
            continue
        balance = get_effective_asset_amount(asset=position.asset, as_of_date=baseline_date)
        for member_id, amount in _allocate(balance, vector).items():
            account_members[(position.id, member_id)] += amount
            member_totals[member_id] += amount


def _convert(
    amount: Decimal,
    currency: str,
    base_currency: str,
    rate_date: date,
    fx_cache,
) -> Decimal:
    return Decimal(
        convert_currency_cached(
            amount,
            currency,
            base_currency,
            rate_date=rate_date,
            fx_cache=fx_cache,
        )
    )


def _load_transactions(
    *, user, ledger_account_ids: list[int], period_start: date, period_end: date
) -> list[LedgerTransaction]:
    if not ledger_account_ids or period_start > period_end:
        return []
    entries = LedgerEntry.objects.select_related("account").order_by("id")
    return list(
        LedgerTransaction.objects.filter(
            user=user,
            status=LedgerTransaction.Status.POSTED,
            booking_date__gte=period_start,
            booking_date__lte=period_end,
            entries__account_id__in=ledger_account_ids,
        )
        .select_related("ownership", "ownership__member")
        .prefetch_related(Prefetch("entries", queryset=entries))
        .distinct()
        .order_by("booking_date", "id")
    )


def _append_unique(rows: list[dict], row: dict) -> None:
    if row not in rows:
        rows.append(row)


def _apply_wallet_normalization(
    *,
    transaction_row: LedgerTransaction,
    settlement_by_ledger: dict[int, SettlementParticipant],
    base_currency: str,
    fx_cache,
    normalization_delta: dict[int, Decimal],
    blockers: list[dict],
) -> None:
    for entry in transaction_row.entries.all():
        settlement_account = settlement_by_ledger.get(entry.account_id)
        if settlement_account is None:
            continue
        signed = (
            Decimal(entry.amount)
            if entry.side == LedgerEntry.Side.DEBIT
            else -Decimal(entry.amount)
        )
        try:
            normalization_delta[settlement_account.id] += _convert(
                signed,
                entry.currency,
                base_currency,
                transaction_row.booking_date,
                fx_cache,
            )
        except DjangoValidationError:
            _append_unique(
                blockers,
                {"code": "missing_fx_rate", "transaction_id": transaction_row.id},
            )


def _compute_movements(
    *,
    transactions: list[LedgerTransaction],
    settlement_by_ledger: dict[int, SettlementParticipant],
    account_ownerships: dict[int, Ownership],
    base_currency: str,
    allocation_cache,
    account_members: dict[tuple[int, int], Decimal],
    member_totals: dict[int, Decimal],
    member_income: dict[int, Decimal],
    member_expense: dict[int, Decimal],
    physical_delta: dict[int, Decimal],
    normalization_delta: dict[int, Decimal],
    normalization_transaction_ids: set[int],
    blockers: list[dict],
) -> list[dict]:
    compensations: list[dict] = []
    currencies = {
        base_currency,
        "USD",
        *(entry.currency.upper() for tx in transactions for entry in tx.entries.all()),
    }
    fx_cache = build_fx_cache(currencies)
    for tx in transactions:
        if tx.id in normalization_transaction_ids:
            _apply_wallet_normalization(
                transaction_row=tx,
                settlement_by_ledger=settlement_by_ledger,
                base_currency=base_currency,
                fx_cache=fx_cache,
                normalization_delta=normalization_delta,
                blockers=blockers,
            )
            continue
        physical_by_member: dict[int, Decimal] = defaultdict(Decimal)
        participant_entries = [
            entry for entry in tx.entries.all() if entry.account_id in settlement_by_ledger
        ]
        participant_total = ZERO
        for entry in participant_entries:
            settlement_account = settlement_by_ledger[entry.account_id]
            signed = (
                Decimal(entry.amount)
                if entry.side == LedgerEntry.Side.DEBIT
                else -Decimal(entry.amount)
            )
            try:
                converted = _convert(
                    signed, entry.currency, base_currency, tx.booking_date, fx_cache
                )
            except DjangoValidationError:
                _append_unique(
                    blockers,
                    {"code": "missing_fx_rate", "transaction_id": tx.id},
                )
                continue
            physical_delta[settlement_account.id] += converted
            participant_total += converted
            ownership = account_ownerships.get(settlement_account.id)
            if ownership is None:
                continue
            vector, allocation_result = _allocation(
                ownership=ownership,
                year=tx.booking_date.year,
                month=tx.booking_date.month,
                cache=allocation_cache,
            )
            if vector is None:
                _append_unique(
                    blockers,
                    {
                        "code": "allocation_blocked",
                        "ownership_id": ownership.id,
                        "quality_reasons": allocation_result["quality_reasons"],
                    },
                )
                continue
            for member_id, amount in _allocate(converted, vector).items():
                account_members[(settlement_account.id, member_id)] += amount
                physical_by_member[member_id] += amount

        classified = [entry for entry in tx.entries.all() if entry.flow_family]
        internal = (
            tx.quick_entry_kind
            in {
                LedgerTransaction.QuickEntryKind.TRANSFER,
                LedgerTransaction.QuickEntryKind.INVESTMENT,
            }
            and _money(participant_total) == ZERO
        )
        if internal:
            continue
        if (
            tx.quick_entry_kind
            in {
                LedgerTransaction.QuickEntryKind.TRANSFER,
                LedgerTransaction.QuickEntryKind.INVESTMENT,
            }
            and _money(participant_total) != ZERO
        ):
            _append_unique(
                blockers,
                {"code": "transaction_outside_perimeter", "transaction_id": tx.id},
            )
            continue

        economic_delta = ZERO
        income_delta = ZERO
        expense_delta = ZERO
        for entry in classified:
            amount = Decimal(entry.amount)
            if entry.flow_family == LedgerEntry.FlowFamily.INCOME:
                signed = amount if entry.side == LedgerEntry.Side.CREDIT else -amount
            else:
                signed = -amount if entry.side == LedgerEntry.Side.DEBIT else amount
            try:
                converted = _convert(
                    signed, entry.currency, base_currency, tx.booking_date, fx_cache
                )
                economic_delta += converted
                if entry.flow_family == LedgerEntry.FlowFamily.INCOME:
                    income_delta += converted
                else:
                    expense_delta -= converted
            except DjangoValidationError:
                _append_unique(
                    blockers,
                    {"code": "missing_fx_rate", "transaction_id": tx.id},
                )
        if _money(economic_delta) == ZERO:
            continue
        if tx.ownership is None:
            _append_unique(
                blockers,
                {"code": "transaction_missing_ownership", "transaction_id": tx.id},
            )
            continue
        vector, allocation_result = _allocation(
            ownership=tx.ownership,
            year=tx.booking_date.year,
            month=tx.booking_date.month,
            cache=allocation_cache,
        )
        if vector is None:
            _append_unique(
                blockers,
                {
                    "code": "allocation_blocked",
                    "ownership_id": tx.ownership_id,
                    "quality_reasons": allocation_result["quality_reasons"],
                },
            )
            continue
        economic_by_member = _allocate(economic_delta, vector)
        income_by_member = _allocate(income_delta, vector)
        expense_by_member = _allocate(expense_delta, vector)
        all_members = sorted(set(economic_by_member) | set(physical_by_member))
        compensation_rows = []
        for member_id in all_members:
            economic = economic_by_member.get(member_id, ZERO)
            member_totals[member_id] += economic
            member_income[member_id] += income_by_member.get(member_id, ZERO)
            member_expense[member_id] += expense_by_member.get(member_id, ZERO)
            difference = _money(economic - physical_by_member.get(member_id, ZERO))
            if difference:
                compensation_rows.append(
                    {"member_id": member_id, "amount": _money_string(difference)}
                )
        if compensation_rows:
            compensations.append(
                {
                    "transaction_id": tx.id,
                    "booking_date": tx.booking_date.isoformat(),
                    "description": tx.description,
                    "ownership_id": tx.ownership_id,
                    "members": compensation_rows,
                }
            )
    return compensations


def _compute_reserves(
    *,
    user,
    target_year: int,
    target_month: int,
    account_by_id: dict[int, SettlementAccount],
    account_ownerships: dict[int, Ownership],
    base_currency: str,
    allocation_cache,
    blockers: list[dict],
    warnings: list[dict],
) -> tuple[list[dict], dict[tuple[int, int], Decimal]]:
    entries = list(
        effective_annual_expense_entries(user=user, fiscal_year=target_year)
        .filter(is_active=True)
        .select_related("ownership", "ownership__member", "settlement_account")
        .prefetch_related("ownership__splits", "ownership__splits__member")
        .order_by("id")
    )
    requirements: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
    rows: list[dict] = []
    fx_cache = build_fx_cache({base_currency, "USD", *(entry.currency for entry in entries)})
    supported = {
        AnnualExpenseEntry.CashflowRole.OPERATING,
        AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
        AnnualExpenseEntry.CashflowRole.SAVINGS,
        AnnualExpenseEntry.CashflowRole.INVESTMENT,
    }
    for entry in entries:
        distribution = planned_expense_monthly_distribution(entry=entry, fiscal_year=target_year)
        amount = distribution.get(target_month)
        if not amount or amount <= ZERO:
            continue
        if (
            entry.time_profile == AnnualExpenseEntry.TimeProfile.ONE_OFF
            or entry.expense_type == AnnualExpenseEntry.ExpenseType.ONE_OFF
            or entry.cashflow_role == AnnualExpenseEntry.CashflowRole.TRANSFER
        ):
            continue
        if entry.cashflow_role not in supported:
            warnings.append(
                {"code": "unsupported_budget_role", "entry_id": entry.id, "name": entry.name}
            )
            continue
        destination = resolve_expense_settlement_destination(
            expense=entry, accounts=list(account_by_id.values())
        )
        if destination is None:
            quality_target = (
                warnings
                if expected_expense_settlement_role(expense=entry)
                == SettlementAccount.Role.ALLOCATION_DESTINATION
                else blockers
            )
            _append_unique(
                quality_target,
                {
                    "code": (
                        "allocation_missing_destination"
                        if quality_target is warnings
                        else "reserve_missing_inputs"
                    ),
                    "entry_id": entry.id,
                    "name": entry.name,
                },
            )
            continue
        expected_role = expected_expense_settlement_role(expense=entry)
        if destination.role != expected_role:
            _append_unique(
                blockers,
                {
                    "code": "invalid_reserve_destination_role",
                    "entry_id": entry.id,
                    "settlement_account_id": destination.id,
                },
            )
            continue
        destination_ownership = account_ownerships.get(destination.id)
        if destination_ownership is None:
            continue
        destination_vector, destination_result = _allocation(
            ownership=destination_ownership,
            year=target_year,
            month=target_month,
            cache=allocation_cache,
        )
        if destination_vector is None:
            _append_unique(
                blockers,
                {
                    "code": "allocation_blocked",
                    "ownership_id": destination_result["ownership_id"],
                    "quality_reasons": destination_result["quality_reasons"],
                },
            )
            continue
        try:
            converted = _convert(
                Decimal(amount),
                entry.currency,
                base_currency,
                date(target_year, target_month, 1),
                fx_cache,
            )
        except DjangoValidationError:
            _append_unique(blockers, {"code": "missing_budget_fx_rate", "entry_id": entry.id})
            continue
        member_rows = []
        for member_id, member_amount in _allocate(converted, destination_vector).items():
            requirements[(destination.id, member_id)] += member_amount
            member_rows.append({"member_id": member_id, "amount": _money_string(member_amount)})
        rows.append(
            {
                "entry_id": entry.id,
                "name": entry.name,
                "kind": (
                    "allocation"
                    if expected_role == SettlementAccount.Role.ALLOCATION_DESTINATION
                    else "reserve"
                ),
                "cashflow_role": entry.cashflow_role,
                "ownership_id": destination_ownership.id,
                "settlement_account_id": destination.id,
                "amount": _money_string(converted),
                "currency": base_currency,
                "members": member_rows,
            }
        )
    return rows, requirements


def _route_transfers(
    *,
    accounts: list[SettlementParticipant],
    current: dict[tuple[int, int], Decimal],
    targets: dict[tuple[int, int], Decimal],
    account_ownerships: dict[int, Ownership],
    base_currency: str,
) -> list[dict]:
    reason_by_role: dict[str, str] = {
        "operating": "next_month_reserve",
        "allocation_destination": "planned_allocation",
        "personal_destination": "member_residual",
        "physical_cash": "physical_cash",
    }
    current_total = {
        account.id: sum(
            (
                amount
                for (account_id, _member_id), amount in current.items()
                if account_id == account.id
            ),
            ZERO,
        )
        for account in accounts
    }
    target_total = {
        account.id: sum(
            (
                amount
                for (account_id, _member_id), amount in targets.items()
                if account_id == account.id
            ),
            ZERO,
        )
        for account in accounts
    }
    surplus = [
        [account.id, _money(current_total[account.id] - target_total[account.id])]
        for account in accounts
        if _money(current_total[account.id] - target_total[account.id]) > ZERO
    ]
    deficit = [
        [account.id, _money(target_total[account.id] - current_total[account.id])]
        for account in accounts
        if _money(target_total[account.id] - current_total[account.id]) > ZERO
    ]
    account_by_id = {account.id: account for account in accounts}
    member_deficits: dict[int, dict[int, Decimal]] = {
        account.id: {
            member_id: _money(target - current.get((account.id, member_id), ZERO))
            for (target_account, member_id), target in sorted(targets.items())
            if target_account == account.id
            and _money(target - current.get((account.id, member_id), ZERO)) > ZERO
        }
        for account in accounts
    }
    rows: list[dict] = []
    source_index = 0
    destination_index = 0
    while source_index < len(surplus) and destination_index < len(deficit):
        source_id = int(surplus[source_index][0])
        source_amount = Decimal(surplus[source_index][1])
        destination_id = int(deficit[destination_index][0])
        destination_amount = Decimal(deficit[destination_index][1])
        amount = min(source_amount, destination_amount)
        destination = account_by_id[destination_id]
        remaining = amount
        for member_id in sorted(member_deficits[destination_id]):
            if remaining <= ZERO:
                break
            member_amount = member_deficits[destination_id][member_id]
            if member_amount <= ZERO:
                continue
            routed = min(remaining, member_amount)
            rows.append(
                {
                    "from_account_id": source_id,
                    "to_account_id": destination_id,
                    "member_id": member_id,
                    "ownership_id": account_ownerships[destination_id].id,
                    "amount": _money_string(routed),
                    "currency": base_currency,
                    "reason": reason_by_role.get(str(destination.role), "settlement"),
                }
            )
            member_deficits[destination_id][member_id] = _money(member_amount - routed)
            remaining = _money(remaining - routed)
        if remaining > ZERO:
            rows.append(
                {
                    "from_account_id": source_id,
                    "to_account_id": destination_id,
                    "member_id": destination.member_id,
                    "ownership_id": account_ownerships[destination_id].id,
                    "amount": _money_string(remaining),
                    "currency": base_currency,
                    "reason": "settlement",
                }
            )
        surplus[source_index][1] = _money(source_amount - amount)
        deficit[destination_index][1] = _money(destination_amount - amount)
        if surplus[source_index][1] == ZERO:
            source_index += 1
        if deficit[destination_index][1] == ZERO:
            destination_index += 1
    return rows


def _serialize_snapshot(snapshot: SettlementSnapshot) -> dict:
    from .services_settlement_execution import serialize_recommendation

    recommendations = [serialize_recommendation(row) for row in snapshot.recommendations.all()]
    return {
        "status": "finalized",
        "calculation_status": snapshot.status,
        "is_frozen": snapshot.is_frozen,
        "computed_at": snapshot.computed_at.isoformat(),
        "period": {
            "start": snapshot.period_start.isoformat(),
            "end": snapshot.period_end.isoformat(),
        },
        "target_period": {"year": snapshot.target_year, "month": snapshot.target_month},
        "base_currency": snapshot.base_currency,
        "opening_source": snapshot.opening_source,
        "allocations": snapshot.allocations,
        "economic_balances": snapshot.economic_balances,
        "accounts": snapshot.account_balances,
        "reserves": snapshot.reserves,
        "compensations": snapshot.compensations,
        "recommendations": recommendations,
        "reconciliation": snapshot.reconciliation,
        "quality": {"blockers": snapshot.blockers, "warnings": snapshot.warnings},
        "source_hash": snapshot.source_hash,
    }


def _economic_balance_rows(
    *,
    opening_totals: dict[int, Decimal],
    member_totals: dict[int, Decimal],
    member_income: dict[int, Decimal],
    member_expense: dict[int, Decimal],
    compensations: list[dict],
    requirements: dict[tuple[int, int], Decimal],
) -> list[dict]:
    compensation_totals: dict[int, Decimal] = defaultdict(Decimal)
    for compensation in compensations:
        for member in compensation["members"]:
            compensation_totals[int(member["member_id"])] += Decimal(str(member["amount"]))
    requirement_totals: dict[int, Decimal] = defaultdict(Decimal)
    for (_account_id, member_id), amount in requirements.items():
        requirement_totals[member_id] += amount
    member_ids = sorted(
        set(opening_totals)
        | set(member_totals)
        | set(member_income)
        | set(member_expense)
        | set(requirement_totals)
    )
    rows = []
    for member_id in member_ids:
        closing = member_totals.get(member_id, ZERO)
        requirement = requirement_totals.get(member_id, ZERO)
        rows.append(
            {
                "member_id": member_id,
                "opening": _money_string(opening_totals.get(member_id, ZERO)),
                "income": _money_string(member_income.get(member_id, ZERO)),
                "expense": _money_string(member_expense.get(member_id, ZERO)),
                "compensation": _money_string(compensation_totals.get(member_id, ZERO)),
                "requirement": _money_string(requirement),
                "closing": _money_string(closing),
                "excess": _money_string(closing - requirement),
            }
        )
    return rows


def _settlement_participants(
    *,
    user,
    profile: SettlementProfile,
    movement_start: date,
    close_end: date,
    previous: SettlementSnapshot | None,
    blockers: list[dict],
) -> tuple[list[SettlementParticipant], dict[int, SettlementAccount], dict[int, Ownership]]:
    configured_accounts = list(profile.accounts.select_related("asset", "member").order_by("id"))
    cards = _credit_card_participants(
        user=user,
        profile=profile,
        movement_start=movement_start,
        close_end=close_end,
        previous=previous,
    )
    investments = _investment_participants(
        user=user,
        profile=profile,
        movement_start=movement_start,
        close_end=close_end,
        previous=previous,
        configured_asset_ids={row.asset_id for row in configured_accounts},
    )
    accounts: list[SettlementParticipant] = [*configured_accounts, *cards, *investments]
    for account in accounts:
        if account.currency != profile.base_currency:
            _append_unique(
                blockers,
                {
                    "code": "unsupported_settlement_currency",
                    "account_id": account.id,
                    "currency": account.currency,
                },
            )
    return (
        accounts,
        {row.id: row for row in configured_accounts},
        _account_ownerships(user=user, accounts=accounts),
    )


def compute_monthly_close_settlement(*, user, fiscal_year: int, month: int) -> dict:
    close = MonthlyClose.objects.filter(user=user, fiscal_year=fiscal_year, month=month).first()
    if close is not None and close.status in {
        MonthlyClose.Status.FINALIZED,
        MonthlyClose.Status.LOCKED,
    }:
        snapshot = getattr(close, "settlement_snapshot", None)
        if snapshot is not None:
            return _serialize_snapshot(snapshot)

    profile = SettlementProfile.objects.filter(user=user).first()
    if profile is None or not profile.is_enabled:
        return {
            "status": "disabled",
            "is_frozen": False,
            "quality": {"blockers": [], "warnings": []},
        }

    close_start = date(fiscal_year, month, 1)
    close_end = _month_end(fiscal_year, month)
    target_year, target_month = _next_period(fiscal_year, month)
    readiness = build_settlement_readiness(
        user=user,
        fiscal_year=target_year,
        month=target_month,
        persist_status=False,
        balance_date=close_end,
    )
    blockers = list(cast(list[dict], readiness["blockers"]))
    warnings = list(cast(list[dict], readiness["warnings"]))
    opening_source, movement_start, account_members, member_totals, previous = _opening_position(
        profile=profile, close_start=close_start
    )
    accounts, account_by_id, account_ownerships = _settlement_participants(
        user=user,
        profile=profile,
        movement_start=movement_start,
        close_end=close_end,
        previous=previous,
        blockers=blockers,
    )
    cards = [row for row in accounts if isinstance(row, SettlementCreditCard)]
    investments = [row for row in accounts if isinstance(row, SettlementInvestmentPosition)]
    allocation_cache: dict[tuple[int, int, int], tuple[dict[int, Decimal] | None, dict]] = {}
    if previous is None and profile.activation_date is not None:
        _add_credit_card_opening(
            cards=cards,
            baseline_date=profile.activation_date,
            allocation_cache=allocation_cache,
            account_ownerships=account_ownerships,
            account_members=account_members,
            member_totals=member_totals,
            blockers=blockers,
        )
        _add_investment_opening(
            positions=investments,
            baseline_date=profile.activation_date,
            allocation_cache=allocation_cache,
            account_ownerships=account_ownerships,
            account_members=account_members,
            member_totals=member_totals,
            blockers=blockers,
        )
    opening_totals = dict(member_totals)
    if previous is None and profile.activation_date and profile.activation_date > close_end:
        _append_unique(blockers, {"code": "settlement_not_active_for_period"})
    settlement_by_ledger = {
        int(_participant_ledger_account_id(account)): account
        for account in accounts
        if _participant_ledger_account_id(account) is not None
    }
    transactions = _load_transactions(
        user=user,
        ledger_account_ids=list(settlement_by_ledger),
        period_start=movement_start,
        period_end=close_end,
    )
    physical_delta: dict[int, Decimal] = defaultdict(Decimal)
    normalization_delta: dict[int, Decimal] = defaultdict(Decimal)
    member_income: dict[int, Decimal] = defaultdict(Decimal)
    member_expense: dict[int, Decimal] = defaultdict(Decimal)
    compensations = _compute_movements(
        transactions=transactions,
        settlement_by_ledger=settlement_by_ledger,
        account_ownerships=account_ownerships,
        base_currency=profile.base_currency,
        allocation_cache=allocation_cache,
        account_members=account_members,
        member_totals=member_totals,
        member_income=member_income,
        member_expense=member_expense,
        physical_delta=physical_delta,
        normalization_delta=normalization_delta,
        normalization_transaction_ids=set(
            SettlementWalletNormalization.objects.filter(profile=profile).values_list(
                "transaction_id", flat=True
            )
        ),
        blockers=blockers,
    )
    cumulative_normalization_delta = _wallet_normalization_deltas(
        profile=profile,
        after_date=profile.activation_date or close_start - timedelta(days=1),
        through_date=close_end,
    )

    reserves, requirements = _compute_reserves(
        user=user,
        target_year=target_year,
        target_month=target_month,
        account_by_id=account_by_id,
        account_ownerships=account_ownerships,
        base_currency=profile.base_currency,
        allocation_cache=allocation_cache,
        blockers=blockers,
        warnings=warnings,
    )

    current = dict(account_members)
    account_rows = []
    for account in accounts:
        opening_total = (
            sum(
                (
                    amount
                    for (account_id, _member_id), amount in account_members.items()
                    if account_id == account.id
                ),
                ZERO,
            )
            - physical_delta[account.id]
        )
        expected = opening_total + physical_delta[account.id]
        if account.role == SettlementAccount.Role.PHYSICAL_CASH:
            modeled = get_effective_asset_amount(asset=account.asset, as_of_date=close_end)
            activation_gap = Decimal(account.modeled_balance_at_activation or ZERO) - Decimal(
                account.accepted_physical_balance or ZERO
            )
            remaining_gap = activation_gap + cumulative_normalization_delta.get(account.id, ZERO)
            observed = modeled - remaining_gap
        elif isinstance(account, SettlementCreditCard):
            observed = -get_effective_liability_amount(
                liability=account.liability, as_of_date=close_end
            )
        elif isinstance(account, SettlementInvestmentPosition):
            observed = get_effective_asset_amount(asset=account.asset, as_of_date=close_end)
        else:
            observed = get_effective_asset_amount(asset=account.asset, as_of_date=close_end)
        difference = _money(Decimal(observed) - expected)
        if difference:
            _append_unique(
                blockers,
                {
                    "code": "unreconciled_account_balance",
                    "account_id": account.id,
                    "expected": _money_string(expected),
                    "observed": _money_string(Decimal(observed)),
                    "difference": _money_string(difference),
                },
            )
        closing_members = [
            {"member_id": member_id, "amount": _money_string(amount)}
            for (account_id, member_id), amount in sorted(current.items())
            if account_id == account.id
        ]
        account_rows.append(
            {
                "account_id": account.id,
                "asset_id": account.asset_id,
                "liability_id": account.liability_id
                if isinstance(account, SettlementCreditCard)
                else None,
                "name": account.name
                if isinstance(account, (SettlementCreditCard, SettlementInvestmentPosition))
                else account.asset.name,
                "role": account.role,
                "ownership_id": account_ownerships.get(account.id).id
                if account.id in account_ownerships
                else None,
                "opening": _money_string(opening_total),
                "physical_delta": _money_string(physical_delta[account.id]),
                "normalization_delta": _money_string(
                    cumulative_normalization_delta.get(account.id, ZERO)
                ),
                "observed_close": _money_string(Decimal(observed)),
                "closing_by_member": closing_members,
            }
        )

    targets: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
    for account in accounts:
        if account.role in {
            SettlementAccount.Role.PHYSICAL_CASH,
            SettlementAccount.Role.ALLOCATION_DESTINATION,
            "credit_card",
            "investment_position",
            "investment_cash",
        }:
            for (account_id, member_id), amount in current.items():
                if account_id == account.id:
                    targets[(account.id, member_id)] += amount
    for key, amount in requirements.items():
        targets[key] += amount

    primary_personal = {
        account.member_id: account
        for account in accounts
        if isinstance(account, SettlementAccount)
        and account.role == SettlementAccount.Role.PERSONAL_DESTINATION
        and account.is_primary
        and account.currency == profile.base_currency
    }
    for member_id, economic_total in member_totals.items():
        allocated_target = sum(
            (
                amount
                for (account_id, target_member), amount in targets.items()
                if target_member == member_id
            ),
            ZERO,
        )
        destination = primary_personal.get(member_id)
        if destination is not None:
            targets[(destination.id, member_id)] += economic_total - allocated_target

    recommendations = (
        []
        if blockers
        else _route_transfers(
            accounts=accounts,
            current=current,
            targets=targets,
            account_ownerships=account_ownerships,
            base_currency=profile.base_currency,
        )
    )
    for row in account_rows:
        account_id = int(row["account_id"])
        row["target_close"] = _money_string(
            sum(
                (
                    amount
                    for (target_account, _member), amount in targets.items()
                    if target_account == account_id
                ),
                ZERO,
            )
        )
        row["target_by_member"] = [
            {"member_id": member_id, "amount": _money_string(amount)}
            for (target_account, member_id), amount in sorted(targets.items())
            if target_account == account_id
        ]

    physical_total = sum((Decimal(str(row["observed_close"])) for row in account_rows), ZERO)
    economic_total = sum(member_totals.values(), ZERO)
    target_total = sum(targets.values(), ZERO)
    reconciliation = {
        "physical_total": _money_string(physical_total),
        "economic_total": _money_string(economic_total),
        "target_total": _money_string(target_total),
        "physical_vs_economic": _money_string(physical_total - economic_total),
        "economic_vs_target": _money_string(economic_total - target_total),
    }
    if _money(physical_total - economic_total):
        _append_unique(blockers, {"code": "household_total_mismatch", **reconciliation})

    economic_rows = _economic_balance_rows(
        opening_totals=opening_totals,
        member_totals=member_totals,
        member_income=member_income,
        member_expense=member_expense,
        compensations=compensations,
        requirements=requirements,
    )
    result = {
        "status": "not_ready" if blockers else "ready",
        "calculation_status": "not_ready" if blockers else "ready",
        "is_frozen": False,
        "computed_at": timezone.now().isoformat(),
        "period": {"start": movement_start.isoformat(), "end": close_end.isoformat()},
        "target_period": {"year": target_year, "month": target_month},
        "base_currency": profile.base_currency,
        "opening_source": opening_source,
        "allocations": _serialized_allocations(allocation_cache),
        "economic_balances": economic_rows,
        "accounts": account_rows,
        "reserves": reserves,
        "compensations": compensations,
        "recommendations": recommendations if not blockers else [],
        "reconciliation": reconciliation,
        "quality": {"blockers": blockers, "warnings": warnings},
    }
    result["source_hash"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return result


@transaction.atomic
def freeze_monthly_close_settlement(
    *, monthly_close: MonthlyClose, user
) -> SettlementSnapshot | None:
    profile = SettlementProfile.objects.filter(user=user, is_enabled=True).first()
    if profile is None:
        return None
    preview = compute_monthly_close_settlement(
        user=user,
        fiscal_year=monthly_close.fiscal_year,
        month=monthly_close.month,
    )
    frozen_allocations: list[OwnershipAllocationSnapshot] = []
    if preview["status"] == "ready":
        for row in preview["allocations"]:
            ownership = Ownership.objects.get(id=row["ownership_id"], user=user)
            if ownership.allocation_basis != Ownership.AllocationBasis.RECURRING_INCOME_12M:
                continue
            resolve_ownership_allocation(
                ownership=ownership,
                fiscal_year=int(row["fiscal_year"]),
                month=int(row["month"]),
                persist=True,
                freeze=True,
            )
            frozen_allocations.append(
                OwnershipAllocationSnapshot.objects.get(
                    ownership=ownership,
                    fiscal_year=int(row["fiscal_year"]),
                    month=int(row["month"]),
                )
            )
        preview = compute_monthly_close_settlement(
            user=user,
            fiscal_year=monthly_close.fiscal_year,
            month=monthly_close.month,
        )
    snapshot = SettlementSnapshot.objects.create(
        monthly_close=monthly_close,
        profile=profile,
        status=(
            SettlementSnapshot.Status.READY
            if preview["calculation_status"] == "ready"
            else SettlementSnapshot.Status.NOT_READY
        ),
        base_currency=preview["base_currency"],
        period_start=date.fromisoformat(preview["period"]["start"]),
        period_end=date.fromisoformat(preview["period"]["end"]),
        target_year=int(preview["target_period"]["year"]),
        target_month=int(preview["target_period"]["month"]),
        opening_source=preview["opening_source"],
        source_hash=preview["source_hash"],
        allocations=preview["allocations"],
        economic_balances=preview["economic_balances"],
        account_balances=preview["accounts"],
        reserves=preview["reserves"],
        compensations=preview["compensations"],
        blockers=preview["quality"]["blockers"],
        warnings=preview["quality"]["warnings"],
        reconciliation=preview["reconciliation"],
    )
    snapshot.allocation_snapshots.set(frozen_allocations)
    SettlementTransferRecommendation.objects.bulk_create(
        [
            SettlementTransferRecommendation(
                snapshot=snapshot,
                from_account_id=row["from_account_id"],
                to_account_id=row["to_account_id"],
                member_id=row["member_id"],
                ownership_id=row["ownership_id"],
                amount=Decimal(row["amount"]),
                currency=row["currency"],
                reason=row["reason"],
                sort_order=index,
            )
            for index, row in enumerate(preview["recommendations"])
        ]
    )
    return snapshot


@transaction.atomic
def clear_monthly_close_settlement(*, monthly_close: MonthlyClose) -> None:
    snapshot = getattr(monthly_close, "settlement_snapshot", None)
    if snapshot is None:
        return
    allocations = list(snapshot.allocation_snapshots.all())
    snapshot.delete()
    for allocation in allocations:
        if not allocation.settlement_snapshots.exists():
            allocation.is_frozen = False
            allocation.frozen_at = None
            allocation.save(update_fields=["is_frozen", "frozen_at", "updated_at"])
