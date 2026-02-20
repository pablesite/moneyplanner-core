from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AnnualIncomeEntryViewSet, FxRateViewSet, InflationIndexViewSet

router = DefaultRouter()
router.register(r"fx-rates", FxRateViewSet, basename="fx-rates")
router.register(r"inflation", InflationIndexViewSet, basename="inflation")
router.register(r"annual-income", AnnualIncomeEntryViewSet, basename="annual-income")

urlpatterns = [
    path("", include(router.urls)),
]
