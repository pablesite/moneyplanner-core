from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AnnualExpenseEntry, AnnualIncomeEntry
from .serializers import AnnualExpenseEntrySerializer, AnnualIncomeEntrySerializer


class AnnualIncomeEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualIncomeEntrySerializer

    def get_queryset(self):
        queryset = AnnualIncomeEntry.objects.filter(user=self.request.user)
        year_param = (self.request.query_params.get("year") or "").strip()
        if year_param:
            try:
                year = int(year_param)
            except ValueError:
                year = None
            if year is not None:
                queryset = queryset.filter(fiscal_year=year)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="totals")
    def totals(self, request):
        queryset = self.get_queryset().filter(is_active=True)
        total_annual = queryset.aggregate(value=Sum("amount_annual"))["value"] or 0
        return Response({"total_annual": str(total_annual), "currency_hint": "mixed"})


class AnnualExpenseEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = AnnualExpenseEntrySerializer

    def get_queryset(self):
        queryset = AnnualExpenseEntry.objects.filter(user=self.request.user)
        year_param = (self.request.query_params.get("year") or "").strip()
        source_liability_param = (self.request.query_params.get("source_liability_id") or "").strip()
        if year_param:
            try:
                year = int(year_param)
            except ValueError:
                year = None
            if year is not None:
                queryset = queryset.filter(fiscal_year=year)
        if source_liability_param:
            try:
                source_liability_id = int(source_liability_param)
            except ValueError:
                source_liability_id = None
            if source_liability_id is not None:
                queryset = queryset.filter(source_liability_id=source_liability_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="totals")
    def totals(self, request):
        queryset = self.get_queryset().filter(is_active=True)
        total_annual = queryset.aggregate(value=Sum("amount_annual"))["value"] or 0
        return Response({"total_annual": str(total_annual), "currency_hint": "mixed"})
