from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnualExpenseEntryViewSet,
    AnnualExpenseMonthlyCheckinViewSet,
    AnnualIncomeEntryViewSet,
)

router = DefaultRouter()
router.register(r"annual-income", AnnualIncomeEntryViewSet, basename="annual-income")
router.register(r"annual-expense", AnnualExpenseEntryViewSet, basename="annual-expense")
router.register(
    r"annual-expense-checkins",
    AnnualExpenseMonthlyCheckinViewSet,
    basename="annual-expense-checkins",
)

urlpatterns = [
    path("", include(router.urls)),
]
