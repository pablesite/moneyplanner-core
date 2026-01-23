from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Asset, Liability, NetWorthSnapshot
from .serializers import (
    AssetSerializer,
    LiabilitySerializer,
    NetWorthSnapshotSerializer,
    EmptySerializer,
)


class UserScopedQuerySetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)


class AssetViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AssetSerializer
    queryset = Asset.objects.all()


class LiabilityViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LiabilitySerializer
    queryset = Liability.objects.all()


class NetWorthSnapshotViewSet(UserScopedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Solo lectura. La creación/actualización se hace únicamente con from-current.
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
        assets_qs = Asset.objects.filter(
            user=request.user,
            is_active=True,
            tracking_mode=Asset.TrackingMode.MANUAL,
        )
        liabilities_qs = Liability.objects.filter(
            user=request.user,
            is_active=True,
            tracking_mode=Liability.TrackingMode.MANUAL,
        )

        assets_total = assets_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        liabilities_total = liabilities_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        net = assets_total - liabilities_total

        snapshot_date = timezone.localdate()

        snapshot, created = NetWorthSnapshot.objects.update_or_create(
            user=request.user,
            snapshot_date=snapshot_date,
            defaults={
                "total_assets": assets_total,
                "total_liabilities": liabilities_total,
                "net_worth": net,
            },
        )

        data = NetWorthSnapshotSerializer(snapshot).data
        return Response(
            {"created": created, "snapshot": data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class NetWorthSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assets_qs = Asset.objects.filter(
            user=request.user,
            is_active=True,
            tracking_mode=Asset.TrackingMode.MANUAL,
        )
        liabilities_qs = Liability.objects.filter(
            user=request.user,
            is_active=True,
            tracking_mode=Liability.TrackingMode.MANUAL,
        )

        assets_total = assets_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        liabilities_total = liabilities_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        net = assets_total - liabilities_total

        assets_by_category = {
            row["category"]: str(row["s"] or Decimal("0"))
            for row in assets_qs.values("category").annotate(s=Sum("amount")).order_by("category")
        }
        liabilities_by_category = {
            row["category"]: str(row["s"] or Decimal("0"))
            for row in liabilities_qs.values("category").annotate(s=Sum("amount")).order_by("category")
        }

        return Response(
            {
                "total_assets": str(assets_total),
                "total_liabilities": str(liabilities_total),
                "net_worth": str(net),
                "assets_by_category": assets_by_category,
                "liabilities_by_category": liabilities_by_category,
            }
        )
