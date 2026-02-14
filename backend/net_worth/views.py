from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import UserSettings
from core.models import InflationIndex
from core.services import adjust_for_inflation, convert_currency

from .models import Asset, Liability, NetWorthSnapshot
from .serializers import (
    AssetSerializer,
    EmptySerializer,
    LiabilitySerializer,
    NetWorthSnapshotSerializer,
)


def _get_base_currency(user) -> str:
    # Ensure user settings exist for users created before this feature.
    UserSettings.objects.get_or_create(user=user)
    return user.settings.base_currency


def _get_inflation_base_period(region: str) -> timezone.datetime.date:
    """
    Return the first available period in DB for the selected region.
    """
    row = InflationIndex.objects.filter(region=region).order_by("period").first()
    if not row:
        raise ValidationError(f"Missing inflation index for region={region}.")
    return row.period


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
        ctx["base_currency"] = _get_base_currency(self.request.user)
        return ctx


class LiabilityViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = LiabilitySerializer
    queryset = Liability.objects.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["base_currency"] = _get_base_currency(self.request.user)
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
        base_currency = _get_base_currency(request.user)

        # Include all active items. Accounting mode is not implemented yet,
        # so it still contributes to totals.
        assets_qs = Asset.objects.filter(user=request.user, is_active=True)
        liabilities_qs = Liability.objects.filter(user=request.user, is_active=True)

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
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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

        # Include all active items. Accounting mode is not implemented yet,
        # so it still contributes to totals.
        assets_qs = Asset.objects.filter(user=request.user, is_active=True)
        liabilities_qs = Liability.objects.filter(user=request.user, is_active=True)

        today = timezone.localdate()

        try:
            assets_total = sum(
                (
                    convert_currency(a.amount, a.currency, base_currency, date=today)
                    for a in assets_qs
                ),
                start=Decimal("0"),
            )
            liabilities_total = Decimal("0")
            liabilities_asset_backed = Decimal("0")
            liabilities_unbacked = Decimal("0")

            for l in liabilities_qs:
                value = convert_currency(l.amount, l.currency, base_currency, date=today)
                liabilities_total += value
                if l.financed_asset_id is not None:
                    liabilities_asset_backed += value
                else:
                    liabilities_unbacked += value

            net = assets_total - liabilities_total

            assets_by_category: dict[str, Decimal] = {}
            assets_by_subcategory: dict[str, Decimal] = {}
            for a in assets_qs:
                assets_by_category.setdefault(a.category, Decimal("0"))
                assets_by_category[a.category] += convert_currency(
                    a.amount, a.currency, base_currency, date=today
                )
                subkey = f"{a.category}:{a.subcategory or 'other'}"
                assets_by_subcategory.setdefault(subkey, Decimal("0"))
                assets_by_subcategory[subkey] += convert_currency(
                    a.amount, a.currency, base_currency, date=today
                )

            liabilities_by_category: dict[str, Decimal] = {}
            for l in liabilities_qs:
                liabilities_by_category.setdefault(l.category, Decimal("0"))
                liabilities_by_category[l.category] += convert_currency(
                    l.amount, l.currency, base_currency, date=today
                )

        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        inflation_region = InflationIndex.Region.ES
        inflation_base_period = None

        total_assets_real = None
        total_liabilities_real = None
        net_worth_real = None
        assets_by_category_real = None
        liabilities_by_category_real = None
        liabilities_asset_backed_real = None
        liabilities_unbacked_real = None

        if base_currency == "EUR":
            try:
                inflation_base_period = _get_inflation_base_period(inflation_region)

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
                    net, date=today, region=inflation_region, base_period=inflation_base_period
                )

                assets_by_category_real = {
                    k: adjust_for_inflation(
                        v, date=today, region=inflation_region, base_period=inflation_base_period
                    )
                    for k, v in assets_by_category.items()
                }
                liabilities_by_category_real = {
                    k: adjust_for_inflation(
                        v, date=today, region=inflation_region, base_period=inflation_base_period
                    )
                    for k, v in liabilities_by_category.items()
                }

                liabilities_asset_backed_real = adjust_for_inflation(
                    liabilities_asset_backed,
                    date=today,
                    region=inflation_region,
                    base_period=inflation_base_period,
                )
                liabilities_unbacked_real = adjust_for_inflation(
                    liabilities_unbacked,
                    date=today,
                    region=inflation_region,
                    base_period=inflation_base_period,
                )

            except ValidationError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "base_currency": base_currency,
                "total_assets": str(assets_total),
                "total_liabilities": str(liabilities_total),
                "net_worth": str(net),
                "assets_by_category": {k: str(v) for k, v in assets_by_category.items()},
                "assets_by_subcategory": {k: str(v) for k, v in assets_by_subcategory.items()},
                "liabilities_by_category": {k: str(v) for k, v in liabilities_by_category.items()},
                "inflation_region": inflation_region if base_currency == "EUR" else None,
                "inflation_base_period": str(inflation_base_period)
                if inflation_base_period
                else None,
                "total_assets_real": str(total_assets_real)
                if total_assets_real is not None
                else None,
                "total_liabilities_real": str(total_liabilities_real)
                if total_liabilities_real is not None
                else None,
                "net_worth_real": str(net_worth_real) if net_worth_real is not None else None,
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
                "liabilities_asset_backed": str(liabilities_asset_backed),
                "liabilities_unbacked": str(liabilities_unbacked),
                "liabilities_asset_backed_real": str(liabilities_asset_backed_real)
                if liabilities_asset_backed_real is not None
                else None,
                "liabilities_unbacked_real": str(liabilities_unbacked_real)
                if liabilities_unbacked_real is not None
                else None,
            }
        )
