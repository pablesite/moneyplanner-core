from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FxRate, InflationIndex
from .portable_data import (
    get_current_portable_app_version,
    import_portable_bundle_from_request,
)
from .serializers import FxRateSerializer, InflationIndexSerializer


class FxRateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FxRateSerializer
    queryset = FxRate.objects.all().order_by("-rate_date", "from_currency", "to_currency")


class InflationIndexViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InflationIndexSerializer
    queryset = InflationIndex.objects.all().order_by("-period")


class PortableDataMetaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"app_version": get_current_portable_app_version()})


class PortableDataImportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = import_portable_bundle_from_request(
            user=request.user,
            request_data=request.data,
            request=request,
        )
        return Response(result, status=status.HTTP_200_OK)
