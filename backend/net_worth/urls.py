from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AssetViewSet,
    AssetValuationViewSet,
    InvestmentAssetEventViewSet,
    LiabilityViewSet,
    LiabilityEventViewSet,
    LiabilityValuationViewSet,
    LiquidityAssetEventViewSet,
    LiquidityMonthlyCheckinViewSet,
    LiquidityMonthlySummaryAPIView,
    NetWorthSummaryAPIView,
    NetWorthTimelineAPIView,
)

router = DefaultRouter()
router.register(r"assets", AssetViewSet, basename="assets")
router.register(r"investment-events", InvestmentAssetEventViewSet, basename="investment-events")
router.register(r"asset-valuations", AssetValuationViewSet, basename="asset-valuations")
router.register(r"liabilities", LiabilityViewSet, basename="liabilities")
router.register(r"liability-events", LiabilityEventViewSet, basename="liability-events")
router.register(r"liability-valuations", LiabilityValuationViewSet, basename="liability-valuations")
router.register(r"liquidity-events", LiquidityAssetEventViewSet, basename="liquidity-events")
router.register(
    r"liquidity-checkins", LiquidityMonthlyCheckinViewSet, basename="liquidity-checkins"
)
urlpatterns = [
    path("", include(router.urls)),
    path("summary/", NetWorthSummaryAPIView.as_view(), name="net-worth-summary"),
    path("timeline/", NetWorthTimelineAPIView.as_view(), name="net-worth-timeline"),
    path(
        "liquidity/monthly-summary/",
        LiquidityMonthlySummaryAPIView.as_view(),
        name="liquidity-monthly-summary",
    ),
]
