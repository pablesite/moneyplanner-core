from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContainerCashAccountViewSet,
    InstrumentViewSet,
    InstrumentPriceViewSet,
    InstrumentProviderMappingViewSet,
    InvestmentContainerViewSet,
    PortfolioBootstrapView,
    PortfolioMigrationIssueViewSet,
    PortfolioOverviewView,
    PortfolioPerformanceView,
    PortfolioPositionViewSet,
    PortfolioQualityView,
    PortfolioReadinessView,
    PortfolioTimelineView,
    PortfolioValuationHealthView,
    PortfolioViewSet,
    PositionOwnershipPeriodViewSet,
    PositionValuationViewSet,
)

router = DefaultRouter()
router.register(r"portfolios", PortfolioViewSet, basename="portfolios")
router.register(r"containers", InvestmentContainerViewSet, basename="portfolio-containers")
router.register(r"cash-accounts", ContainerCashAccountViewSet, basename="portfolio-cash-accounts")
router.register(r"instruments", InstrumentViewSet, basename="portfolio-instruments")
router.register(
    r"provider-mappings", InstrumentProviderMappingViewSet, basename="portfolio-mappings"
)
router.register(r"prices", InstrumentPriceViewSet, basename="portfolio-prices")
router.register(r"positions", PortfolioPositionViewSet, basename="portfolio-positions")
router.register(r"valuations", PositionValuationViewSet, basename="portfolio-valuations")
router.register(
    r"ownership-periods",
    PositionOwnershipPeriodViewSet,
    basename="portfolio-ownership-periods",
)
router.register(r"issues", PortfolioMigrationIssueViewSet, basename="portfolio-issues")

urlpatterns = [
    path("", include(router.urls)),
    path("bootstrap/", PortfolioBootstrapView.as_view(), name="portfolio-bootstrap"),
    path("readiness/", PortfolioReadinessView.as_view(), name="portfolio-readiness"),
    path("overview/", PortfolioOverviewView.as_view(), name="portfolio-overview"),
    path("timeline/", PortfolioTimelineView.as_view(), name="portfolio-timeline"),
    path("performance/", PortfolioPerformanceView.as_view(), name="portfolio-performance"),
    path("quality/", PortfolioQualityView.as_view(), name="portfolio-quality"),
    path(
        "valuation-health/",
        PortfolioValuationHealthView.as_view(),
        name="portfolio-valuation-health",
    ),
]
