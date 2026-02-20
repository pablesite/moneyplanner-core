from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AnnualExpenseEntryViewSet, AnnualIncomeEntryViewSet

router = DefaultRouter()
router.register(r"annual-income", AnnualIncomeEntryViewSet, basename="annual-income")
router.register(r"annual-expense", AnnualExpenseEntryViewSet, basename="annual-expense")

urlpatterns = [
    path("", include(router.urls)),
]
