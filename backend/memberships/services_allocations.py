from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q

from accounting.models import LedgerEntry, LedgerTransaction
from accounts.services import get_base_currency_for_user
from core.services import build_fx_cache, convert_currency_cached

from .models import (
    Ownership,
    OwnershipAllocationSnapshot,
    OwnershipAllocationSnapshotShare,
)

ZERO = Decimal("0")
PERCENT_STEP = Decimal("0.01")
DEFAULT_INCOME_CATEGORY = "salary"


def _shift_month(month_start: date, months: int) -> date:
    month_index = month_start.year * 12 + month_start.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def allocation_window(*, fiscal_year: int, month: int) -> tuple[date, date]:
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    period_start = date(fiscal_year, month, 1)
    return _shift_month(period_start, -12), period_start - timedelta(days=1)


def _serialize_snapshot(snapshot: OwnershipAllocationSnapshot) -> dict[str, object]:
    return {
        "ownership_id": snapshot.ownership_id,
        "allocation_basis": snapshot.ownership.allocation_basis,
        "fiscal_year": snapshot.fiscal_year,
        "month": snapshot.month,
        "window_start": snapshot.window_start.isoformat(),
        "window_end": snapshot.window_end.isoformat(),
        "base_currency": snapshot.base_currency,
        "status": snapshot.status,
        "quality_reasons": snapshot.quality_reasons,
        "observed_months": snapshot.observed_months,
        "eligible_transaction_count": snapshot.eligible_transaction_count,
        "excluded_transaction_count": snapshot.excluded_transaction_count,
        "total_qualifying_income": str(snapshot.total_qualifying_income),
        "source_hash": snapshot.source_hash,
        "is_frozen": snapshot.is_frozen,
        "shares": [
            {
                "member_id": share.member_id,
                "member_name": share.member.name,
                "qualifying_income": str(share.qualifying_income),
                "percent": str(share.percent) if share.percent is not None else None,
            }
            for share in snapshot.shares.select_related("member").all()
        ],
    }


def _static_allocation_result(
    *, ownership: Ownership, fiscal_year: int, month: int
) -> dict[str, object]:
    window_start, window_end = allocation_window(fiscal_year=fiscal_year, month=month)
    if ownership.kind == Ownership.Kind.INDIVIDUAL:
        shares = [
            {
                "member_id": ownership.member_id,
                "member_name": ownership.member.name,
                "qualifying_income": None,
                "percent": "100.00",
            }
        ]
    else:
        shares = [
            {
                "member_id": split.member_id,
                "member_name": split.member.name,
                "qualifying_income": None,
                "percent": str(split.percent),
            }
            for split in ownership.splits.select_related("member").order_by("member_id")
        ]
    return {
        "ownership_id": ownership.id,
        "allocation_basis": ownership.allocation_basis,
        "fiscal_year": fiscal_year,
        "month": month,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "base_currency": get_base_currency_for_user(user=ownership.user),
        "status": OwnershipAllocationSnapshot.Status.READY,
        "quality_reasons": [],
        "observed_months": None,
        "eligible_transaction_count": None,
        "excluded_transaction_count": None,
        "total_qualifying_income": None,
        "source_hash": None,
        "is_frozen": False,
        "shares": shares,
    }


def _income_rule_filter(ownership: Ownership) -> tuple[Q, list[tuple[str, str]]]:
    rules = list(
        ownership.income_rules.order_by("category_key", "subcategory_key").values_list(
            "category_key", "subcategory_key"
        )
    )
    if not rules:
        rules = [(DEFAULT_INCOME_CATEGORY, "")]

    query = Q()
    for category_key, subcategory_key in rules:
        rule_query = Q(category_key=category_key)
        if subcategory_key:
            rule_query &= Q(subcategory_key=subcategory_key)
        query |= rule_query
    return query, rules


def _calculate_dynamic_allocation(
    *, ownership: Ownership, fiscal_year: int, month: int
) -> dict[str, object]:
    window_start, window_end = allocation_window(fiscal_year=fiscal_year, month=month)
    member_rows = list(
        ownership.splits.select_related("member")
        .order_by("member_id")
        .values_list("member_id", "member__name")
    )
    member_ids = [member_id for member_id, _ in member_rows]
    rule_filter, rules = _income_rule_filter(ownership)

    candidates = LedgerEntry.objects.filter(
        transaction__user_id=ownership.user_id,
        transaction__status=LedgerTransaction.Status.POSTED,
        transaction__booking_date__gte=window_start,
        transaction__booking_date__lte=window_end,
        transaction__ownership__kind=Ownership.Kind.INDIVIDUAL,
        transaction__ownership__member_id__in=member_ids,
        flow_family=LedgerEntry.FlowFamily.INCOME,
    )
    candidate_transaction_ids = set(candidates.values_list("transaction_id", flat=True))
    entries = list(
        candidates.filter(rule_filter)
        .select_related("transaction", "transaction__ownership")
        .order_by("transaction__booking_date", "transaction_id", "id")
        .values(
            "id",
            "updated_at",
            "transaction_id",
            "transaction__updated_at",
            "transaction__booking_date",
            "transaction__ownership__member_id",
            "side",
            "amount",
            "currency",
            "category_key",
            "subcategory_key",
        )
    )

    base_currency = get_base_currency_for_user(user=ownership.user)
    currencies = {base_currency, "USD", *(str(row["currency"]).upper() for row in entries)}
    fx_cache = build_fx_cache(currencies)
    totals = {member_id: ZERO for member_id in member_ids}
    observed_periods: set[tuple[int, int]] = set()
    eligible_transaction_ids: set[int] = set()
    missing_fx_transaction_ids: set[int] = set()
    source_rows: list[dict[str, object]] = []

    for row in entries:
        amount = Decimal(row["amount"])
        if row["side"] == LedgerEntry.Side.DEBIT:
            amount = -amount
        try:
            converted = convert_currency_cached(
                amount,
                str(row["currency"]),
                base_currency,
                rate_date=row["transaction__booking_date"],
                fx_cache=fx_cache,
            )
        except DjangoValidationError:
            missing_fx_transaction_ids.add(row["transaction_id"])
            source_rows.append(
                {
                    "entry_id": row["id"],
                    "entry_updated_at": row["updated_at"].isoformat(),
                    "transaction_id": row["transaction_id"],
                    "transaction_updated_at": row["transaction__updated_at"].isoformat(),
                    "member_id": row["transaction__ownership__member_id"],
                    "booking_date": row["transaction__booking_date"].isoformat(),
                    "amount": str(amount),
                    "currency": row["currency"],
                    "fx_missing": True,
                }
            )
            continue

        member_id = row["transaction__ownership__member_id"]
        totals[member_id] += converted
        booking_date = row["transaction__booking_date"]
        observed_periods.add((booking_date.year, booking_date.month))
        eligible_transaction_ids.add(row["transaction_id"])
        source_rows.append(
            {
                "entry_id": row["id"],
                "entry_updated_at": row["updated_at"].isoformat(),
                "transaction_id": row["transaction_id"],
                "transaction_updated_at": row["transaction__updated_at"].isoformat(),
                "member_id": member_id,
                "booking_date": booking_date.isoformat(),
                "converted": str(converted),
            }
        )

    reasons: list[str] = []
    observed_months = len(observed_periods)
    if observed_months < 3:
        status = OwnershipAllocationSnapshot.Status.BLOCKED
        reasons.append("insufficient_history")
    elif observed_months < 12:
        status = OwnershipAllocationSnapshot.Status.PROVISIONAL
        reasons.append("partial_history")
    else:
        status = OwnershipAllocationSnapshot.Status.READY
    if missing_fx_transaction_ids:
        status = OwnershipAllocationSnapshot.Status.BLOCKED
        reasons.append("missing_fx_rates")
    if any(amount < ZERO for amount in totals.values()):
        status = OwnershipAllocationSnapshot.Status.BLOCKED
        reasons.append("negative_member_income")

    total_income = sum(totals.values(), ZERO)
    if total_income <= ZERO:
        status = OwnershipAllocationSnapshot.Status.BLOCKED
        reasons.append("no_positive_income")

    percentages: dict[int, Decimal | None] = dict.fromkeys(member_ids)
    if status != OwnershipAllocationSnapshot.Status.BLOCKED:
        allocated = ZERO
        for index, member_id in enumerate(member_ids):
            if index == len(member_ids) - 1:
                percentages[member_id] = Decimal("100.00") - allocated
            else:
                percent = (totals[member_id] * Decimal("100") / total_income).quantize(
                    PERCENT_STEP, rounding=ROUND_HALF_UP
                )
                percentages[member_id] = percent
                allocated += percent

    source_hash = hashlib.sha256(
        json.dumps(
            {
                "rules": rules,
                "base_currency": base_currency,
                "rows": source_rows,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return {
        "window_start": window_start,
        "window_end": window_end,
        "base_currency": base_currency,
        "source_hash": source_hash,
        "status": status,
        "quality_reasons": reasons,
        "observed_months": observed_months,
        "eligible_transaction_count": len(eligible_transaction_ids),
        "excluded_transaction_count": len(candidate_transaction_ids - eligible_transaction_ids),
        "total_qualifying_income": total_income,
        "shares": [
            {
                "member_id": member_id,
                "member_name": member_name,
                "qualifying_income": totals[member_id],
                "percent": percentages[member_id],
            }
            for member_id, member_name in member_rows
        ],
    }


@transaction.atomic
def resolve_ownership_allocation(
    *,
    ownership: Ownership,
    fiscal_year: int,
    month: int,
    persist: bool = True,
    freeze: bool = False,
) -> dict[str, object]:
    if ownership.allocation_basis != Ownership.AllocationBasis.RECURRING_INCOME_12M:
        return _static_allocation_result(ownership=ownership, fiscal_year=fiscal_year, month=month)

    frozen = (
        ownership.allocation_snapshots.filter(
            fiscal_year=fiscal_year,
            month=month,
            is_frozen=True,
        )
        .prefetch_related("shares", "shares__member")
        .first()
    )
    if frozen is not None:
        return _serialize_snapshot(frozen)

    calculated = _calculate_dynamic_allocation(
        ownership=ownership, fiscal_year=fiscal_year, month=month
    )
    calculated_shares = calculated["shares"]
    if not isinstance(calculated_shares, list):
        raise TypeError("calculated shares must be a list")
    if not persist:
        return {
            "ownership_id": ownership.id,
            "allocation_basis": ownership.allocation_basis,
            "fiscal_year": fiscal_year,
            "month": month,
            **{
                key: (
                    value.isoformat()
                    if isinstance(value, date)
                    else str(value)
                    if isinstance(value, Decimal)
                    else value
                )
                for key, value in calculated.items()
                if key != "shares"
            },
            "is_frozen": False,
            "shares": [
                {
                    **share,
                    "qualifying_income": str(share["qualifying_income"]),
                    "percent": str(share["percent"]) if share["percent"] is not None else None,
                }
                for share in calculated_shares
            ],
        }

    snapshot, _ = OwnershipAllocationSnapshot.objects.update_or_create(
        ownership=ownership,
        fiscal_year=fiscal_year,
        month=month,
        defaults={key: value for key, value in calculated.items() if key != "shares"},
    )
    snapshot.shares.all().delete()
    OwnershipAllocationSnapshotShare.objects.bulk_create(
        [
            OwnershipAllocationSnapshotShare(
                snapshot=snapshot,
                member_id=share["member_id"],
                qualifying_income=share["qualifying_income"],
                percent=share["percent"],
            )
            for share in calculated_shares
        ]
    )
    if freeze:
        snapshot.freeze()
    snapshot.refresh_from_db()
    return _serialize_snapshot(snapshot)
