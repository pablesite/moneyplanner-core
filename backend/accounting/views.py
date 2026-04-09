import json
from decimal import Decimal

from django.db.models import Prefetch
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
from .moneywiz_import import (
    build_moneywiz_import_preview,
    commit_moneywiz_import,
    extract_moneywiz_csv_text,
)
from .services import (
    apply_transaction_list_filters,
    build_account_balances_summary,
    build_budget_derived_suggestions,
    build_monthly_accounting_summary,
    validate_balance_summary_filters,
    validate_budget_suggestion_filters,
)
from .services_ledger import get_account_balance


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
        if instance.asset_id is not None:
            from net_worth.models import Asset

            Asset.objects.filter(
                id=instance.asset_id,
                user_id=instance.user_id,
                accounting_account_id=instance.id,
            ).update(
                accounting_account_id=None,
                tracking_mode=Asset.TrackingMode.MANUAL,
            )
        if instance.liability_id is not None:
            from net_worth.models import Liability

            Liability.objects.filter(
                id=instance.liability_id,
                user_id=instance.user_id,
                accounting_account_id=instance.id,
            ).update(
                accounting_account_id=None,
                tracking_mode=Liability.TrackingMode.MANUAL,
            )

        transaction_ids = list(
            LedgerEntry.objects.filter(account_id=instance.id)
            .values_list("transaction_id", flat=True)
            .distinct()
        )
        if transaction_ids:
            LedgerTransaction.objects.filter(
                user_id=instance.user_id, id__in=transaction_ids
            ).delete()
        instance.delete()

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
    def _signed_impact_for_account(
        *, account_type: str, side: str, amount: Decimal
    ) -> Decimal:
        increases_on_debit = account_type in {
            LedgerAccount.AccountType.ASSET,
            LedgerAccount.AccountType.EXPENSE,
        }
        if (side == LedgerEntry.Side.DEBIT) == increases_on_debit:
            return amount
        return -amount

    def _build_account_balance_after_map(self, *, account: LedgerAccount) -> dict[int, Decimal]:
        account_rows = list(
            self.get_queryset()
            .filter(entries__account_id=account.id)
            .distinct()
            .order_by("-booking_date", "-id")
        )
        running_balance = get_account_balance(account=account)
        by_transaction_id: dict[int, Decimal] = {}
        for transaction in account_rows:
            by_transaction_id[transaction.id] = running_balance
            impact = Decimal("0")
            for entry in transaction.entries.all():
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
        queryset = self.get_queryset()
        queryset = apply_transaction_list_filters(queryset, request.query_params)

        page_size = parse_optional_int_query_param(request.query_params, "page_size") or 50
        if page_size < 1 or page_size > 200:
            raise ValidationError({"page_size": "Query param 'page_size' invalido (1-200)."})
        cursor = (request.query_params.get("cursor") or "").strip() or None
        rows, next_cursor, total_count = paginate_transactions(
            queryset=queryset,
            page_size=page_size,
            cursor=cursor,
        )
        serializer_context = self.get_serializer_context()
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
                    account=account
                ),
            }

        serializer = self.get_serializer(rows, many=True, context=serializer_context)
        return Response(
            {
                "results": serializer.data,
                "next_cursor": next_cursor,
                "total_count": total_count,
            }
        )

    @action(detail=False, methods=["get"], url_path="monthly-summary")
    def monthly_summary(self, request):
        fiscal_year = parse_required_int_query_param(request.query_params, "year")
        return Response(
            build_monthly_accounting_summary(user_id=request.user.id, fiscal_year=fiscal_year)
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

    @action(
        detail=False,
        methods=["post"],
        url_path="import-moneywiz/preview",
    )
    def import_preview(self, request):
        csv_text = extract_moneywiz_csv_text(
            csv_text=request.data.get("csv_text"),
            file=request.FILES.get("file"),
        )
        payload = build_moneywiz_import_preview(
            user=request.user,
            csv_text=csv_text,
        )
        return Response(payload)

    @action(
        detail=False,
        methods=["post"],
        url_path="import-moneywiz/commit",
    )
    def import_commit(self, request):
        csv_text = extract_moneywiz_csv_text(
            csv_text=request.data.get("csv_text"),
            file=request.FILES.get("file"),
        )
        account_id_map: dict[str, int] = {}
        raw_map = request.data.get("account_id_map")
        if raw_map:
            try:
                account_id_map = json.loads(raw_map)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        payload = commit_moneywiz_import(
            user=request.user,
            csv_text=csv_text,
            account_id_map=account_id_map or None,
        )
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(
        detail=False,
        methods=["post"],
        url_path="delete-imported",
    )
    def delete_imported(self, request):
        queryset = LedgerTransaction.objects.filter(
            user=request.user,
            origin=LedgerTransaction.Origin.IMPORT,
        )
        deleted_count = queryset.count()
        queryset.delete()
        return Response({"deleted_count": deleted_count}, status=status.HTTP_200_OK)


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
