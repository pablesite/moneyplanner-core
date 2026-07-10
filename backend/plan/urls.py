from django.urls import path

from .views import (
    AssetFunctionsView,
    FinancialPlanView,
    FindingsView,
    FoundationsView,
    PlanEventDetailView,
    PlanEventsView,
    PlanMemberDetailView,
    PlanMembersView,
    ProjectionHistoryView,
    ProjectionView,
    RecalculateProjectionView,
    RecommendationAcceptView,
    RecommendationDismissView,
    RecommendationSimulateView,
    RecommendationsView,
    ScenarioAcceptView,
    ScenarioComparisonView,
    ScenarioDetailView,
    ScenarioDiscardView,
    ScenarioListView,
)

urlpatterns = [
    path("", FinancialPlanView.as_view(), name="financial-plan"),
    path("recalculate/", RecalculateProjectionView.as_view(), name="financial-plan-recalculate"),
    path("projection/", ProjectionView.as_view(), name="financial-plan-projection"),
    path("history/", ProjectionHistoryView.as_view(), name="financial-plan-history"),
    path("members/", PlanMembersView.as_view(), name="financial-plan-members"),
    path("members/<int:pk>/", PlanMemberDetailView.as_view(), name="financial-plan-member-detail"),
    path("asset-functions/", AssetFunctionsView.as_view(), name="financial-plan-asset-functions"),
    path("foundations/", FoundationsView.as_view(), name="financial-plan-foundations"),
    path("findings/", FindingsView.as_view(), name="financial-plan-findings"),
    path("recommendations/", RecommendationsView.as_view(), name="financial-plan-recommendations"),
    path(
        "recommendations/<int:pk>/accept/",
        RecommendationAcceptView.as_view(),
        name="financial-plan-recommendation-accept",
    ),
    path(
        "recommendations/<int:pk>/dismiss/",
        RecommendationDismissView.as_view(),
        name="financial-plan-recommendation-dismiss",
    ),
    path(
        "recommendations/<int:pk>/simulate/",
        RecommendationSimulateView.as_view(),
        name="financial-plan-recommendation-simulate",
    ),
    path("scenarios/", ScenarioListView.as_view(), name="financial-plan-scenarios"),
    path(
        "scenarios/<int:pk>/", ScenarioDetailView.as_view(), name="financial-plan-scenario-detail"
    ),
    path(
        "scenarios/<int:pk>/comparison/",
        ScenarioComparisonView.as_view(),
        name="financial-plan-scenario-comparison",
    ),
    path(
        "scenarios/<int:pk>/accept/",
        ScenarioAcceptView.as_view(),
        name="financial-plan-scenario-accept",
    ),
    path(
        "scenarios/<int:pk>/discard/",
        ScenarioDiscardView.as_view(),
        name="financial-plan-scenario-discard",
    ),
    path("events/", PlanEventsView.as_view(), name="financial-plan-events"),
    path("events/<int:pk>/", PlanEventDetailView.as_view(), name="financial-plan-event-detail"),
]
