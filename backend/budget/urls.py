from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnualExpenseEntryViewSet,
    AnnualExpenseMonthlyCheckinViewSet,
    AnnualIncomeEntryViewSet,
    AnnualIncomeMonthlyCheckinViewSet,
)
from .views_monthly_close import (
    MonthlyCloseFinalizeView,
    MonthlyCloseLockView,
    MonthlyCloseReopenView,
    MonthlyCloseView,
)

router = DefaultRouter()
router.register(r"annual-income", AnnualIncomeEntryViewSet, basename="annual-income")
router.register(
    r"annual-income-checkins",
    AnnualIncomeMonthlyCheckinViewSet,
    basename="annual-income-checkins",
)
router.register(r"annual-expense", AnnualExpenseEntryViewSet, basename="annual-expense")
router.register(
    r"annual-expense-checkins",
    AnnualExpenseMonthlyCheckinViewSet,
    basename="annual-expense-checkins",
)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "monthly-close/<int:year>/<int:month>/",
        MonthlyCloseView.as_view(),
        name="monthly-close",
    ),
    path(
        "monthly-close/<int:year>/<int:month>/finalize/",
        MonthlyCloseFinalizeView.as_view(),
        name="monthly-close-finalize",
    ),
    path(
        "monthly-close/<int:year>/<int:month>/reopen/",
        MonthlyCloseReopenView.as_view(),
        name="monthly-close-reopen",
    ),
    path(
        "monthly-close/<int:year>/<int:month>/lock/",
        MonthlyCloseLockView.as_view(),
        name="monthly-close-lock",
    ),
]
