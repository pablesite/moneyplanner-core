from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .services_ledger import ZERO, normalize_currency_code


def validate_transaction_entries(*, entries_data: list[dict], user_id: int) -> None:
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
    if transaction.origin == LedgerTransaction.Origin.SYSTEM:
        return "revaluation"
    if transaction.quick_entry_kind == LedgerTransaction.QuickEntryKind.REVALUATION:
        return "revaluation"

    has_income = any(
        entry.flow_family == LedgerEntry.FlowFamily.INCOME
        or entry.annual_income_entry_id is not None
        for entry in entries
    )
    if has_income:
        return "income"

    has_liability = any(entry.liability_id is not None for entry in entries)
    if has_liability:
        return "debt_payment"

    has_expense = any(
        (
            entry.flow_family == LedgerEntry.FlowFamily.EXPENSE
            or entry.annual_expense_entry_id is not None
        )
        and entry.liability_id is None
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
        return "investment_purchase"

    asset_entries_count = sum(
        1 for entry in entries if entry.account.account_type == LedgerAccount.AccountType.ASSET
    )
    if asset_entries_count >= 2:
        return "transfer"

    return "other"


def apply_transaction_list_filters(queryset: QuerySet, params) -> QuerySet:
    date_from = (params.get("date_from") or "").strip()
    date_to = (params.get("date_to") or "").strip()
    account_id = (params.get("account_id") or "").strip()
    query = (params.get("query") or "").strip()
    kind = (params.get("kind") or "").strip()
    category_key = (params.get("category_key") or "").strip()
    subcategory_key = (params.get("subcategory_key") or "").strip()

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

    if query:
        queryset = queryset.filter(
            Q(description__icontains=query)
            | Q(notes__icontains=query)
            | Q(entries__account__name__icontains=query)
        ).distinct()

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
        return queryset.filter(
            Exists(
                entry_subquery.filter(
                    Q(flow_family=LedgerEntry.FlowFamily.INCOME)
                    | Q(annual_income_entry_id__isnull=False)
                )
            )
        )
    if kind == "expense":
        return queryset.filter(
            Exists(
                entry_subquery.filter(
                    (
                        Q(flow_family=LedgerEntry.FlowFamily.EXPENSE)
                        | Q(annual_expense_entry_id__isnull=False)
                    )
                    & Q(liability_id__isnull=True)
                )
            )
        )
    if kind == "debt_payment":
        return queryset.filter(
            ~Q(origin=LedgerTransaction.Origin.SYSTEM),
            ~Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION),
            Exists(entry_subquery.filter(liability_id__isnull=False)),
        )
    if kind == "investment_purchase":
        return queryset.filter(
            ~Q(origin=LedgerTransaction.Origin.SYSTEM),
            ~Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION),
            Exists(
                entry_subquery.filter(
                    asset_id__isnull=False,
                    account__account_type=LedgerAccount.AccountType.ASSET,
                    account__asset_id__isnull=False,
                )
            )
        )
    if kind == "revaluation":
        return queryset.filter(
            Q(origin=LedgerTransaction.Origin.SYSTEM)
            | Q(quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION)
        )
    if kind == "transfer":
        return queryset.annotate(
            asset_entry_count=Count(
                "entries",
                filter=Q(entries__account__account_type=LedgerAccount.AccountType.ASSET),
                distinct=True,
            ),
            income_like_entry_count=Count(
                "entries",
                filter=Q(entries__flow_family=LedgerEntry.FlowFamily.INCOME)
                | Q(entries__annual_income_entry_id__isnull=False),
                distinct=True,
            ),
            expense_like_entry_count=Count(
                "entries",
                filter=Q(entries__flow_family=LedgerEntry.FlowFamily.EXPENSE)
                | Q(entries__annual_expense_entry_id__isnull=False),
                distinct=True,
            ),
            liability_entry_count=Count(
                "entries",
                filter=Q(entries__liability_id__isnull=False),
                distinct=True,
            ),
            investment_entry_count=Count(
                "entries",
                filter=Q(entries__asset_id__isnull=False),
                distinct=True,
            ),
        ).filter(
            asset_entry_count__gte=2,
            income_like_entry_count=0,
            expense_like_entry_count=0,
            liability_entry_count=0,
            investment_entry_count=0,
        )
    raise ValidationError({"kind": "Query param 'kind' invalido."})
