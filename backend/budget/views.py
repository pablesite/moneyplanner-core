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
        return AnnualIncomeEntry.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="totals")
    def totals(self, request):
        queryset = self.get_queryset().filter(is_active=True)
        total_annual = queryset.aggregate(value=Sum("amount_annual"))["value"] or 0
        return Response({"total_annual": str(total_annual), "currency_hint": "mixed"})
