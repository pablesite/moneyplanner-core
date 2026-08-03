from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from config.view_mixins import UserScopedQuerySetMixin
from .models import FamilyMember, Ownership, OwnershipLink
from .serializers import (
    FamilyMemberSerializer,
    OwnershipLinkReadSerializer,
    OwnershipLinkSyncSerializer,
    OwnershipReadSerializer,
    OwnershipWriteSerializer,
)
from .services import (
    delete_member_and_individual_ownership,
    delete_ownership,
    ensure_primary_family_member_for_user,
    list_ownership_links_for_user,
    sync_ownership_link_from_payload,
)
from .services_allocations import resolve_ownership_allocation


class FamilyMemberViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = FamilyMemberSerializer
    permission_classes = [IsAuthenticated]
    queryset = FamilyMember.objects.all()

    def perform_destroy(self, instance):
        delete_member_and_individual_ownership(member=instance)

    @action(detail=False, methods=["post"], url_path="ensure-primary")
    def ensure_primary(self, request):
        member = ensure_primary_family_member_for_user(user=request.user)
        serializer = self.get_serializer(member)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OwnershipViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Ownership.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.select_related("member").prefetch_related(
            "splits", "splits__member", "income_rules"
        )

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return OwnershipReadSerializer
        return OwnershipWriteSerializer

    def perform_destroy(self, instance):
        delete_ownership(ownership=instance)

    @action(detail=True, methods=["get"], url_path="allocation-preview")
    def allocation_preview(self, request, pk=None):
        ownership = self.get_object()
        try:
            fiscal_year = int(request.query_params["year"])
            month = int(request.query_params["month"])
            if fiscal_year < 1 or month < 1 or month > 12:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            return Response(
                {"detail": "year y month son obligatorios y deben formar un periodo valido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            resolve_ownership_allocation(
                ownership=ownership,
                fiscal_year=fiscal_year,
                month=month,
                persist=True,
            )
        )


class OwnershipLinkViewSet(UserScopedQuerySetMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = OwnershipLink.objects.all()

    def list(self, request):
        qs = list_ownership_links_for_user(user=request.user)
        serializer = OwnershipLinkReadSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request):
        serializer = OwnershipLinkSyncSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        result = sync_ownership_link_from_payload(
            user=request.user,
            payload=serializer.validated_data,
        )
        return Response(result, status=status.HTTP_200_OK)
