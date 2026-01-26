from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Asset, Liability, NetWorthSnapshot
from .serializers import (
    AssetSerializer,
    LiabilitySerializer,
    NetWorthSnapshotSerializer,
    EmptySerializer,
)

from accounts.models import UserSettings
from core.services import (
    convert_currency,
    adjust_for_inflation,
    get_latest_inflation_period,
)


def _get_base_currency(user) -> str:
    # Robusto: si no existe settings (usuarios creados antes), lo crea.
    UserSettings.objects.get_or_create(user=user)
    return user.settings.base_currency


class UserScopedQuerySetMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)


class AssetViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AssetSerializer
    queryset = Asset.objects.all()


class LiabilityViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LiabilitySerializer
    queryset = Liability.objects.all()


class NetWorthSnapshotViewSet(UserScopedQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Solo lectura. La creación/actualización se hace únicamente con from-current.
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
        base_currency = _get_base_currency(request.user)

        assets_qs = Asset.objects.filter(
            user=request.user,
            is_active=True,
            tracking_mode=Asset.TrackingMode.MANUAL,
        )
        liabilities_qs = Liability.objects.filter(
            user=request.user,
            is_active=True,
            tracking_mode=Liability.TrackingMode.MANUAL,
        )

        snapshot_date = timezone.localdate()

        try:
            assets_total = sum(
                (
                    convert_currency(a.amount, a.currency, base_currency, date=snapshot_date)
                    for a in assets_qs
                ),
                start=Decimal("0"),
            )
            liabilities_total = sum(
                (
                    convert_currency(l.amount, l.currency, base_currency, date=snapshot_date)
                    for l in liabilities_qs
                ),
                start=Decimal("0"),
            )
        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        net = assets_total - liabilities_total

        snapshot, created = NetWorthSnapshot.objects.update_or_create(
            user=request.user,
            snapshot_date=snapshot_date,
            defaults={
                "base_currency": base_currency,
                "total_assets": assets_total,
                "total_liabilities": liabilities_total,
                "net_worth": net,
            },
        )

        data = NetWorthSnapshotSerializer(snapshot).data
        return Response(
            {"created": created, "snapshot": data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class NetWorthSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        base_currency = _get_base_currency(request.user)
        today = timezone.localdate()

        assets_qs = Asset.objects.filter(
            user=request.user,
            is_active=True,
            tracking_mode=Asset.TrackingMode.MANUAL,
        )
        liabilities_qs = Liability.objects.filter(
            user=request.user,
            is_active=True,
            tracking_mode=Liability.TrackingMode.MANUAL,
        )

        try:
            assets_total = sum(
                (
                    convert_currency(a.amount, a.currency, base_currency, date=today)
                    for a in assets_qs
                ),
                start=Decimal("0"),
            )
            liabilities_total = sum(
                (
                    convert_currency(l.amount, l.currency, base_currency, date=today)
                    for l in liabilities_qs
                ),
                start=Decimal("0"),
            )

            assets_by_category = {}
            for a in assets_qs:
                assets_by_category.setdefault(a.category, Decimal("0"))
                assets_by_category[a.category] += convert_currency(
                    a.amount, a.currency, base_currency, date=today
                )

            liabilities_by_category = {}
            for l in liabilities_qs:
                liabilities_by_category.setdefault(l.category, Decimal("0"))
                liabilities_by_category[l.category] += convert_currency(
                    l.amount, l.currency, base_currency, date=today
                )

        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        net = assets_total - liabilities_total

        # -------------------------
        # Inflación (solo EUR)
        # -------------------------
        inflation_region = "ES"
        inflation_base_period = None
        inflation_error = None

        total_assets_real = None
        total_liabilities_real = None
        net_worth_real = None
        assets_by_category_real = None
        liabilities_by_category_real = None

        if base_currency == "EUR":
            try:
                inflation_base_period = get_latest_inflation_period(inflation_region)
            except ValidationError as e:
                inflation_error = str(e)

        if base_currency == "EUR" and inflation_base_period is not None:
            try:
                total_assets_real = adjust_for_inflation(
                    assets_total,
                    date=today,
                    region=inflation_region,
                    base_period=inflation_base_period,
                )
                total_liabilities_real = adjust_for_inflation(
                    liabilities_total,
                    date=today,
                    region=inflation_region,
                    base_period=inflation_base_period,
                )
                net_worth_real = adjust_for_inflation(
                    net,
                    date=today,
                    region=inflation_region,
                    base_period=inflation_base_period,
                )

                assets_by_category_real = {
                    k: adjust_for_inflation(
                        v,
                        date=today,
                        region=inflation_region,
                        base_period=inflation_base_period,
                    )
                    for k, v in assets_by_category.items()
                }

                liabilities_by_category_real = {
                    k: adjust_for_inflation(
                        v,
                        date=today,
                        region=inflation_region,
                        base_period=inflation_base_period,
                    )
                    for k, v in liabilities_by_category.items()
                }

            except ValidationError as e:
                inflation_error = str(e)

        return Response(
            {
                "base_currency": base_currency,
                "total_assets": str(assets_total),
                "total_liabilities": str(liabilities_total),
                "net_worth": str(net),

                "assets_by_category": {
                    k: str(v) for k, v in assets_by_category.items()
                },
                "liabilities_by_category": {
                    k: str(v) for k, v in liabilities_by_category.items()
                },

                # IPC
                "inflation_region": inflation_region if base_currency == "EUR" else None,
                "inflation_base_period": (
                    str(inflation_base_period) if inflation_base_period else None
                ),
                "inflation_error": inflation_error,

                "total_assets_real": (
                    str(total_assets_real) if total_assets_real is not None else None
                ),
                "total_liabilities_real": (
                    str(total_liabilities_real) if total_liabilities_real is not None else None
                ),
                "net_worth_real": (
                    str(net_worth_real) if net_worth_real is not None else None
                ),

                "assets_by_category_real": (
                    {k: str(v) for k, v in assets_by_category_real.items()}
                    if assets_by_category_real is not None
                    else None
                ),
                "liabilities_by_category_real": (
                    {k: str(v) for k, v in liabilities_by_category_real.items()}
                    if liabilities_by_category_real is not None
                    else None
                ),
            }
        )
