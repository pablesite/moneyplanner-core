from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.view_mixins import UserScopedQuerySetMixin
from .api import raise_api_validation_error
from .models import Asset, Liability, LiquidityMonthlyCheckin, NetWorthSnapshot
from .serializers import (
    AssetSerializer,
    EmptySerializer,
    LiabilitySerializer,
    LiquidityMonthlyCheckinSerializer,
    NetWorthSnapshotSerializer,
)
from .services import (
    delete_generated_budget_commitments_for_liability,
    get_financed_asset_queryset_for_user,
    get_base_currency_for_user,
    get_liquidity_asset_queryset_for_user,
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


class AssetViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AssetSerializer
    queryset = Asset.objects.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["base_currency"] = get_base_currency_for_user(user=self.request.user)
        return ctx


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

    def perform_update(self, serializer):
        serializer.save()


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
