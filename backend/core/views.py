from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import FxRate, InflationIndex
from .serializers import FxRateSerializer, InflationIndexSerializer


class FxRateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FxRateSerializer
    queryset = FxRate.objects.all().order_by("-rate_date", "from_currency", "to_currency")


class InflationIndexViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InflationIndexSerializer
    queryset = InflationIndex.objects.all().order_by("-period")

# Create your views here.
