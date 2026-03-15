from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from budget.query_params import parse_optional_int_query_param, parse_required_int_query_param

from .models import LedgerAccount, LedgerEntry, LedgerTransaction
from .serializers import (
    LedgerAccountSerializer,
    LedgerEntrySerializer,
    LedgerTransactionSerializer,
    QuickLedgerTransactionSerializer,
)
from .services import build_monthly_accounting_summary


class LedgerAccountViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LedgerAccountSerializer

    def get_queryset(self):
        queryset = LedgerAccount.objects.filter(user=self.request.user)
        account_type = self.request.query_params.get("account_type")
        is_active = self.request.query_params.get("is_active")
        if account_type:
            queryset = queryset.filter(account_type=account_type)
        if is_active in {"true", "false"}:
            queryset = queryset.filter(is_active=(is_active == "true"))
        return queryset.order_by("account_type", "name", "id")


class LedgerTransactionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LedgerTransactionSerializer

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
        return queryset.order_by("-booking_date", "-created_at", "-id")

    @action(detail=False, methods=["get"], url_path="monthly-summary")
    def monthly_summary(self, request):
        fiscal_year = parse_required_int_query_param(request.query_params, "year")
        return Response(
            build_monthly_accounting_summary(user_id=request.user.id, fiscal_year=fiscal_year)
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
