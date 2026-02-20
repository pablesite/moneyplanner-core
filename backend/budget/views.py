from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AnnualIncomeEntry
from .serializers import AnnualIncomeEntrySerializer


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
