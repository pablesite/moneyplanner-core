from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.view_mixins import UserScopedQuerySetMixin
from .api import raise_api_validation_error
from .models import (
    Asset,
    AssetValuation,
    InvestmentAssetEvent,
    Liability,
    LiabilityEvent,
    LiabilityValuation,
    LiquidityAssetEvent,
    LiquidityMonthlyCheckin,
    NetWorthSnapshot,
)
from .serializers import (
    AssetSerializer,
    AssetValuationSerializer,
    EmptySerializer,
    InvestmentAssetEventSerializer,
    LiabilitySerializer,
    LiabilityEventSerializer,
    LiabilityValuationSerializer,
    LiquidityAssetEventSerializer,
    LiquidityMonthlyCheckinSerializer,
    NetWorthSnapshotSerializer,
)
from .services import (
    get_financed_asset_queryset_for_user,
    get_base_currency_for_user,
    get_liquidity_asset_queryset_for_user,
)
from .services_assets_budget import (
    delete_generated_budget_commitments_for_asset,
    sync_generated_budget_commitments_for_asset,
)
from .services_liabilities_budget import (
    delete_generated_budget_commitments_for_liability,
    sync_generated_budget_commitments_for_liability,
)
from .services_liquidity import (
    build_liquidity_monthly_summary,
    parse_liquidity_monthly_summary_period,
)
from .services_snapshots import (
    create_or_update_snapshot_from_current,
)
from .services_snapshot_api import import_snapshots_bulk_from_request
from .services_summaries import build_net_worth_summary, serialize_net_worth_summary
from .services_timelines import (
    build_asset_timeline,
    build_liability_timeline,
    build_net_worth_timeline,
    parse_timeline_query_params,
)


class AssetViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AssetSerializer
    queryset = Asset.objects.prefetch_related("improvements").all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["base_currency"] = get_base_currency_for_user(user=self.request.user)
        return ctx

    def perform_create(self, serializer):
        asset = serializer.save()
        sync_generated_budget_commitments_for_asset(asset=asset)

    def perform_update(self, serializer):
        asset = serializer.save()
        sync_generated_budget_commitments_for_asset(asset=asset)

    def perform_destroy(self, instance):
        with transaction.atomic():
            delete_generated_budget_commitments_for_asset(asset=instance)
            instance.delete()

    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        asset = self.get_object()
        params = parse_timeline_query_params(query_params=request.query_params)
        try:
            timeline = build_asset_timeline(asset=asset, end_date=params["end_date"])
        except ValidationError as exc:
            raise_api_validation_error(exc)
        return Response(timeline)


class LiabilityViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LiabilitySerializer
    queryset = Liability.objects.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["base_currency"] = get_base_currency_for_user(user=self.request.user)
        ctx["financed_asset_queryset"] = get_financed_asset_queryset_for_user(
            user=self.request.user
        )
        return ctx

    def perform_create(self, serializer):
        liability = serializer.save()
        sync_generated_budget_commitments_for_liability(liability=liability)

    def perform_update(self, serializer):
        liability = serializer.save()
        sync_generated_budget_commitments_for_liability(liability=liability)

    def perform_destroy(self, instance):
        with transaction.atomic():
            delete_generated_budget_commitments_for_liability(liability=instance)
            instance.delete()

    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        liability = self.get_object()
        params = parse_timeline_query_params(query_params=request.query_params)
        try:
            timeline = build_liability_timeline(
                liability=liability,
                end_date=params["end_date"],
            )
        except ValidationError as exc:
            raise_api_validation_error(exc)
        return Response(timeline)


def _assert_liquidity_monthly_close_not_finalized(*, user, fiscal_year: int, month: int) -> None:
    from budget.models import MonthlyClose
    from rest_framework.exceptions import PermissionDenied

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


class LiquidityMonthlyCheckinViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LiquidityMonthlyCheckinSerializer
    queryset = LiquidityMonthlyCheckin.objects.select_related("asset").all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["liquidity_asset_queryset"] = get_liquidity_asset_queryset_for_user(
            user=self.request.user
        )
        return ctx

    def perform_create(self, serializer):
        fiscal_year = serializer.validated_data.get("fiscal_year")
        month = serializer.validated_data.get("month")
        if fiscal_year and month:
            _assert_liquidity_monthly_close_not_finalized(
                user=self.request.user, fiscal_year=fiscal_year, month=month
            )
        serializer.save()

    def perform_update(self, serializer):
        fiscal_year = serializer.instance.fiscal_year
        month = serializer.instance.month
        _assert_liquidity_monthly_close_not_finalized(
            user=self.request.user, fiscal_year=fiscal_year, month=month
        )
        serializer.save()


class AssetValuationViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AssetValuationSerializer
    queryset = AssetValuation.objects.select_related("asset").all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["asset_queryset"] = Asset.objects.filter(user=self.request.user, is_active=True)
        return ctx


class InvestmentAssetEventViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InvestmentAssetEventSerializer
    queryset = InvestmentAssetEvent.objects.select_related("asset").all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["investment_asset_queryset"] = Asset.objects.filter(
            user=self.request.user,
            is_active=True,
            category=Asset.Category.INVESTMENTS,
        )
        return ctx


class LiquidityAssetEventViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LiquidityAssetEventSerializer
    queryset = LiquidityAssetEvent.objects.select_related("asset").all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["liquidity_event_asset_queryset"] = Asset.objects.filter(
            user=self.request.user,
            is_active=True,
            category=Asset.Category.CASH,
        )
        return ctx


class LiabilityEventViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LiabilityEventSerializer
    queryset = LiabilityEvent.objects.select_related("liability").all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["liability_event_queryset"] = Liability.objects.filter(
            user=self.request.user, is_active=True
        )
        return ctx


class LiabilityValuationViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LiabilityValuationSerializer
    queryset = LiabilityValuation.objects.select_related("liability").all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["liability_queryset"] = Liability.objects.filter(user=self.request.user, is_active=True)
        return ctx


class NetWorthSnapshotViewSet(
    UserScopedQuerySetMixin, mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet
):
    """
    Read-only snapshots. Creation/update only through from-current.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NetWorthSnapshotSerializer
    queryset = NetWorthSnapshot.objects.all()

    def get_serializer_class(self):
        if self.action == "from_current":
            return EmptySerializer
        return super().get_serializer_class()

    @action(detail=False, methods=["post"], url_path="from-current")
    def from_current(self, request):
        try:
            snapshot, created = create_or_update_snapshot_from_current(user=request.user)
        except ValidationError as exc:
            raise_api_validation_error(exc)

        data = NetWorthSnapshotSerializer(snapshot).data
        return Response(
            {"created": created, "snapshot": data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="import-bulk")
    def import_bulk(self, request):
        result = import_snapshots_bulk_from_request(
            user=request.user,
            request_data=request.data,
            request=request,
        )
        return Response(
            result,
            status=status.HTTP_200_OK,
        )


class NetWorthSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            summary = build_net_worth_summary(user=request.user)
        except ValidationError as exc:
            raise_api_validation_error(exc)

        return Response(serialize_net_worth_summary(summary))


class LiquidityMonthlySummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        fiscal_year, month = parse_liquidity_monthly_summary_period(
            query_params=request.query_params
        )

        try:
            summary = build_liquidity_monthly_summary(
                user=request.user,
                fiscal_year=fiscal_year,
                month=month,
            )
        except ValidationError as exc:
            raise_api_validation_error(exc)
        return Response(summary)


class NetWorthTimelineAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = parse_timeline_query_params(query_params=request.query_params)
        try:
            timeline = build_net_worth_timeline(
                user=request.user,
                start_date=params["start_date"],
                end_date=params["end_date"],
                asset_category=params["asset_category"],
                liability_category=params["liability_category"],
            )
        except ValidationError as exc:
            raise_api_validation_error(exc)
        return Response(timeline)
