from django.shortcuts import render

# Create your views here.
from decimal import Decimal
from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response

from rest_framework.permissions import IsAuthenticated

from .models import Asset, Liability, NetWorthSnapshot
from .serializers import AssetSerializer, LiabilitySerializer, NetWorthSnapshotSerializer


class UserScopedQuerySetMixin:
    """
    Restringe queryset al usuario autenticado.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(user=self.request.user)


class AssetViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = AssetSerializer
    queryset = Asset.objects.all()


class LiabilityViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = LiabilitySerializer
    queryset = Liability.objects.all()


class NetWorthSnapshotViewSet(UserScopedQuerySetMixin, viewsets.ModelViewSet):
    serializer_class = NetWorthSnapshotSerializer
    queryset = NetWorthSnapshot.objects.all()


class NetWorthSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assets_total = Asset.objects.filter(user=request.user).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        liabilities_total = Liability.objects.filter(user=request.user).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        net = assets_total - liabilities_total

        return Response(
            {
                "total_assets": str(assets_total),
                "total_liabilities": str(liabilities_total),
                "net_worth": str(net),
            }
        )