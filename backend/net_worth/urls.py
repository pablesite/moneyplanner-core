from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AssetViewSet,
    LiabilityViewSet,
    LiquidityMonthlyCheckinViewSet,
    LiquidityMonthlySummaryAPIView,
    NetWorthSnapshotViewSet,
    NetWorthSummaryAPIView,
)

router = DefaultRouter()
router.register(r"assets", AssetViewSet, basename="assets")
router.register(r"liabilities", LiabilityViewSet, basename="liabilities")
router.register(r"liquidity-checkins", LiquidityMonthlyCheckinViewSet, basename="liquidity-checkins")
router.register(r"snapshots", NetWorthSnapshotViewSet, basename="snapshots")

urlpatterns = [
    path("", include(router.urls)),
    path("summary/", NetWorthSummaryAPIView.as_view(), name="net-worth-summary"),
    path("liquidity/monthly-summary/", LiquidityMonthlySummaryAPIView.as_view(), name="liquidity-monthly-summary"),
]
