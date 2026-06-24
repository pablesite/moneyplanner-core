from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Exists, OuterRef, Prefetch, Q, QuerySet
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .services_ledger import NET_WORTH_OPENING_NOTE_PREFIX, ZERO, normalize_currency_code


def validate_transaction_entries(
    *,
    entries_data: list[dict],
    user_id: int,
    allow_unbalanced_multicurrency: bool = False,
) -> None:
    if len(entries_data) < 2:
        raise ValidationError({"entries": "Una transaccion debe incluir al menos dos apuntes."})

    totals_by_currency: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"debit": ZERO, "credit": ZERO}
    )
    for index, entry_data in enumerate(entries_data):
        account = entry_data["account"]
        if account.user_id != user_id:
            raise ValidationError(
                {
                    "entries": {
                        index: {"account_id": "La cuenta no pertenece al usuario autenticado."}
                    }
                }
            )

        currency = normalize_currency_code(entry_data.get("currency") or account.currency)
        if len(currency) != 3:
            raise ValidationError({"entries": {index: {"currency": "Moneda invalida."}}})
        if currency != account.currency:
            raise ValidationError(
                {
                    "entries": {
                        index: {
                            "currency": "La moneda del apunte debe coincidir con la moneda de la cuenta."
                        }
                    }
                }
            )

        amount = entry_data["amount"]
        if amount <= ZERO:
            raise ValidationError(
                {"entries": {index: {"amount": "El importe del apunte debe ser mayor que cero."}}}
            )
        totals_by_currency[currency][entry_data["side"]] += amount

    if allow_unbalanced_multicurrency:
        return

    for currency, totals in totals_by_currency.items():
        if totals["debit"] != totals["credit"]:
            raise ValidationError(
                {
                    "entries": (
                        "La transaccion no esta balanceada para la moneda "
                        f"{currency}: debe={totals['debit']} haber={totals['credit']}."
                    )
                }
            )


def validate_booking_and_value_dates(*, booking_date, value_date) -> None:
    if value_date < booking_date:
        raise ValidationError(
            {"value_date": "La fecha valor no puede ser anterior a la fecha de contabilizacion."}
        )


def validate_balance_summary_filters(*, fiscal_year: int | None, month: int | None) -> None:
    if month is not None and fiscal_year is None:
        raise ValidationError(
            {"year": "Query param 'year' es obligatorio cuando se informa 'month'."}
        )
    if month is not None and (month < 1 or month > 12):
        raise ValidationError({"month": "Query param 'month' invalido."})


def classify_transaction_activity_kind(transaction: LedgerTransaction) -> str:
    entries = list(transaction.entries.all())
    notes = str(transaction.notes or "").strip()
    is_opening_balance = notes.startswith(NET_WORTH_OPENING_NOTE_PREFIX)
    if transaction.origin == LedgerTransaction.Origin.SYSTEM:
        if is_opening_balance:
            return "opening_balance"
        return "revaluation"
    # If quick_entry_kind is explicitly set, trust it over entry-based heuristics.
    qek = transaction.quick_entry_kind
    if qek == LedgerTransaction.QuickEntryKind.REVALUATION:
        return "revaluation"
    if qek == LedgerTransaction.QuickEntryKind.TRANSFER:
        return "transfer"
    if qek == LedgerTransaction.QuickEntryKind.ADJUSTMENT:
        return "adjustment"
    if qek == LedgerTransaction.QuickEntryKind.INVESTMENT:
        return "investment"
    if qek == LedgerTransaction.QuickEntryKind.INCOME:
        return "income"
    if qek == LedgerTransaction.QuickEntryKind.EXPENSE:
        return "expense"
    if qek == LedgerTransaction.QuickEntryKind.DEBT_PAYMENT:
        return "debt_payment"

    has_income = any(entry.flow_family == LedgerEntry.FlowFamily.INCOME for entry in entries)
    if has_income:
        return "income"

    has_liability = any(entry.liability_id is not None for entry in entries)
    if has_liability:
        return "debt_payment"

    has_expense = any(
        entry.flow_family == LedgerEntry.FlowFamily.EXPENSE and entry.liability_id is None
        for entry in entries
    )
    if has_expense:
        return "expense"

    has_investment = any(
        entry.asset_id is not None
        and entry.account_id is not None
        and entry.account.account_type == LedgerAccount.AccountType.ASSET
        and entry.account.asset_id is not None
        for entry in entries
    )
    if has_investment:
        return "investment"

    asset_entries_count = sum(
        1 for entry in entries if entry.account.account_type == LedgerAccount.AccountType.ASSET
    )
    if asset_entries_count >= 2:
        return "transfer"

    return "other"


def _get_legacy_transfer_transaction_ids(queryset: QuerySet) -> list[int]:
    legacy_rows = (
        queryset.prefetch_related(None)
        .filter(quick_entry_kind="")
        .prefetch_related(
            Prefetch("entries", queryset=LedgerEntry.objects.select_related("account"))
        )
    )
    legacy_transfer_ids: list[int] = []
    for transaction in legacy_rows:
        entries = list(transaction.entries.all())
        asset_entry_count = sum(
            1 for entry in entries if entry.account.account_type == LedgerAccount.AccountType.ASSET
        )
        has_income_like_entry = any(
            entry.flow_family == LedgerEntry.FlowFamily.INCOME for entry in entries
        )
        has_expense_like_entry = any(
            entry.flow_family == LedgerEntry.FlowFamily.EXPENSE for entry in entries
        )
        has_liability_entry = any(entry.liability_id is not None for entry in entries)
        has_investment_entry = any(entry.asset_id is not None for entry in entries)
        if (
            asset_entry_count >= 2
            and not has_income_like_entry
            and not has_expense_like_entry
            and not has_liability_entry
            and not has_investment_entry
        ):
            legacy_transfer_ids.append(transaction.id)
    return legacy_transfer_ids


def transaction_needs_review(transaction: LedgerTransaction) -> bool:
    """Return whether an operational movement still lacks functional classification."""
    kind = classify_transaction_activity_kind(transaction)
    if kind not in {"income", "expense", "investment", "debt_payment"}:
        return False
    if (
        kind == "investment"
        and transaction.investment_direction == LedgerTransaction.InvestmentDirection.REINVESTMENT
    ):
        return False
    return not any(
        entry.flow_family and entry.category_key and entry.subcategory_key
        for entry in transaction.entries.all()
    )


def filter_transactions_by_review_state(queryset: QuerySet, review_state: str) -> QuerySet:
    if review_state not in {"needs_review", "reviewed"}:
        raise ValidationError({"review_state": "Query param 'review_state' invalido."})

    entry_subquery = LedgerEntry.objects.filter(transaction_id=OuterRef("pk"))
    has_complete_classification = Exists(
        entry_subquery.exclude(flow_family="").exclude(category_key="").exclude(subcategory_key="")
    )
    legacy_review_candidate = (
        Q(quick_entry_kind="")
        & ~Q(origin=LedgerTransaction.Origin.SYSTEM)
        & (
            Exists(
                entry_subquery.filter(
                    flow_family__in=[LedgerEntry.FlowFamily.INCOME, LedgerEntry.FlowFamily.EXPENSE]
                )
            )
            | Exists(entry_subquery.filter(liability_id__isnull=False))
            | Exists(
                entry_subquery.filter(
                    asset_id__isnull=False,
                    account__account_type=LedgerAccount.AccountType.ASSET,
                    account__asset_id__isnull=False,
                )
            )
        )
    )
    explicit_review_candidate = Q(
        quick_entry_kind__in=[
            LedgerTransaction.QuickEntryKind.INCOME,
            LedgerTransaction.QuickEntryKind.EXPENSE,
            LedgerTransaction.QuickEntryKind.DEBT_PAYMENT,
        ]
    ) | (
        Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT)
        & ~Q(investment_direction=LedgerTransaction.InvestmentDirection.REINVESTMENT)
    )
    needs_review = (
        explicit_review_candidate | legacy_review_candidate
    ) & ~has_complete_classification
    return queryset.filter(needs_review if review_state == "needs_review" else ~needs_review)


def _filter_transactions_by_ownership(queryset: QuerySet, ownership_id: str) -> QuerySet:
    if not ownership_id:
        return queryset
    if ownership_id.lower() in {"null", "none"}:
        return queryset.filter(ownership_id__isnull=True)
    try:
        ownership_id_int = int(ownership_id)
    except ValueError as exc:
        raise ValidationError({"ownership_id": "Query param 'ownership_id' invalido."}) from exc
    if ownership_id_int < 1:
        raise ValidationError({"ownership_id": "Query param 'ownership_id' invalido."})
    return queryset.filter(ownership_id=ownership_id_int)


def apply_transaction_list_filters(queryset: QuerySet, params) -> QuerySet:
    date_from = (params.get("date_from") or "").strip()
    date_to = (params.get("date_to") or "").strip()
    account_id = (params.get("account_id") or "").strip()
    query = (params.get("query") or "").strip()
    kind = (params.get("kind") or "").strip()
    category_key = (params.get("category_key") or "").strip()
    subcategory_key = (params.get("subcategory_key") or "").strip()
    ownership_id = (params.get("ownership_id") or "").strip()

    if date_from:
        parsed = parse_date(date_from)
        if parsed is None:
            raise ValidationError({"date_from": "Query param 'date_from' invalido (YYYY-MM-DD)."})
        queryset = queryset.filter(booking_date__gte=parsed)
    if date_to:
        parsed = parse_date(date_to)
        if parsed is None:
            raise ValidationError({"date_to": "Query param 'date_to' invalido (YYYY-MM-DD)."})
        queryset = queryset.filter(booking_date__lte=parsed)

    if account_id:
        try:
            account_id_int = int(account_id)
        except ValueError as exc:
            raise ValidationError({"account_id": "Query param 'account_id' invalido."}) from exc
        queryset = queryset.filter(entries__account_id=account_id_int).distinct()

    queryset = _filter_transactions_by_ownership(queryset, ownership_id)

    if query:
        matching_account_ids = LedgerAccount.objects.filter(name__icontains=query).values("id")
        matching_account_entry = LedgerEntry.objects.filter(
            transaction_id=OuterRef("pk"),
            account_id__in=matching_account_ids,
        )
        queryset = queryset.filter(
            Q(description__icontains=query)
            | Q(notes__icontains=query)
            | Exists(matching_account_entry)
        )

    if category_key:
        queryset = queryset.filter(
            Exists(
                LedgerEntry.objects.filter(
                    transaction_id=OuterRef("pk"),
                    category_key=category_key,
                )
            )
        )
    if subcategory_key:
        queryset = queryset.filter(
            Exists(
                LedgerEntry.objects.filter(
                    transaction_id=OuterRef("pk"),
                    subcategory_key=subcategory_key,
                )
            )
        )

    if not kind:
        return queryset

    entry_subquery = LedgerEntry.objects.filter(transaction_id=OuterRef("pk"))
    if kind == "income":
        queryset = queryset.filter(
            Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.INCOME)
            | (
                Q(quick_entry_kind="")
                & Exists(entry_subquery.filter(flow_family=LedgerEntry.FlowFamily.INCOME))
            )
        )
    elif kind == "expense":
        queryset = queryset.filter(
            Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.EXPENSE)
            | (
                Q(quick_entry_kind="")
                & Exists(
                    entry_subquery.filter(
                        flow_family=LedgerEntry.FlowFamily.EXPENSE,
                        liability_id__isnull=True,
                    )
                )
            )
        )
    elif kind == "debt_payment":
        queryset = queryset.filter(
            Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.DEBT_PAYMENT)
            | (
                Q(quick_entry_kind="")
                & ~Q(origin=LedgerTransaction.Origin.SYSTEM)
                & ~Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION)
                & Exists(entry_subquery.filter(liability_id__isnull=False))
            ),
        )
    elif kind == "investment":
        queryset = queryset.filter(
            Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT)
            | (
                Q(quick_entry_kind="")
                & ~Q(origin=LedgerTransaction.Origin.SYSTEM)
                & ~Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION)
                & Exists(
                    entry_subquery.filter(
                        asset_id__isnull=False,
                        account__account_type=LedgerAccount.AccountType.ASSET,
                        account__asset_id__isnull=False,
                    )
                )
            ),
        )
    elif kind == "revaluation":
        queryset = queryset.filter(
            Q(origin=LedgerTransaction.Origin.SYSTEM)
            & ~Q(notes__startswith=NET_WORTH_OPENING_NOTE_PREFIX)
            | Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION)
        )
    elif kind == "opening_balance":
        queryset = queryset.filter(
            Q(origin=LedgerTransaction.Origin.SYSTEM)
            & Q(notes__startswith=NET_WORTH_OPENING_NOTE_PREFIX)
        )
    elif kind == "transfer":
        legacy_transfer_ids = _get_legacy_transfer_transaction_ids(queryset)
        queryset = queryset.filter(
            Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER)
            | Q(id__in=legacy_transfer_ids)
        )
    elif kind == "adjustment":
        queryset = queryset.filter(Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.ADJUSTMENT))
    else:
        raise ValidationError({"kind": "Query param 'kind' invalido."})
    return queryset
