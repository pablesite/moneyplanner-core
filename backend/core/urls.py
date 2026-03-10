from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    FxRateViewSet,
    InflationIndexViewSet,
    PortableDataImportAPIView,
    PortableDataMetaAPIView,
)

router = DefaultRouter()
router.register(r"fx-rates", FxRateViewSet, basename="fx-rates")
router.register(r"inflation", InflationIndexViewSet, basename="inflation")

urlpatterns = [
    path("", include(router.urls)),
    path("portable-data/meta/", PortableDataMetaAPIView.as_view(), name="portable-data-meta"),
    path("portable-data/import/", PortableDataImportAPIView.as_view(), name="portable-data-import"),
]
