from django.db.models import Sum
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import AnnualIncomeEntry, FxRate, InflationIndex
from .serializers import AnnualIncomeEntrySerializer, FxRateSerializer, InflationIndexSerializer


class FxRateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FxRateSerializer
    queryset = FxRate.objects.all().order_by("-rate_date", "from_currency", "to_currency")


class InflationIndexViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InflationIndexSerializer
    queryset = InflationIndex.objects.all().order_by("-period")


class AnnualIncomeEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualIncomeEntrySerializer

    def get_queryset(self):
        return AnnualIncomeEntry.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="totals")
    def totals(self, request):
        queryset = self.get_queryset().filter(is_active=True)
        total_annual = queryset.aggregate(value=Sum("amount_annual"))["value"] or 0
        return Response({"total_annual": str(total_annual), "currency_hint": "mixed"})
