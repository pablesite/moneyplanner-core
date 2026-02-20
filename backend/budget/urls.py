from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AnnualIncomeEntryViewSet

router = DefaultRouter()
router.register(r"annual-income", AnnualIncomeEntryViewSet, basename="annual-income")

urlpatterns = [
    path("", include(router.urls)),
]
