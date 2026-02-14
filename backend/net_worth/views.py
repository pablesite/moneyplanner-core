from django.core.exceptions import ValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
    get_base_currency_for_user,
)


def _raise_api_validation_error(exc: ValidationError) -> None:
    message = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
    raise DRFValidationError({"detail": message}) from exc


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
            _raise_api_validation_error(exc)

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
            _raise_api_validation_error(exc)

        return Response(
            {
                "base_currency": summary["base_currency"],
                "total_assets": str(summary["total_assets"]),
                "total_liabilities": str(summary["total_liabilities"]),
                "net_worth": str(summary["net_worth"]),
                "assets_by_category": {
                    k: str(v) for k, v in summary["assets_by_category"].items()
                },
                "assets_by_subcategory": {
                    k: str(v) for k, v in summary["assets_by_subcategory"].items()
                },
                "liabilities_by_category": {
                    k: str(v) for k, v in summary["liabilities_by_category"].items()
                },
                "inflation_region": summary["inflation_region"],
                "inflation_base_period": (
                    str(summary["inflation_base_period"]) if summary["inflation_base_period"] else None
                ),
                "total_assets_real": (
                    str(summary["total_assets_real"]) if summary["total_assets_real"] is not None else None
                ),
                "total_liabilities_real": (
                    str(summary["total_liabilities_real"])
                    if summary["total_liabilities_real"] is not None
                    else None
                ),
                "net_worth_real": (
                    str(summary["net_worth_real"]) if summary["net_worth_real"] is not None else None
                ),
                "assets_by_category_real": (
                    {k: str(v) for k, v in summary["assets_by_category_real"].items()}
                    if summary["assets_by_category_real"] is not None
                    else None
                ),
                "liabilities_by_category_real": (
                    {k: str(v) for k, v in summary["liabilities_by_category_real"].items()}
                    if summary["liabilities_by_category_real"] is not None
                    else None
                ),
                "liabilities_asset_backed": str(summary["liabilities_asset_backed"]),
                "liabilities_unbacked": str(summary["liabilities_unbacked"]),
                "liabilities_asset_backed_real": (
                    str(summary["liabilities_asset_backed_real"])
                    if summary["liabilities_asset_backed_real"] is not None
                    else None
                ),
                "liabilities_unbacked_real": (
                    str(summary["liabilities_unbacked_real"])
                    if summary["liabilities_unbacked_real"] is not None
                    else None
                ),
            }
        )
