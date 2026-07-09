from django.urls import path

from .views import (
    AssetFunctionsView,
    FinancialPlanView,
    PlanMemberDetailView,
    PlanMembersView,
    ProjectionHistoryView,
    ProjectionView,
    RecalculateProjectionView,
)

urlpatterns = [
    path("", FinancialPlanView.as_view(), name="financial-plan"),
    path("recalculate/", RecalculateProjectionView.as_view(), name="financial-plan-recalculate"),
    path("projection/", ProjectionView.as_view(), name="financial-plan-projection"),
    path("history/", ProjectionHistoryView.as_view(), name="financial-plan-history"),
    path("members/", PlanMembersView.as_view(), name="financial-plan-members"),
    path("members/<int:pk>/", PlanMemberDetailView.as_view(), name="financial-plan-member-detail"),
    path("asset-functions/", AssetFunctionsView.as_view(), name="financial-plan-asset-functions"),
]
