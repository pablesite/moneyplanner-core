from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContainerCashAccountViewSet,
    InstrumentViewSet,
    InvestmentContainerViewSet,
    PortfolioBootstrapView,
    PortfolioMigrationIssueViewSet,
    PortfolioPositionViewSet,
    PortfolioReadinessView,
    PortfolioViewSet,
    PositionOwnershipPeriodViewSet,
)

router = DefaultRouter()
router.register(r"portfolios", PortfolioViewSet, basename="portfolios")
router.register(r"containers", InvestmentContainerViewSet, basename="portfolio-containers")
router.register(r"cash-accounts", ContainerCashAccountViewSet, basename="portfolio-cash-accounts")
router.register(r"instruments", InstrumentViewSet, basename="portfolio-instruments")
router.register(r"positions", PortfolioPositionViewSet, basename="portfolio-positions")
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
]
