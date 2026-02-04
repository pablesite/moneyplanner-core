from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Asset, Liability, NetWorthSnapshot, FamilyMember, Ownership
from .serializers import (
    AssetSerializer,
    LiabilitySerializer,
    NetWorthSnapshotSerializer,
    EmptySerializer,
    FamilyMemberSerializer,
    OwnershipWriteSerializer,
    OwnershipReadSerializer, 
)

from accounts.models import UserSettings
from core.services import convert_currency, adjust_for_inflation
from core.models import InflationIndex  # ajusta el import si InflationIndex vive en otro sitio


def _get_base_currency(user) -> str:
    # Robusto: si no existe settings (usuarios creados antes), lo crea.
    UserSettings.objects.get_or_create(user=user)
    return user.settings.base_currency


def _get_inflation_base_period(region: str) -> timezone.datetime.date:
    """
    Devuelve el primer mes (period) disponible en BD para esa región.
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
                (convert_currency(a.amount, a.currency, base_currency, date=snapshot_date) for a in assets_qs),
                start=Decimal("0"),
            )
            liabilities_total = sum(
                (convert_currency(l.amount, l.currency, base_currency, date=snapshot_date) for l in liabilities_qs),
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

        today = timezone.localdate()

        try:
            # Totales nominales en moneda base
            assets_total = sum(
                (convert_currency(a.amount, a.currency, base_currency, date=today) for a in assets_qs),
                start=Decimal("0"),
            )
            liabilities_total = Decimal("0")
            liabilities_asset_backed = Decimal("0")
            liabilities_unbacked = Decimal("0")

            for l in liabilities_qs:
                v = convert_currency(l.amount, l.currency, base_currency, date=today)
                liabilities_total += v
                if l.financed_asset_id is not None:
                    liabilities_asset_backed += v
                else:
                    liabilities_unbacked += v

            net = assets_total - liabilities_total


            # Breakdown nominal por categoría en moneda base
            assets_by_category: dict[str, Decimal] = {}
            for a in assets_qs:
                assets_by_category.setdefault(a.category, Decimal("0"))
                assets_by_category[a.category] += convert_currency(a.amount, a.currency, base_currency, date=today)

            liabilities_by_category: dict[str, Decimal] = {}
            for l in liabilities_qs:
                liabilities_by_category.setdefault(l.category, Decimal("0"))
                liabilities_by_category[l.category] += convert_currency(l.amount, l.currency, base_currency, date=today)

        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # IPC (solo si base_currency=EUR)
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
                # Base = primer dato disponible en BD
                inflation_base_period = _get_inflation_base_period(inflation_region)

                # Interpretación: "valor de HOY expresado en euros del mes base"
                total_assets_real = adjust_for_inflation(
                    assets_total, date=today, region=inflation_region, base_period=inflation_base_period
                )
                total_liabilities_real = adjust_for_inflation(
                    liabilities_total, date=today, region=inflation_region, base_period=inflation_base_period
                )
                net_worth_real = adjust_for_inflation(
                    net, date=today, region=inflation_region, base_period=inflation_base_period
                )

                assets_by_category_real = {
                    k: adjust_for_inflation(v, date=today, region=inflation_region, base_period=inflation_base_period)
                    for k, v in assets_by_category.items()
                }
                liabilities_by_category_real = {
                    k: adjust_for_inflation(v, date=today, region=inflation_region, base_period=inflation_base_period)
                    for k, v in liabilities_by_category.items()
                }

                liabilities_asset_backed_real = adjust_for_inflation(
                    liabilities_asset_backed, date=today, region=inflation_region, base_period=inflation_base_period
                )
                liabilities_unbacked_real = adjust_for_inflation(
                    liabilities_unbacked, date=today, region=inflation_region, base_period=inflation_base_period
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
                "liabilities_by_category": {k: str(v) for k, v in liabilities_by_category.items()},
                "inflation_region": inflation_region if base_currency == "EUR" else None,
                "inflation_base_period": str(inflation_base_period) if inflation_base_period else None,
                "total_assets_real": str(total_assets_real) if total_assets_real is not None else None,
                "total_liabilities_real": str(total_liabilities_real) if total_liabilities_real is not None else None,
                "net_worth_real": str(net_worth_real) if net_worth_real is not None else None,
                "assets_by_category_real": (
                    {k: str(v) for k, v in assets_by_category_real.items()} if assets_by_category_real is not None else None
                ),
                "liabilities_by_category_real": (
                    {k: str(v) for k, v in liabilities_by_category_real.items()} if liabilities_by_category_real is not None else None
                ),
                "liabilities_asset_backed": str(liabilities_asset_backed),
                "liabilities_unbacked": str(liabilities_unbacked),
                "liabilities_asset_backed_real": str(liabilities_asset_backed_real) if liabilities_asset_backed_real is not None else None,
                "liabilities_unbacked_real": str(liabilities_unbacked_real) if liabilities_unbacked_real is not None else None,

            }
        )


class FamilyMemberViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = FamilyMemberSerializer
    permission_classes = [IsAuthenticated]
    queryset = FamilyMember.objects.all()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class OwnershipViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Ownership.objects.all()

    def get_queryset(self):
        # UserScopedQuerySetMixin filtra por user, pero aquí además optimizamos lectura de splits+member
        qs = super().get_queryset()
        return qs.select_related("member").prefetch_related("splits", "splits__member")

    def get_serializer_class(self):
        # Lectura bonita
        if self.action in ("list", "retrieve"):
            return OwnershipReadSerializer
        # Escritura/validación
        return OwnershipWriteSerializer


class NetWorthByMemberSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        base_currency = _get_base_currency(request.user)
        today = timezone.localdate()

        members = list(
            FamilyMember.objects.filter(user=request.user, is_active=True).only("id", "name", "role")
        )
        member_map = {m.id: {"id": m.id, "name": m.name, "role": m.role} for m in members}

        # buckets
        assets_by_member = {m.id: Decimal("0") for m in members}
        liabilities_by_member = {m.id: Decimal("0") for m in members}
        unassigned_assets = Decimal("0")
        unassigned_liabilities = Decimal("0")

        # precargar ownerships para no hacer N+1
        assets_qs = (
            Asset.objects.filter(user=request.user, is_active=True, tracking_mode=Asset.TrackingMode.MANUAL)
            .select_related("ownership", "ownership__member")
            .prefetch_related("ownership__splits", "ownership__splits__member")
        )
        liabilities_qs = (
            Liability.objects.filter(user=request.user, is_active=True, tracking_mode=Liability.TrackingMode.MANUAL)
            .select_related("ownership", "ownership__member")
            .prefetch_related("ownership__splits", "ownership__splits__member")
        )

        def allocate_amount(amount_base: Decimal, ownership: Ownership | None, is_asset: bool):
            nonlocal unassigned_assets, unassigned_liabilities

            if ownership is None:
                if is_asset:
                    unassigned_assets += amount_base
                else:
                    unassigned_liabilities += amount_base
                return

            if ownership.kind == Ownership.Kind.INDIVIDUAL:
                if ownership.member_id is None:
                    # inconsistente con constraint, pero por seguridad
                    if is_asset:
                        unassigned_assets += amount_base
                    else:
                        unassigned_liabilities += amount_base
                    return
                if is_asset:
                    assets_by_member[ownership.member_id] += amount_base
                else:
                    liabilities_by_member[ownership.member_id] += amount_base
                return

            if ownership.kind == Ownership.Kind.SHARED:
                splits = list(ownership.splits.all())
                if not splits:
                    # shared sin splits => lo tratamos como unassigned
                    if is_asset:
                        unassigned_assets += amount_base
                    else:
                        unassigned_liabilities += amount_base
                    return

                for s in splits:
                    portion = (amount_base * Decimal(str(s.percent))) / Decimal("100")
                    if is_asset:
                        assets_by_member[s.member_id] += portion
                    else:
                        liabilities_by_member[s.member_id] += portion
                return

            # kind desconocido
            if is_asset:
                unassigned_assets += amount_base
            else:
                unassigned_liabilities += amount_base

        # assets
        try:
            for a in assets_qs:
                amt = convert_currency(a.amount, a.currency, base_currency, date=today)
                allocate_amount(amt, a.ownership, is_asset=True)

            for l in liabilities_qs:
                amt = convert_currency(l.amount, l.currency, base_currency, date=today)
                allocate_amount(amt, l.ownership, is_asset=False)

        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # construir salida
        rows = []
        for m in members:
            a = assets_by_member[m.id]
            d = liabilities_by_member[m.id]
            rows.append(
                {
                    "member": member_map[m.id],
                    "total_assets": str(a),
                    "total_liabilities": str(d),
                    "net_worth": str(a - d),
                }
            )

        total_assets = sum(assets_by_member.values(), start=Decimal("0")) + unassigned_assets
        total_liabilities = sum(liabilities_by_member.values(), start=Decimal("0")) + unassigned_liabilities

        return Response(
            {
                "base_currency": base_currency,
                "totals": {
                    "total_assets": str(total_assets),
                    "total_liabilities": str(total_liabilities),
                    "net_worth": str(total_assets - total_liabilities),
                },
                "by_member": rows,
                "unassigned": {
                    "assets": str(unassigned_assets),
                    "liabilities": str(unassigned_liabilities),
                    "net_worth": str(unassigned_assets - unassigned_liabilities),
                },
            }
        )
