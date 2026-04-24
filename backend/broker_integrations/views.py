from __future__ import annotations

from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from .csv_importers import (
    import_binance_convert,
    import_binance_recurring,
    import_binance_transactions,
    import_pionex_dust,
    import_pionex_futures,
    import_pionex_others,
    import_pionex_staking,
    import_pionex_trading,
)
from .models import BrokerCredential
from .serializers import (
    BrokerCredentialSerializer,
    BrokerCsvImportSerializer,
    BrokerFiscalReportQuerySerializer,
    BrokerSyncRequestSerializer,
)
from .services.broker_sync import sync_credential
from .services.fiscal_report import generate_fiscal_report


class BrokerCredentialListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        credentials = BrokerCredential.objects.filter(user=request.user).select_related("ownership")
        serializer = BrokerCredentialSerializer(credentials, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = BrokerCredentialSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        credential = serializer.save()
        response_serializer = BrokerCredentialSerializer(credential)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class BrokerCredentialDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, credential_id: int):
        credential = get_object_or_404(BrokerCredential, id=credential_id, user=request.user)
        credential.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BrokerSyncTriggerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, credential_id: int):
        credential = get_object_or_404(BrokerCredential, id=credential_id, user=request.user)
        serializer = BrokerSyncRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        year = serializer.validated_data.get("year") or date.today().year
        stats_payload = sync_credential(credential=credential, year=year)
        return Response({"year": year, "stats": stats_payload})


class BrokerSyncStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, credential_id: int):
        credential = get_object_or_404(BrokerCredential, id=credential_id, user=request.user)
        stats = credential.last_sync_stats if isinstance(credential.last_sync_stats, dict) else {}
        gaps = credential.last_sync_gaps if isinstance(credential.last_sync_gaps, list) else []
        return Response(
            {
                "last_sync": credential.last_sync_at,
                "stats": stats,
                "gaps_detected": bool(gaps),
                "gaps": gaps,
            }
        )


IMPORTER_BY_TYPE = {
    "pionex_trading": import_pionex_trading,
    "pionex_futures": import_pionex_futures,
    "pionex_staking": import_pionex_staking,
    "pionex_others": import_pionex_others,
    "pionex_dust": import_pionex_dust,
    "binance_transactions": import_binance_transactions,
    "binance_convert": import_binance_convert,
    "binance_recurring": import_binance_recurring,
}


class BrokerCsvImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BrokerCsvImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        importer = IMPORTER_BY_TYPE[serializer.validated_data["file_type"]]
        result = importer(uploaded_file=serializer.validated_data["file"], credential=None)
        return Response(
            {
                "broker": serializer.validated_data["broker"],
                "file_type": serializer.validated_data["file_type"],
                **result,
            },
            status=status.HTTP_200_OK,
        )


class BrokerFiscalReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = BrokerFiscalReportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        year = serializer.validated_data.get("year") or date.today().year
        ownership = serializer.validated_data.get("ownership")
        if ownership is not None and ownership.user_id != request.user.id:
            return Response(
                {"detail": "La ownership no pertenece al usuario autenticado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resolved_ownership = ownership
        if resolved_ownership is None:
            credential = (
                BrokerCredential.objects.filter(user=request.user)
                .select_related("ownership")
                .order_by("id")
                .first()
            )
            resolved_ownership = credential.ownership if credential else None
        if resolved_ownership is None:
            return Response(
                {"detail": "No hay ownership disponible para generar informe fiscal."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = generate_fiscal_report(ownership=resolved_ownership, year=year)
        return Response(payload, status=status.HTTP_200_OK)


# Create your views here.
