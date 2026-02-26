from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import FamilyMember, Ownership, OwnershipLink
from .serializers import (
    FamilyMemberSerializer,
    OwnershipLinkReadSerializer,
    OwnershipLinkSyncSerializer,
    OwnershipReadSerializer,
    OwnershipWriteSerializer,
)
from .services import (
    create_member_with_default_ownership,
    delete_member_and_individual_ownership,
    delete_ownership,
    list_ownership_links_for_user,
    sync_ownership_link_from_payload,
    update_ownership,
)


class UserScopedQuerySetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)


class FamilyMemberViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = FamilyMemberSerializer
    permission_classes = [IsAuthenticated]
    queryset = FamilyMember.objects.all()

    def perform_create(self, serializer):
        member = create_member_with_default_ownership(
            user=self.request.user,
            validated_data=serializer.validated_data,
        )
        serializer.instance = member

    def destroy(self, request, *args, **kwargs):
        member = self.get_object()
        delete_member_and_individual_ownership(member=member)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnershipViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Ownership.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.select_related("member").prefetch_related("splits", "splits__member")

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return OwnershipReadSerializer
        return OwnershipWriteSerializer

    def perform_update(self, serializer):
        instance = self.get_object()
        updated = update_ownership(
            ownership=instance,
            user=self.request.user,
            validated_data=serializer.validated_data,
        )
        serializer.instance = updated

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        delete_ownership(ownership=instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
