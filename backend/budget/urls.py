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
    MonthlyClosePlanImpactView,
    MonthlyCloseReopenView,
    MonthlyCloseView,
)
from .views_settlement import (
    SettlementActivateView,
    SettlementConfigurationView,
    SettlementDisableView,
    SettlementReadinessView,
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
        "settlement/configuration/",
        SettlementConfigurationView.as_view(),
        name="settlement-configuration",
    ),
    path(
        "settlement/readiness/",
        SettlementReadinessView.as_view(),
        name="settlement-readiness",
    ),
    path(
        "settlement/activate/",
        SettlementActivateView.as_view(),
        name="settlement-activate",
    ),
    path(
        "settlement/disable/",
        SettlementDisableView.as_view(),
        name="settlement-disable",
    ),
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
    path(
        "monthly-closes/<int:pk>/plan-impact/",
        MonthlyClosePlanImpactView.as_view(),
        name="monthly-close-plan-impact",
    ),
]
