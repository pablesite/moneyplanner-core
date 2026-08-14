import os
import subprocess
import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .market_data import MarketDataSyncError, get_market_data_status, sync_market_data
from .models import FxRate, InflationIndex
from .portable_data import (
    get_current_portable_app_version,
    import_portable_bundle_from_request,
)
from .serializers import FxRateSerializer, InflationIndexSerializer
from .services import convert_currency_detailed, refresh_currency_rate


class _MarketDataPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


def _pg_env() -> dict[str, str]:
    db = settings.DATABASES["default"]
    env = os.environ.copy()
    env["PGHOST"] = db.get("HOST", "db")
    env["PGPORT"] = str(db.get("PORT", "5432"))
    env["PGDATABASE"] = db["NAME"]
    env["PGUSER"] = db["USER"]
    env["PGPASSWORD"] = db.get("PASSWORD", "")
    return env


class _IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)


class FxRateViewSet(viewsets.ModelViewSet):
    permission_classes = [_IsAdminOrReadOnly]
    serializer_class = FxRateSerializer
    queryset = FxRate.objects.all().order_by("-rate_date", "from_currency", "to_currency")
    pagination_class = _MarketDataPagination


class InflationIndexViewSet(viewsets.ModelViewSet):
    permission_classes = [_IsAdminOrReadOnly]
    serializer_class = InflationIndexSerializer
    queryset = InflationIndex.objects.all().order_by("-period", "region")
    pagination_class = _MarketDataPagination


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


class MarketDataStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_market_data_status())


class MarketDataSyncAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        datasets = request.data.get("datasets") or ["inflation"]
        mode = request.data.get("mode") or "reconcile"
        fx_full_history = bool(request.data.get("fx_full_history"))
        fx_history_floor_years = None if fx_full_history else 5
        try:
            summary = sync_market_data(
                datasets=datasets,
                mode=mode,
                fx_history_floor_years=fx_history_floor_years,
            )
        except MarketDataSyncError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"summary": summary}, status=status.HTTP_200_OK)


class FxConvertAPIView(APIView):
    """Convierte un importe entre divisas usando los FxRate diarios.

    Query params: amount, from, to, date (ISO, opcional → hoy).
    Devuelve el importe convertido a precisión de cripto/fiat y cómo se resolvió
    el tipo (exact/synced/fallback), para que el cliente pueda avisar al usuario.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        amount_raw = params.get("amount")
        from_currency = params.get("from")
        to_currency = params.get("to")
        date_raw = params.get("date")

        if not amount_raw or not from_currency or not to_currency:
            raise ValidationError("amount, from y to son obligatorios.")
        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, ValueError):
            raise ValidationError("amount no es un número válido.")
        on_date: date | None = None
        if date_raw:
            try:
                on_date = date.fromisoformat(date_raw)
            except ValueError:
                raise ValidationError("date debe ser una fecha ISO (YYYY-MM-DD).")

        try:
            result = convert_currency_detailed(amount, from_currency, to_currency, on_date=on_date)
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message", None) or str(exc))

        return Response(
            {
                "amount": str(result.amount),
                "from_currency": result.from_currency,
                "to_currency": result.to_currency,
                "converted": str(result.converted),
                "rate": str(result.rate),
                "rate_date": result.rate_date.isoformat() if result.rate_date else None,
                "resolution": result.resolution,
                "requested_date": (on_date or date.today()).isoformat(),
            }
        )


class FxRefreshAPIView(APIView):
    """Refresh one current FX pair for an authenticated portfolio owner."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from_currency = request.data.get("from")
        to_currency = request.data.get("to")
        if not from_currency or not to_currency:
            raise ValidationError("from y to son obligatorios.")
        try:
            result = refresh_currency_rate(from_currency, to_currency)
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message", None) or str(exc))
        return Response(
            {
                "from_currency": result.from_currency,
                "to_currency": result.to_currency,
                "rate": str(result.rate),
                "rate_date": result.rate_date.isoformat() if result.rate_date else None,
                "resolution": result.resolution,
                "requested_date": timezone.localdate().isoformat(),
            }
        )


class DbBackupView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        env = _pg_env()
        filename = f"the_arkenstone_backup_{date.today().isoformat()}.dump"

        proc = subprocess.Popen(
            ["pg_dump", "-Fc", "--no-owner", "--no-privileges"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        def stream():
            assert proc.stdout is not None
            for chunk in iter(lambda: proc.stdout.read(65536), b""):
                yield chunk
            proc.wait()

        response = StreamingHttpResponse(stream(), content_type="application/octet-stream")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class DbRestoreView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser]

    def post(self, request):
        dump_file = request.FILES.get("file")
        if not dump_file:
            raise ValidationError({"file": "Se requiere un archivo .dump."})

        env = _pg_env()

        with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as tmp:
            for chunk in dump_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [
                    "pg_restore",
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--no-privileges",
                    f"--dbname={env['PGDATABASE']}",
                    tmp_path,
                ],
                capture_output=True,
                env=env,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace")
                raise ValidationError({"detail": f"pg_restore falló: {stderr[:500]}"})
        finally:
            os.unlink(tmp_path)

        return Response({"ok": True}, status=status.HTTP_200_OK)
