from django.utils import timezone
from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    AnnualExpenseEntry,
    AnnualExpenseMonthlyCheckin,
    AnnualIncomeEntry,
    AnnualIncomeMonthlyCheckin,
)
from .serializers import (
    AnnualExpenseEntrySerializer,
    AnnualExpenseMonthlyCheckinSerializer,
    AnnualIncomeEntrySerializer,
    AnnualIncomeMonthlyCheckinSerializer,
)
from .services import (
    build_expense_monthly_plan_vs_executed_summary,
    build_income_monthly_plan_vs_executed_summary,
)


class AnnualIncomeEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualIncomeEntrySerializer

    def get_queryset(self):
        queryset = AnnualIncomeEntry.objects.filter(user=self.request.user)
        year_param = (self.request.query_params.get("year") or "").strip()
        if year_param:
            try:
                year = int(year_param)
            except ValueError:
                year = None
            if year is not None:
                queryset = queryset.filter(fiscal_year=year)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="totals")
    def totals(self, request):
        queryset = self.get_queryset().filter(is_active=True)
        total_annual = queryset.aggregate(value=Sum("amount_annual"))["value"] or 0
        return Response({"total_annual": str(total_annual), "currency_hint": "mixed"})

    @action(detail=False, methods=["get"], url_path="monthly-summary")
    def monthly_summary(self, request):
        year_param = (request.query_params.get("year") or "").strip()
        if not year_param:
            return Response({"detail": "Query param 'year' es obligatorio."}, status=400)
        try:
            fiscal_year = int(year_param)
        except ValueError:
            return Response({"detail": "Query param 'year' invalido."}, status=400)
        payload = build_income_monthly_plan_vs_executed_summary(
            user=request.user,
            fiscal_year=fiscal_year,
        )
        return Response(payload)


class AnnualExpenseEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualExpenseEntrySerializer

    def get_queryset(self):
        queryset = AnnualExpenseEntry.objects.filter(user=self.request.user)
        year_param = (self.request.query_params.get("year") or "").strip()
        source_liability_param = (
            self.request.query_params.get("source_liability_id") or ""
        ).strip()
        if year_param:
            try:
                year = int(year_param)
            except ValueError:
                year = None
            if year is not None:
                queryset = queryset.filter(fiscal_year=year)
        if source_liability_param:
            try:
                source_liability_id = int(source_liability_param)
            except ValueError:
                source_liability_id = None
            if source_liability_id is not None:
                queryset = queryset.filter(source_liability_id=source_liability_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="totals")
    def totals(self, request):
        queryset = self.get_queryset().filter(is_active=True)
        total_annual = queryset.aggregate(value=Sum("amount_annual"))["value"] or 0
        return Response({"total_annual": str(total_annual), "currency_hint": "mixed"})

    @action(detail=False, methods=["get"], url_path="monthly-summary")
    def monthly_summary(self, request):
        year_param = (request.query_params.get("year") or "").strip()
        if not year_param:
            return Response({"detail": "Query param 'year' es obligatorio."}, status=400)
        try:
            fiscal_year = int(year_param)
        except ValueError:
            return Response({"detail": "Query param 'year' invalido."}, status=400)
        payload = build_expense_monthly_plan_vs_executed_summary(
            user=request.user,
            fiscal_year=fiscal_year,
        )
        return Response(payload)


class AnnualExpenseMonthlyCheckinViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualExpenseMonthlyCheckinSerializer

    def get_queryset(self):
        queryset = AnnualExpenseMonthlyCheckin.objects.filter(user=self.request.user)
        year_param = (self.request.query_params.get("year") or "").strip()
        entry_param = (self.request.query_params.get("annual_expense_entry_id") or "").strip()
        month_param = (self.request.query_params.get("month") or "").strip()
        if year_param:
            try:
                queryset = queryset.filter(fiscal_year=int(year_param))
            except ValueError:
                pass
        if entry_param:
            try:
                queryset = queryset.filter(annual_expense_entry_id=int(entry_param))
            except ValueError:
                pass
        if month_param:
            try:
                queryset = queryset.filter(month=int(month_param))
            except ValueError:
                pass
        return queryset.order_by("-fiscal_year", "-month", "-updated_at")

    def perform_create(self, serializer):
        status_value = serializer.validated_data.get("status")
        confirmed_at = None
        if status_value != AnnualExpenseMonthlyCheckin.Status.SKIPPED:
            confirmed_at = timezone.now()
        serializer.save(user=self.request.user, confirmed_at=confirmed_at)

    def perform_update(self, serializer):
        status_value = serializer.validated_data.get("status", serializer.instance.status)
        confirmed_at = serializer.instance.confirmed_at
        if status_value == AnnualExpenseMonthlyCheckin.Status.SKIPPED:
            confirmed_at = None
        else:
            confirmed_at = confirmed_at or timezone.now()
        serializer.save(confirmed_at=confirmed_at)


class AnnualIncomeMonthlyCheckinViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualIncomeMonthlyCheckinSerializer

    def get_queryset(self):
        queryset = AnnualIncomeMonthlyCheckin.objects.filter(user=self.request.user)
        year_param = (self.request.query_params.get("year") or "").strip()
        entry_param = (self.request.query_params.get("annual_income_entry_id") or "").strip()
        month_param = (self.request.query_params.get("month") or "").strip()
        if year_param:
            try:
                queryset = queryset.filter(fiscal_year=int(year_param))
            except ValueError:
                pass
        if entry_param:
            try:
                queryset = queryset.filter(annual_income_entry_id=int(entry_param))
            except ValueError:
                pass
        if month_param:
            try:
                queryset = queryset.filter(month=int(month_param))
            except ValueError:
                pass
        return queryset.order_by("-fiscal_year", "-month", "-updated_at")

    def perform_create(self, serializer):
        status_value = serializer.validated_data.get("status")
        confirmed_at = None
        if status_value != AnnualIncomeMonthlyCheckin.Status.SKIPPED:
            confirmed_at = timezone.now()
        serializer.save(user=self.request.user, confirmed_at=confirmed_at)

    def perform_update(self, serializer):
        status_value = serializer.validated_data.get("status", serializer.instance.status)
        confirmed_at = serializer.instance.confirmed_at
        if status_value == AnnualIncomeMonthlyCheckin.Status.SKIPPED:
            confirmed_at = None
        else:
            confirmed_at = confirmed_at or timezone.now()
        serializer.save(confirmed_at=confirmed_at)
