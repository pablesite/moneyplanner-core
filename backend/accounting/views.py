from decimal import Decimal

from django.db.models import Prefetch, Q, QuerySet, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from budget.query_params import parse_optional_int_query_param, parse_required_int_query_param

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .pagination import paginate_transactions
from .serializers import (
    LedgerAccountSerializer,
    LedgerEntrySerializer,
    LedgerTransactionSerializer,
    QuickLedgerTransactionSerializer,
)
from .services_budget import build_budget_derived_suggestions
from .services_summaries import (
    build_account_balances_summary,
    build_daily_balance_series,
    build_monthly_accounting_summary,
    validate_budget_suggestion_filters,
)
from .services_ledger import delete_ledger_account
from .services_transactions import (
    apply_transaction_list_filters,
    filter_transactions_by_review_state,
    validate_balance_summary_filters,
)


class LedgerAccountViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LedgerAccountSerializer

    def get_queryset(self):
        queryset = LedgerAccount.objects.filter(user=self.request.user).select_related(
            "asset", "liability"
        )
        account_type = self.request.query_params.get("account_type")
        is_active = self.request.query_params.get("is_active")
        if account_type:
            queryset = queryset.filter(account_type=account_type)
        if is_active in {"true", "false"}:
            queryset = queryset.filter(is_active=(is_active == "true"))
        return queryset.order_by("account_type", "name", "id")

    def perform_destroy(self, instance: LedgerAccount) -> None:
        if instance.origin == LedgerAccount.Origin.SYSTEM:
            raise ValidationError(
                {
                    "detail": (
                        "No se puede eliminar una cuenta de sistema. "
                        "Estas cuentas se gestionan automaticamente."
                    )
                }
            )
        delete_ledger_account(account=instance)

    @action(detail=False, methods=["get"], url_path="balances")
    def balances(self, request):
        fiscal_year = parse_optional_int_query_param(request.query_params, "year")
        month = parse_optional_int_query_param(request.query_params, "month")
        validate_balance_summary_filters(fiscal_year=fiscal_year, month=month)
        return Response(
            build_account_balances_summary(
                user_id=request.user.id,
                fiscal_year=fiscal_year,
                month=month,
                account_type=request.query_params.get("account_type") or None,
                status=request.query_params.get("status") or None,
            )
        )


class LedgerTransactionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LedgerTransactionSerializer

    @staticmethod
    def _parse_bool_query_param(*, param_name: str, raw_value: str | None, default: bool) -> bool:
        value = (raw_value or ("true" if default else "false")).strip().lower()
        if value in {"true", "1", "yes"}:
            return True
        if value in {"false", "0", "no"}:
            return False
        raise ValidationError({param_name: f"Query param '{param_name}' invalido."})

    @staticmethod
    def _signed_impact_for_account(*, account_type: str, side: str, amount: Decimal) -> Decimal:
        increases_on_debit = account_type in {
            LedgerAccount.AccountType.ASSET,
            LedgerAccount.AccountType.EXPENSE,
        }
        if (side == LedgerEntry.Side.DEBIT) == increases_on_debit:
            return amount
        return -amount

    def _sum_account_entry_impacts(
        self,
        *,
        account: LedgerAccount,
        transaction_ids: QuerySet | None = None,
    ) -> Decimal:
        queryset = LedgerEntry.objects.filter(
            account_id=account.id,
            transaction__user_id=account.user_id,
        )
        if transaction_ids is not None:
            queryset = queryset.filter(transaction_id__in=transaction_ids)

        impact = Decimal("0")
        for row in queryset.values("side").annotate(amount_total=Sum("amount")):
            amount = row["amount_total"] or Decimal("0")
            impact += self._signed_impact_for_account(
                account_type=account.account_type,
                side=row["side"],
                amount=amount,
            )
        return impact

    def _build_account_balance_after_map(
        self,
        *,
        account: LedgerAccount,
        rows: list[LedgerTransaction],
    ) -> dict[int, Decimal]:
        if not rows:
            return {}

        first_row = rows[0]
        newer_transaction_ids = (
            self.get_queryset()
            .filter(entries__account_id=account.id)
            .filter(
                Q(booking_date__gt=first_row.booking_date)
                | Q(booking_date=first_row.booking_date, id__gt=first_row.id)
            )
            .distinct()
            .order_by()
            .values("id")
        )
        running_balance = self._sum_account_entry_impacts(account=account)
        running_balance -= self._sum_account_entry_impacts(
            account=account,
            transaction_ids=newer_transaction_ids,
        )
        by_transaction_id: dict[int, Decimal] = {}
        for txn in rows:
            by_transaction_id[txn.id] = running_balance
            impact = Decimal("0")
            for entry in txn.entries.all():
                if entry.account_id != account.id:
                    continue
                impact += self._signed_impact_for_account(
                    account_type=account.account_type,
                    side=entry.side,
                    amount=entry.amount,
                )
            running_balance -= impact
        return by_transaction_id

    def get_queryset(self):
        queryset = LedgerTransaction.objects.filter(user=self.request.user).prefetch_related(
            Prefetch("entries", queryset=LedgerEntry.objects.select_related("account"))
        )
        fiscal_year = parse_optional_int_query_param(self.request.query_params, "year")
        month = parse_optional_int_query_param(self.request.query_params, "month")
        status_value = self.request.query_params.get("status")
        if fiscal_year is not None:
            queryset = queryset.filter(booking_date__year=fiscal_year)
        if month is not None:
            queryset = queryset.filter(booking_date__month=month)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset.order_by("-booking_date", "-id")

    def list(self, request, *args, **kwargs):
        queryset_without_review = apply_transaction_list_filters(
            self.get_queryset(),
            request.query_params,
        )
        needs_review_count = filter_transactions_by_review_state(
            queryset_without_review, "needs_review"
        ).count()
        review_state = (request.query_params.get("review_state") or "").strip()
        queryset = (
            filter_transactions_by_review_state(queryset_without_review, review_state)
            if review_state
            else queryset_without_review
        )

        page_size = parse_optional_int_query_param(request.query_params, "page_size") or 50
        if page_size < 1 or page_size > 200:
            raise ValidationError({"page_size": "Query param 'page_size' invalido (1-200)."})
        cursor = (request.query_params.get("cursor") or "").strip() or None
        include_total = self._parse_bool_query_param(
            param_name="include_total",
            raw_value=request.query_params.get("include_total"),
            default=True,
        )
        include_entries = self._parse_bool_query_param(
            param_name="include_entries",
            raw_value=request.query_params.get("include_entries"),
            default=True,
        )
        rows, next_cursor, total_count = paginate_transactions(
            queryset=queryset,
            page_size=page_size,
            cursor=cursor,
            include_total=include_total,
        )
        serializer_context = self.get_serializer_context()
        serializer_context = {**serializer_context, "include_entries": include_entries}
        account_id = parse_optional_int_query_param(request.query_params, "account_id")
        if account_id is not None:
            account = LedgerAccount.objects.filter(user=request.user, id=account_id).first()
            if account is None:
                raise ValidationError(
                    {"account_id": "La cuenta no existe o no pertenece al usuario autenticado."}
                )
            serializer_context = {
                **serializer_context,
                "account_balance_after_by_tx_id": self._build_account_balance_after_map(
                    account=account,
                    rows=rows,
                ),
            }

        serializer = self.get_serializer(rows, many=True, context=serializer_context)
        return Response(
            {
                "results": serializer.data,
                "next_cursor": next_cursor,
                "total_count": total_count,
                "needs_review_count": needs_review_count,
            }
        )

    @action(detail=False, methods=["get"], url_path="monthly-summary")
    def monthly_summary(self, request):
        fiscal_year = parse_required_int_query_param(request.query_params, "year")
        return Response(
            build_monthly_accounting_summary(user_id=request.user.id, fiscal_year=fiscal_year)
        )

    @action(detail=False, methods=["get"], url_path="daily-balance-series")
    def daily_balance_series(self, request):
        today = timezone.localdate()
        date_from_raw = (request.query_params.get("date_from") or "").strip()
        date_to_raw = (request.query_params.get("date_to") or "").strip()
        status_raw = (request.query_params.get("status") or "").strip()
        ownership_id_raw = (request.query_params.get("ownership_id") or "").strip()
        account_ids_raw = (request.query_params.get("account_ids") or "").strip()
        ownership_is_null = None
        ownership_id = None
        account_ids = None
        try:
            date_from = parse_date(date_from_raw) if date_from_raw else None
        except ValueError as exc:
            raise ValidationError(
                {"date_from": "Query param 'date_from' invalido (YYYY-MM-DD)."}
            ) from exc
        try:
            date_to = parse_date(date_to_raw) if date_to_raw else today
        except ValueError as exc:
            raise ValidationError(
                {"date_to": "Query param 'date_to' invalido (YYYY-MM-DD)."}
            ) from exc
        status_value = status_raw or LedgerTransaction.Status.POSTED

        if date_from_raw and date_from is None:
            raise ValidationError({"date_from": "Query param 'date_from' invalido (YYYY-MM-DD)."})
        if date_to is None:
            raise ValidationError({"date_to": "Query param 'date_to' invalido (YYYY-MM-DD)."})
        if status_value not in {
            LedgerTransaction.Status.POSTED,
            LedgerTransaction.Status.DRAFT,
        }:
            raise ValidationError({"status": "Query param 'status' invalido."})
        if ownership_id_raw:
            if ownership_id_raw.lower() in {"null", "none"}:
                ownership_is_null = True
            else:
                try:
                    ownership_id = int(ownership_id_raw)
                except ValueError as exc:
                    raise ValidationError(
                        {"ownership_id": "Query param 'ownership_id' invalido."}
                    ) from exc
                if ownership_id < 1:
                    raise ValidationError({"ownership_id": "Query param 'ownership_id' invalido."})
        if account_ids_raw:
            try:
                account_ids = list(
                    dict.fromkeys(int(value.strip()) for value in account_ids_raw.split(","))
                )
            except ValueError as exc:
                raise ValidationError(
                    {"account_ids": "Query param 'account_ids' invalido."}
                ) from exc
            if not account_ids or any(account_id < 1 for account_id in account_ids):
                raise ValidationError({"account_ids": "Query param 'account_ids' invalido."})

        return Response(
            build_daily_balance_series(
                user_id=request.user.id,
                date_from=date_from,
                date_to=date_to,
                status=status_value,
                ownership_id=ownership_id,
                ownership_is_null=ownership_is_null,
                account_ids=account_ids,
            )
        )

    @action(detail=False, methods=["get"], url_path="budget-suggestions")
    def budget_suggestions(self, request):
        fiscal_year = parse_required_int_query_param(request.query_params, "year")
        lookback_years = parse_optional_int_query_param(request.query_params, "lookback_years") or 2
        validate_budget_suggestion_filters(lookback_years=lookback_years)
        return Response(
            build_budget_derived_suggestions(
                user_id=request.user.id,
                fiscal_year=fiscal_year,
                lookback_years=lookback_years,
            )
        )

    @action(detail=False, methods=["post"], url_path="quick-entry")
    def quick_entry(self, request):
        serializer = QuickLedgerTransactionSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        return Response(
            LedgerTransactionSerializer(transaction, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class LedgerEntryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LedgerEntrySerializer

    def get_queryset(self):
        queryset = LedgerEntry.objects.filter(transaction__user=self.request.user).select_related(
            "account", "transaction"
        )
        transaction_id = parse_optional_int_query_param(self.request.query_params, "transaction_id")
        account_id = parse_optional_int_query_param(self.request.query_params, "account_id")
        fiscal_year = parse_optional_int_query_param(self.request.query_params, "year")
        month = parse_optional_int_query_param(self.request.query_params, "month")
        if transaction_id is not None:
            queryset = queryset.filter(transaction_id=transaction_id)
        if account_id is not None:
            queryset = queryset.filter(account_id=account_id)
        if fiscal_year is not None:
            queryset = queryset.filter(transaction__booking_date__year=fiscal_year)
        if month is not None:
            queryset = queryset.filter(transaction__booking_date__month=month)
        return queryset.order_by("-transaction__booking_date", "-id")
