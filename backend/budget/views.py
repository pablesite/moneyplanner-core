from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .checkins import resolve_confirmed_at
from .models import (
    AnnualExpenseEntry,
    AnnualExpenseMonthlyCheckin,
    AnnualIncomeEntry,
    AnnualIncomeMonthlyCheckin,
    MonthlyClose,
)
from .query_params import (
    parse_optional_int_query_param,
    parse_required_int_query_param,
)
from .plan_lineage import plan_lineage_for_entry
from .serializers import (
    AnnualExpenseEntrySerializer,
    AnnualExpenseMonthlyCheckinSerializer,
    AnnualIncomeEntrySerializer,
    AnnualIncomeMonthlyCheckinSerializer,
)
from .services import (
    build_expense_monthly_plan_vs_executed_summary,
    build_income_monthly_plan_vs_executed_summary,
    effective_annual_expense_entries,
    effective_annual_income_entries,
)


def _assert_monthly_close_not_finalized(*, user, fiscal_year: int, month: int) -> None:
    """Raises 409 if a MonthlyClose FINALIZED or LOCKED exists for this period."""
    if MonthlyClose.objects.filter(
        user=user,
        fiscal_year=fiscal_year,
        month=month,
        status__in=[MonthlyClose.Status.FINALIZED, MonthlyClose.Status.LOCKED],
    ).exists():
        raise PermissionDenied(
            "El cierre mensual de este periodo está finalizado o bloqueado. "
            "Reabre el cierre antes de modificar los checkins."
        )


class AnnualEntrySummaryMixin:
    monthly_summary_builder = None

    @action(detail=False, methods=["get"], url_path="totals")
    def totals(self, request):
        queryset = self.get_queryset().filter(is_active=True)
        total_annual = queryset.aggregate(value=Sum("amount_annual"))["value"] or 0
        return Response({"total_annual": str(total_annual), "currency_hint": "mixed"})

    @action(detail=False, methods=["get"], url_path="monthly-summary")
    def monthly_summary(self, request):
        fiscal_year = parse_required_int_query_param(request.query_params, "year")
        payload = self.monthly_summary_builder(
            user=request.user,
            fiscal_year=fiscal_year,
        )
        return Response(payload)


class PlanManagedEntry(APIException):
    status_code = 403
    default_code = "plan_managed_entry"
    default_detail = (
        "Esta partida está gestionada por Mi Plan. Abre el acontecimiento correspondiente para "
        "modificarla o retirarla."
    )


class PlanManagedEntryProtectionMixin:
    def _assert_not_plan_managed(self, instance) -> None:
        if plan_lineage_for_entry(instance).is_managed:
            raise PlanManagedEntry()

    def update(self, request, *args, **kwargs):
        self._assert_not_plan_managed(self.get_object())
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._assert_not_plan_managed(self.get_object())
        return super().destroy(request, *args, **kwargs)


class AnnualIncomeEntryViewSet(
    PlanManagedEntryProtectionMixin, AnnualEntrySummaryMixin, viewsets.ModelViewSet
):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualIncomeEntrySerializer
    monthly_summary_builder = staticmethod(build_income_monthly_plan_vs_executed_summary)

    def get_queryset(self):
        queryset = AnnualIncomeEntry.objects.filter(user=self.request.user)
        fiscal_year = parse_optional_int_query_param(self.request.query_params, "year")
        if fiscal_year is not None:
            queryset = effective_annual_income_entries(
                user=self.request.user, fiscal_year=fiscal_year
            )
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AnnualExpenseEntryViewSet(
    PlanManagedEntryProtectionMixin, AnnualEntrySummaryMixin, viewsets.ModelViewSet
):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualExpenseEntrySerializer
    monthly_summary_builder = staticmethod(build_expense_monthly_plan_vs_executed_summary)

    def get_queryset(self):
        queryset = AnnualExpenseEntry.objects.filter(user=self.request.user)
        fiscal_year = parse_optional_int_query_param(self.request.query_params, "year")
        source_liability_id = parse_optional_int_query_param(
            self.request.query_params, "source_liability_id"
        )
        source_asset_id = parse_optional_int_query_param(
            self.request.query_params, "source_asset_id"
        )
        if fiscal_year is not None:
            queryset = effective_annual_expense_entries(
                user=self.request.user, fiscal_year=fiscal_year
            )
        if source_liability_id is not None:
            queryset = queryset.filter(source_liability_id=source_liability_id)
        if source_asset_id is not None:
            queryset = queryset.filter(source_asset_id=source_asset_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AnnualExpenseMonthlyCheckinViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualExpenseMonthlyCheckinSerializer

    def get_queryset(self):
        queryset = AnnualExpenseMonthlyCheckin.objects.filter(user=self.request.user)
        fiscal_year = parse_optional_int_query_param(self.request.query_params, "year")
        annual_expense_entry_id = parse_optional_int_query_param(
            self.request.query_params, "annual_expense_entry_id"
        )
        month = parse_optional_int_query_param(self.request.query_params, "month")
        if fiscal_year is not None:
            queryset = queryset.filter(fiscal_year=fiscal_year)
        if annual_expense_entry_id is not None:
            queryset = queryset.filter(annual_expense_entry_id=annual_expense_entry_id)
        if month is not None:
            queryset = queryset.filter(month=month)
        return queryset.order_by("-fiscal_year", "-month", "-updated_at")

    def perform_create(self, serializer):
        fiscal_year = serializer.validated_data.get("fiscal_year")
        month = serializer.validated_data.get("month")
        if fiscal_year and month:
            _assert_monthly_close_not_finalized(
                user=self.request.user, fiscal_year=fiscal_year, month=month
            )
        status_value = serializer.validated_data.get("status")
        confirmed_at = resolve_confirmed_at(
            current_confirmed_at=None,
            status_value=status_value,
            skipped_status=AnnualExpenseMonthlyCheckin.Status.SKIPPED,
        )
        serializer.save(user=self.request.user, confirmed_at=confirmed_at)

    def perform_update(self, serializer):
        fiscal_year = serializer.instance.fiscal_year
        month = serializer.instance.month
        _assert_monthly_close_not_finalized(
            user=self.request.user, fiscal_year=fiscal_year, month=month
        )
        status_value = serializer.validated_data.get("status", serializer.instance.status)
        confirmed_at = resolve_confirmed_at(
            current_confirmed_at=serializer.instance.confirmed_at,
            status_value=status_value,
            skipped_status=AnnualExpenseMonthlyCheckin.Status.SKIPPED,
        )
        serializer.save(confirmed_at=confirmed_at)


class AnnualIncomeMonthlyCheckinViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualIncomeMonthlyCheckinSerializer

    def get_queryset(self):
        queryset = AnnualIncomeMonthlyCheckin.objects.filter(user=self.request.user)
        fiscal_year = parse_optional_int_query_param(self.request.query_params, "year")
        annual_income_entry_id = parse_optional_int_query_param(
            self.request.query_params, "annual_income_entry_id"
        )
        month = parse_optional_int_query_param(self.request.query_params, "month")
        if fiscal_year is not None:
            queryset = queryset.filter(fiscal_year=fiscal_year)
        if annual_income_entry_id is not None:
            queryset = queryset.filter(annual_income_entry_id=annual_income_entry_id)
        if month is not None:
            queryset = queryset.filter(month=month)
        return queryset.order_by("-fiscal_year", "-month", "-updated_at")

    def perform_create(self, serializer):
        fiscal_year = serializer.validated_data.get("fiscal_year")
        month = serializer.validated_data.get("month")
        if fiscal_year and month:
            _assert_monthly_close_not_finalized(
                user=self.request.user, fiscal_year=fiscal_year, month=month
            )
        status_value = serializer.validated_data.get("status")
        confirmed_at = resolve_confirmed_at(
            current_confirmed_at=None,
            status_value=status_value,
            skipped_status=AnnualIncomeMonthlyCheckin.Status.SKIPPED,
        )
        serializer.save(user=self.request.user, confirmed_at=confirmed_at)

    def perform_update(self, serializer):
        fiscal_year = serializer.instance.fiscal_year
        month = serializer.instance.month
        _assert_monthly_close_not_finalized(
            user=self.request.user, fiscal_year=fiscal_year, month=month
        )
        status_value = serializer.validated_data.get("status", serializer.instance.status)
        confirmed_at = resolve_confirmed_at(
            current_confirmed_at=serializer.instance.confirmed_at,
            status_value=status_value,
            skipped_status=AnnualIncomeMonthlyCheckin.Status.SKIPPED,
        )
        serializer.save(confirmed_at=confirmed_at)
