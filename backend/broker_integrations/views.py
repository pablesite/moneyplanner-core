from __future__ import annotations

from datetime import date

from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import exceptions, status
from rest_framework.negotiation import DefaultContentNegotiation, _MediaType, order_by_precedence
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.utils.mediatypes import media_type_matches
from rest_framework.views import APIView

from .csv_importers import (
    import_binance_convert,
    import_binance_recurring,
    import_binance_transactions,
    import_pionex_deposit_withdraw,
    import_pionex_dust,
    import_pionex_futures,
    import_pionex_others,
    import_pionex_staking,
    import_pionex_trading,
)
from .models import (
    BotNetResult,
    BrokerCredential,
    BrokerSyncRun,
    BrokerTrade,
    IncomeEvent,
    ManualCostBasis,
)
from .serializers import (
    BotNetResultSerializer,
    BrokerBotResultListQuerySerializer,
    BrokerCredentialSerializer,
    BrokerCsvImportSerializer,
    BrokerFiscalReportExportQuerySerializer,
    BrokerFiscalReportQuerySerializer,
    BrokerIncomeEventListQuerySerializer,
    BrokerSyncRequestSerializer,
    BrokerSyncRunListQuerySerializer,
    BrokerSyncRunSerializer,
    BrokerTradeListQuerySerializer,
    BrokerTradeSerializer,
    IncomeEventSerializer,
    ManualCostBasisQuerySerializer,
    ManualCostBasisSerializer,
)
from .services.broker_sync import sync_credential
from .services.fiscal_report import generate_fiscal_report
from .services.fiscal_report_export import export_csv, export_pdf


class BrokerPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class IgnoreQueryFormatNegotiation(DefaultContentNegotiation):
    """Avoid DRF taking `?format=` as renderer override for this module endpoints."""

    def select_renderer(self, request, renderers, format_suffix=None):
        format_value = format_suffix
        if format_value:
            renderers = self.filter_renderers(renderers, format_value)

        accepts = self.get_accept_list(request)
        for media_type_set in order_by_precedence(accepts):
            for renderer in renderers:
                for media_type in media_type_set:
                    if media_type_matches(renderer.media_type, media_type):
                        media_type_wrapper = _MediaType(media_type)
                        if (
                            _MediaType(renderer.media_type).precedence
                            > media_type_wrapper.precedence
                        ):
                            full_media_type = ";".join(
                                (renderer.media_type,)
                                + tuple(
                                    f"{key}={value}"
                                    for key, value in media_type_wrapper.params.items()
                                )
                            )
                            return renderer, full_media_type
                        return renderer, media_type
        raise exceptions.NotAcceptable(available_renderers=renderers)


def _start_of_year(year: int):
    return date(year, 1, 1)


def _start_of_next_year(year: int):
    return date(year + 1, 1, 1)


def _paginate(request, queryset, serializer_class):
    paginator = BrokerPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(page, many=True)
    return paginator.get_paginated_response(serializer.data)


def _clean_query_data(**kwargs):
    return {key: value for key, value in kwargs.items() if value is not None}


def _resolve_sync_run_for_user(*, sync_run_id: int, user_id: int) -> BrokerSyncRun:
    return get_object_or_404(
        BrokerSyncRun.objects.select_related("credential"),
        id=sync_run_id,
        credential__user_id=user_id,
    )


def _collect_run_ids(sync_run: BrokerSyncRun, *, model: str) -> list[int]:
    if model == "trade":
        return [*sync_run.new_trade_ids, *sync_run.updated_trade_ids]
    if model == "income_event":
        return [*sync_run.new_income_event_ids, *sync_run.updated_income_event_ids]
    if model == "bot_result":
        return [*sync_run.new_bot_result_ids, *sync_run.updated_bot_result_ids]
    return []


def _resolve_report_ownership(*, user, ownership):
    if ownership is not None:
        if ownership.user_id != user.id:
            return None
        return ownership
    credential = (
        BrokerCredential.objects.filter(user=user)
        .select_related("ownership")
        .order_by("id")
        .first()
    )
    return credential.ownership if credential else None


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


class BrokerSyncRunListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = BrokerSyncRunListQuerySerializer(
            data=_clean_query_data(
                credential_id=request.query_params.get("credential"),
                year=request.query_params.get("year"),
            )
        )
        serializer.is_valid(raise_exception=True)
        queryset = BrokerSyncRun.objects.filter(credential__user=request.user).select_related(
            "credential"
        )
        credential_id = serializer.validated_data.get("credential_id")
        year = serializer.validated_data.get("year")
        if credential_id:
            queryset = queryset.filter(credential_id=credential_id)
        if year:
            queryset = queryset.filter(year=year)
        return _paginate(request, queryset, BrokerSyncRunSerializer)


class BrokerSyncRunDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, sync_run_id: int):
        sync_run = _resolve_sync_run_for_user(sync_run_id=sync_run_id, user_id=request.user.id)
        payload = BrokerSyncRunSerializer(sync_run).data

        trades = BrokerTrade.objects.filter(
            credential__user=request.user,
            id__in=_collect_run_ids(sync_run, model="trade"),
        ).order_by("-timestamp", "-id")
        income_events = IncomeEvent.objects.filter(
            credential__user=request.user,
            id__in=_collect_run_ids(sync_run, model="income_event"),
        ).order_by("-timestamp", "-id")
        bot_results = (
            BotNetResult.objects.filter(
                credential__user=request.user,
                id__in=_collect_run_ids(sync_run, model="bot_result"),
            )
            .annotate(fill_count=Count("fills"))
            .order_by("-period_end", "-id")
        )

        payload["trades"] = _paginate(request, trades, BrokerTradeSerializer).data
        payload["income_events"] = _paginate(request, income_events, IncomeEventSerializer).data
        payload["bot_results"] = _paginate(request, bot_results, BotNetResultSerializer).data
        return Response(payload, status=status.HTTP_200_OK)


class BrokerTradeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = BrokerTradeListQuerySerializer(
            data=_clean_query_data(
                credential_id=request.query_params.get("credential"),
                year=request.query_params.get("year"),
                source=request.query_params.get("source"),
                symbol=request.query_params.get("symbol"),
                side=request.query_params.get("side"),
                bot_id=request.query_params.get("bot_id"),
                sync_run=request.query_params.get("sync_run"),
            )
        )
        serializer.is_valid(raise_exception=True)
        queryset = BrokerTrade.objects.filter(credential__user=request.user).select_related("bot")
        credential_id = serializer.validated_data.get("credential_id")
        year = serializer.validated_data.get("year")
        source = serializer.validated_data.get("source")
        symbol = serializer.validated_data.get("symbol")
        side = serializer.validated_data.get("side")
        bot_id = serializer.validated_data.get("bot_id")
        sync_run_id = serializer.validated_data.get("sync_run")
        if credential_id:
            queryset = queryset.filter(credential_id=credential_id)
        if year:
            queryset = queryset.filter(
                timestamp__date__gte=_start_of_year(year),
                timestamp__date__lt=_start_of_next_year(year),
            )
        if source:
            queryset = queryset.filter(source=source)
        if symbol:
            queryset = queryset.filter(symbol=symbol.upper())
        if side:
            queryset = queryset.filter(side=side)
        if bot_id:
            queryset = queryset.filter(bot__bot_id=bot_id)
        if sync_run_id:
            sync_run = _resolve_sync_run_for_user(sync_run_id=sync_run_id, user_id=request.user.id)
            queryset = queryset.filter(id__in=_collect_run_ids(sync_run, model="trade"))
        queryset = queryset.order_by("-timestamp", "-id")
        return _paginate(request, queryset, BrokerTradeSerializer)


class BrokerIncomeEventListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = BrokerIncomeEventListQuerySerializer(
            data=_clean_query_data(
                credential_id=request.query_params.get("credential"),
                year=request.query_params.get("year"),
                source=request.query_params.get("source"),
                sync_run=request.query_params.get("sync_run"),
            )
        )
        serializer.is_valid(raise_exception=True)
        queryset = IncomeEvent.objects.filter(credential__user=request.user)
        credential_id = serializer.validated_data.get("credential_id")
        year = serializer.validated_data.get("year")
        source = serializer.validated_data.get("source")
        sync_run_id = serializer.validated_data.get("sync_run")
        if credential_id:
            queryset = queryset.filter(credential_id=credential_id)
        if year:
            queryset = queryset.filter(
                timestamp__date__gte=_start_of_year(year),
                timestamp__date__lt=_start_of_next_year(year),
            )
        if source:
            queryset = queryset.filter(source=source)
        if sync_run_id:
            sync_run = _resolve_sync_run_for_user(sync_run_id=sync_run_id, user_id=request.user.id)
            queryset = queryset.filter(id__in=_collect_run_ids(sync_run, model="income_event"))
        queryset = queryset.order_by("-timestamp", "-id")
        return _paginate(request, queryset, IncomeEventSerializer)


class BrokerBotResultListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = BrokerBotResultListQuerySerializer(
            data=_clean_query_data(
                credential_id=request.query_params.get("credential"),
                year=request.query_params.get("year"),
                bot_id=request.query_params.get("bot_id"),
                sync_run=request.query_params.get("sync_run"),
            )
        )
        serializer.is_valid(raise_exception=True)
        queryset = BotNetResult.objects.filter(credential__user=request.user).annotate(
            fill_count=Count("fills")
        )
        credential_id = serializer.validated_data.get("credential_id")
        year = serializer.validated_data.get("year")
        bot_id = serializer.validated_data.get("bot_id")
        sync_run_id = serializer.validated_data.get("sync_run")
        if credential_id:
            queryset = queryset.filter(credential_id=credential_id)
        if year:
            queryset = queryset.filter(
                period_end__date__gte=_start_of_year(year),
                period_end__date__lt=_start_of_next_year(year),
            )
        if bot_id:
            queryset = queryset.filter(bot_id=bot_id)
        if sync_run_id:
            sync_run = _resolve_sync_run_for_user(sync_run_id=sync_run_id, user_id=request.user.id)
            queryset = queryset.filter(id__in=_collect_run_ids(sync_run, model="bot_result"))
        queryset = queryset.order_by("-period_end", "-id")
        return _paginate(request, queryset, BotNetResultSerializer)


class BrokerBotResultDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, bot_result_id: int):
        bot_result = get_object_or_404(
            BotNetResult.objects.filter(credential__user=request.user).annotate(
                fill_count=Count("fills")
            ),
            id=bot_result_id,
        )
        payload = BotNetResultSerializer(bot_result).data
        fills = BrokerTrade.objects.filter(
            credential__user=request.user,
            bot=bot_result,
        ).order_by("-timestamp", "-id")
        payload["fills"] = _paginate(request, fills, BrokerTradeSerializer).data
        return Response(payload, status=status.HTTP_200_OK)


class ManualCostBasisListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ManualCostBasisQuerySerializer(
            data=_clean_query_data(asset=request.query_params.get("asset"))
        )
        serializer.is_valid(raise_exception=True)
        queryset = ManualCostBasis.objects.filter(ownership__user=request.user)
        asset = serializer.validated_data.get("asset")
        if asset:
            queryset = queryset.filter(asset=asset.strip().upper())
        queryset = queryset.order_by("acquired_at", "id")
        return _paginate(request, queryset, ManualCostBasisSerializer)

    def post(self, request):
        serializer = ManualCostBasisSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        row = serializer.save()
        return Response(
            ManualCostBasisSerializer(row).data,
            status=status.HTTP_201_CREATED,
        )


class ManualCostBasisDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, row_id: int):
        row = get_object_or_404(ManualCostBasis, id=row_id, ownership__user=request.user)
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


IMPORTER_BY_TYPE = {
    "pionex_trading": import_pionex_trading,
    "pionex_futures": import_pionex_futures,
    "pionex_staking": import_pionex_staking,
    "pionex_others": import_pionex_others,
    "pionex_dust": import_pionex_dust,
    "pionex_deposit_withdraw": import_pionex_deposit_withdraw,
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
        resolved_ownership = _resolve_report_ownership(user=request.user, ownership=ownership)
        if resolved_ownership is None:
            return Response(
                {"detail": "No hay ownership disponible para generar informe fiscal."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = generate_fiscal_report(ownership=resolved_ownership, year=year)
        return Response(payload, status=status.HTTP_200_OK)


class BrokerFiscalReportExportView(APIView):
    permission_classes = [IsAuthenticated]
    content_negotiation_class = IgnoreQueryFormatNegotiation

    def get(self, request):
        serializer = BrokerFiscalReportExportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        year = serializer.validated_data.get("year") or date.today().year
        ownership = serializer.validated_data.get("ownership")
        if ownership is not None and ownership.user_id != request.user.id:
            return Response(
                {"detail": "La ownership no pertenece al usuario autenticado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        resolved_ownership = _resolve_report_ownership(user=request.user, ownership=ownership)
        if resolved_ownership is None:
            return Response(
                {"detail": "No hay ownership disponible para generar informe fiscal."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report = generate_fiscal_report(ownership=resolved_ownership, year=year)
        fmt = serializer.validated_data.get("format", "csv")
        if fmt == "csv":
            content = export_csv(report)
            return HttpResponse(
                content,
                content_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="fiscal-{year}.csv"'},
            )
        if fmt == "pdf":
            content = export_pdf(report)
            return HttpResponse(
                content,
                content_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="fiscal-{year}.pdf"'},
            )
        return Response(
            {"detail": "unsupported format. use csv or pdf."},
            status=status.HTTP_400_BAD_REQUEST,
        )
