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
    PlanFamilyMemberSerializer,
    ProjectionSnapshotSerializer,
)
from .services_classification import AssetClassificationService
from .services_projection import ProjectionService, get_assumption_set, serialize_classification


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
