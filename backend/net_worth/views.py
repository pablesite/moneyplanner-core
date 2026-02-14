from django.core.exceptions import ValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .api import raise_api_validation_error
from .models import Asset, Liability, NetWorthSnapshot
from .serializers import (
    AssetSerializer,
    EmptySerializer,
    LiabilitySerializer,
    NetWorthSnapshotSerializer,
)
from .services import (
    build_net_worth_summary,
    create_or_update_snapshot_from_current,
    get_financed_asset_queryset_for_user,
    get_base_currency_for_user,
    serialize_net_worth_summary,
)

class UserScopedQuerySetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)


class AssetViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AssetSerializer
    queryset = Asset.objects.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["base_currency"] = get_base_currency_for_user(user=self.request.user)
        return ctx


class LiabilityViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LiabilitySerializer
    queryset = Liability.objects.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["base_currency"] = get_base_currency_for_user(user=self.request.user)
        ctx["financed_asset_queryset"] = get_financed_asset_queryset_for_user(user=self.request.user)
        return ctx


class NetWorthSnapshotViewSet(
    UserScopedQuerySetMixin, mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet
):
    """
    Read-only snapshots. Creation/update only through from-current.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NetWorthSnapshotSerializer
    queryset = NetWorthSnapshot.objects.all()

    def get_serializer_class(self):
        if self.action == "from_current":
            return EmptySerializer
        return super().get_serializer_class()

    @action(detail=False, methods=["post"], url_path="from-current")
    def from_current(self, request):
        try:
            snapshot, created = create_or_update_snapshot_from_current(user=request.user)
        except ValidationError as exc:
            raise_api_validation_error(exc)

        data = NetWorthSnapshotSerializer(snapshot).data
        return Response(
            {"created": created, "snapshot": data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class NetWorthSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            summary = build_net_worth_summary(user=request.user)
        except ValidationError as exc:
            raise_api_validation_error(exc)

        return Response(serialize_net_worth_summary(summary))
