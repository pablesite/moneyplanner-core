from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from memberships.models import FamilyMember

from .models import FinancialPlan, PlanAssetFunction, ProjectionSnapshot
from .serializers import (
    AssetFunctionUpdateSerializer,
    FinancialPlanSerializer,
    FindingSerializer,
    PlanFamilyMemberSerializer,
    PlanEventSerializer,
    ProjectionSnapshotSerializer,
    RecommendationSerializer,
    ScenarioSerializer,
)
from .models import PlanEvent, Recommendation, Scenario
from .services_classification import AssetClassificationService
from .services_findings import FindingService
from .services_foundations import FoundationService
from .services_projection import ProjectionService, get_assumption_set, serialize_classification
from .services_recommendations import RecommendationService
from .services_scenarios import ScenarioService


def attach_calculated_at(result: dict, calculated_at: str) -> dict:
    result["calculated_at"] = calculated_at
    for metric in result.get("summary", {}).values():
        if isinstance(metric, dict):
            metric["calculated_at"] = calculated_at
    return result


class FinancialPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def get_plan(self, request) -> FinancialPlan:
        plan = FinancialPlan.objects.filter(user=request.user).prefetch_related("members").first()
        if not plan:
            raise NotFound("Financial plan not found.")
        return plan

    def get(self, request):
        serializer = FinancialPlanSerializer(self.get_plan(request), context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        existing = FinancialPlan.objects.filter(user=request.user).first()
        serializer = FinancialPlanSerializer(
            existing,
            data=request.data,
            context={"request": request},
            partial=existing is not None,
        )
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        return Response(
            FinancialPlanSerializer(plan, context={"request": request}).data,
            status=status.HTTP_200_OK if existing else status.HTTP_201_CREATED,
        )

    def patch(self, request):
        serializer = FinancialPlanSerializer(
            self.get_plan(request),
            data=request.data,
            context={"request": request},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        return Response(FinancialPlanSerializer(plan, context={"request": request}).data)


class RecalculateProjectionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan = get_object_or_404(FinancialPlan, user=request.user)
        scenario = (
            request.query_params.get("scenario") or request.data.get("scenario") or "expected"
        )
        result = ProjectionService().recalculate(plan=plan, assumption_name=scenario)
        snapshot = plan.projection_snapshots.filter(input_hash=result["input_hash"]).first()
        if snapshot:
            attach_calculated_at(result, snapshot.calculated_at.isoformat())
        return Response(result)


class ProjectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = get_object_or_404(FinancialPlan, user=request.user)
        scenario = request.query_params.get("scenario") or "expected"
        assumption_set = get_assumption_set(name=scenario)
        result = ProjectionService().calculate(plan=plan, assumption_set=assumption_set)
        return Response(attach_calculated_at(result, timezone.now().isoformat()))


class ProjectionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = get_object_or_404(FinancialPlan, user=request.user)
        snapshots = ProjectionSnapshot.objects.filter(plan=plan, is_official=True)[:20]
        return Response(ProjectionSnapshotSerializer(snapshots, many=True).data)


class PlanMembersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = get_object_or_404(FinancialPlan, user=request.user)
        return Response(PlanFamilyMemberSerializer(plan.members.all(), many=True).data)

    def post(self, request):
        serializer = PlanFamilyMemberSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        member = serializer.save()
        return Response(
            PlanFamilyMemberSerializer(member).data,
            status=status.HTTP_201_CREATED,
        )


class PlanMemberDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk: int):
        member = get_object_or_404(
            FamilyMember,
            user=request.user,
            id=pk,
            role=FamilyMember.Role.ADULT,
        )
        serializer = PlanFamilyMemberSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(PlanFamilyMemberSerializer(serializer.save()).data)


class AssetFunctionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from accounts.models import UserSettings

        settings, _ = UserSettings.objects.get_or_create(user=request.user)
        classification = AssetClassificationService().summarize(
            user=request.user,
            base_currency=(settings.base_currency or "EUR").upper(),
        )
        return Response(serialize_classification(classification))

    def put(self, request):
        items = request.data if isinstance(request.data, list) else request.data.get("items", [])
        serializer = AssetFunctionUpdateSerializer(
            data=items,
            many=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        for item in serializer.validated_data:
            if item["function"] is None:
                PlanAssetFunction.objects.filter(
                    user=request.user,
                    asset_id=item["asset_id"],
                ).delete()
            else:
                PlanAssetFunction.objects.update_or_create(
                    user=request.user,
                    asset_id=item["asset_id"],
                    defaults={"function": item["function"]},
                )
        return self.get(request)


class ScenarioListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = get_object_or_404(FinancialPlan, user=request.user)
        scenarios = Scenario.objects.filter(plan=plan).prefetch_related("events")
        return Response(ScenarioSerializer(scenarios, many=True).data)

    def post(self, request):
        get_object_or_404(FinancialPlan, user=request.user)
        serializer = ScenarioSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        scenario = serializer.save()
        return Response(ScenarioSerializer(scenario).data, status=status.HTTP_201_CREATED)


class ScenarioDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk: int) -> Scenario:
        return get_object_or_404(
            Scenario.objects.prefetch_related("events"),
            pk=pk,
            plan__user=request.user,
        )

    def get(self, request, pk: int):
        return Response(ScenarioSerializer(self.get_object(request, pk)).data)

    def patch(self, request, pk: int):
        scenario = self.get_object(request, pk)
        serializer = ScenarioSerializer(
            scenario,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        return Response(ScenarioSerializer(serializer.save()).data)


class ScenarioComparisonView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        scenario = get_object_or_404(
            Scenario.objects.select_related("plan").prefetch_related("events"),
            pk=pk,
            plan__user=request.user,
        )
        assumption = request.query_params.get("scenario") or "expected"
        return Response(ScenarioService().compare(scenario=scenario, assumption_name=assumption))


class ScenarioAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        scenario = get_object_or_404(Scenario, pk=pk, plan__user=request.user)
        assumption = (
            request.query_params.get("scenario") or request.data.get("scenario") or "expected"
        )
        result = ScenarioService().accept(scenario=scenario, assumption_name=assumption)
        return Response(
            {
                "event": PlanEventSerializer(result["event"]).data,
                "projection": result["projection"],
                "budget_entries_created": result["budget_entries_created"],
            }
        )


class ScenarioDiscardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        scenario = get_object_or_404(Scenario, pk=pk, plan__user=request.user)
        return Response(ScenarioSerializer(ScenarioService().discard(scenario=scenario)).data)


class PlanEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = get_object_or_404(FinancialPlan, user=request.user)
        events = PlanEvent.objects.filter(plan=plan)
        return Response(PlanEventSerializer(events, many=True).data)


class PlanEventDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk: int):
        event = get_object_or_404(PlanEvent, pk=pk, plan__user=request.user)
        serializer = PlanEventSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(PlanEventSerializer(serializer.save()).data)


class FoundationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = get_object_or_404(FinancialPlan, user=request.user)
        return Response(FoundationService().calculate(plan=plan))


class FindingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = get_object_or_404(FinancialPlan, user=request.user)
        findings = FindingService().evaluate(plan=plan)
        return Response(FindingSerializer(findings, many=True).data)


class RecommendationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plan = get_object_or_404(FinancialPlan, user=request.user)
        recommendations = RecommendationService().refresh(plan=plan)
        return Response(RecommendationSerializer(recommendations, many=True).data)


class RecommendationActionView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk: int) -> Recommendation:
        return get_object_or_404(Recommendation, pk=pk, finding__plan__user=request.user)


class RecommendationAcceptView(RecommendationActionView):
    def post(self, request, pk: int):
        recommendation = RecommendationService().accept(recommendation=self.get_object(request, pk))
        return Response(RecommendationSerializer(recommendation).data)


class RecommendationDismissView(RecommendationActionView):
    def post(self, request, pk: int):
        recommendation = RecommendationService().dismiss(
            recommendation=self.get_object(request, pk)
        )
        return Response(RecommendationSerializer(recommendation).data)


class RecommendationSimulateView(RecommendationActionView):
    def post(self, request, pk: int):
        scenario = RecommendationService().simulate(recommendation=self.get_object(request, pk))
        return Response(ScenarioSerializer(scenario).data, status=status.HTTP_201_CREATED)
