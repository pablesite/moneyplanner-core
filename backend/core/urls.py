from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DbBackupView,
    DbRestoreView,
    FxConvertAPIView,
    FxRefreshAPIView,
    FxRateViewSet,
    InflationIndexViewSet,
    MarketDataSyncAPIView,
    MarketDataStatusAPIView,
    PortableDataImportAPIView,
    PortableDataMetaAPIView,
)

router = DefaultRouter()
router.register(r"fx-rates", FxRateViewSet, basename="fx-rates")
router.register(r"inflation", InflationIndexViewSet, basename="inflation")

urlpatterns = [
    path("", include(router.urls)),
    path("fx/convert/", FxConvertAPIView.as_view(), name="fx-convert"),
    path("fx/refresh/", FxRefreshAPIView.as_view(), name="fx-refresh"),
    path("market-data/status/", MarketDataStatusAPIView.as_view(), name="market-data-status"),
    path("market-data/sync/", MarketDataSyncAPIView.as_view(), name="market-data-sync"),
    path("portable-data/meta/", PortableDataMetaAPIView.as_view(), name="portable-data-meta"),
    path("portable-data/import/", PortableDataImportAPIView.as_view(), name="portable-data-import"),
    path("db-backup/", DbBackupView.as_view(), name="db-backup"),
    path("db-restore/", DbRestoreView.as_view(), name="db-restore"),
]
