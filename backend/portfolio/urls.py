from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AllocationScopesView,
    AllocationStrategyViewSet,
    ContainerCashAccountViewSet,
    ContributionBasketViewSet,
    ContributionCommitmentViewSet,
    ContributionSolveView,
    PortfolioAllocationView,
    PortfolioExposureView,
    PositionExposureViewSet,
    PositionAllocationRuleViewSet,
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
    PortfolioWorkspaceView,
    PortfolioOperationConfirmView,
    PortfolioOperationOptionsView,
    PortfolioOperationPreviewView,
    PortfolioImportConfirmView,
    PortfolioImportDetailView,
    PortfolioImportPreviewView,
    PortfolioImportUploadView,
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
router.register(r"exposures", PositionExposureViewSet, basename="portfolio-exposures")
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
router.register(r"strategies", AllocationStrategyViewSet, basename="portfolio-strategies")
router.register(
    r"allocation-rules", PositionAllocationRuleViewSet, basename="portfolio-allocation-rules"
)
router.register(r"commitments", ContributionCommitmentViewSet, basename="portfolio-commitments")
router.register(r"baskets", ContributionBasketViewSet, basename="portfolio-baskets")

urlpatterns = [
    path("", include(router.urls)),
    path("bootstrap/", PortfolioBootstrapView.as_view(), name="portfolio-bootstrap"),
    path("readiness/", PortfolioReadinessView.as_view(), name="portfolio-readiness"),
    path("allocation/", PortfolioAllocationView.as_view(), name="portfolio-allocation"),
    path("allocation/scopes/", AllocationScopesView.as_view(), name="portfolio-allocation-scopes"),
    path("exposure/", PortfolioExposureView.as_view(), name="portfolio-exposure"),
    path("contribution/solve/", ContributionSolveView.as_view(), name="portfolio-contribution"),
    path("overview/", PortfolioOverviewView.as_view(), name="portfolio-overview"),
    path("timeline/", PortfolioTimelineView.as_view(), name="portfolio-timeline"),
    path("performance/", PortfolioPerformanceView.as_view(), name="portfolio-performance"),
    path("quality/", PortfolioQualityView.as_view(), name="portfolio-quality"),
    path("workspace/", PortfolioWorkspaceView.as_view(), name="portfolio-workspace"),
    path(
        "operations/options/",
        PortfolioOperationOptionsView.as_view(),
        name="portfolio-operation-options",
    ),
    path(
        "operations/preview/",
        PortfolioOperationPreviewView.as_view(),
        name="portfolio-operation-preview",
    ),
    path(
        "operations/confirm/",
        PortfolioOperationConfirmView.as_view(),
        name="portfolio-operation-confirm",
    ),
    path("imports/upload/", PortfolioImportUploadView.as_view(), name="portfolio-import-upload"),
    path(
        "imports/<int:batch_id>/",
        PortfolioImportDetailView.as_view(),
        name="portfolio-import-detail",
    ),
    path(
        "imports/<int:batch_id>/preview/",
        PortfolioImportPreviewView.as_view(),
        name="portfolio-import-preview",
    ),
    path(
        "imports/<int:batch_id>/confirm/",
        PortfolioImportConfirmView.as_view(),
        name="portfolio-import-confirm",
    ),
    path(
        "valuation-health/",
        PortfolioValuationHealthView.as_view(),
        name="portfolio-valuation-health",
    ),
]
