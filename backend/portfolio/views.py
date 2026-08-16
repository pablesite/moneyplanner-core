from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.utils.dateparse import parse_date

from core.market_data import MarketDataSyncError

from .models import (
    ContainerCashAccount,
    Instrument,
    InstrumentPrice,
    InstrumentProviderMapping,
    InvestmentContainer,
    Portfolio,
    PortfolioMigrationIssue,
    PortfolioPosition,
    PositionValuation,
    PositionOwnershipPeriod,
)
from .serializers import (
    ContainerCashAccountSerializer,
    InstrumentSerializer,
    InstrumentPriceSerializer,
    InstrumentProviderMappingSerializer,
    InvestmentContainerSerializer,
    PortfolioMigrationIssueSerializer,
    PortfolioPositionSerializer,
    PortfolioSerializer,
    PositionOwnershipPeriodSerializer,
    PositionValuationSerializer,
)
from .market_data import refresh_confirmed_mapping
from .performance import (
    build_portfolio_overview,
    build_portfolio_performance,
    build_portfolio_positions,
    build_portfolio_quality,
    build_portfolio_timeline,
    default_performance_period,
    timeline_dates,
)
from .services import bootstrap_portfolio_for_user, build_portfolio_readiness
from .valuations import build_valuation_health, resolve_position_valuation


class PortfolioViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PortfolioSerializer

    def get_queryset(self):
        return Portfolio.objects.filter(user=self.request.user)

    def perform_create(self, serializer) -> None:
        if Portfolio.objects.filter(user=self.request.user).exists():
            raise ValidationError({"detail": "El usuario ya tiene una cartera global."})
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance: Portfolio) -> None:
        raise ValidationError({"detail": "La cartera global no se puede eliminar."})


class InvestmentContainerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InvestmentContainerSerializer

    def get_queryset(self):
        return InvestmentContainer.objects.filter(portfolio__user=self.request.user)


class ContainerCashAccountViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ContainerCashAccountSerializer

    def get_queryset(self):
        return ContainerCashAccount.objects.filter(
            container__portfolio__user=self.request.user
        ).select_related("container", "container__portfolio", "ledger_account")


class InstrumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InstrumentSerializer

    def get_queryset(self):
        if self.action == "refresh":
            return Instrument.objects.filter(
                Q(user=self.request.user) | Q(positions__portfolio__user=self.request.user)
            ).distinct()
        if self.action in {"list", "retrieve"}:
            return Instrument.objects.filter(Q(user=self.request.user) | Q(user__isnull=True))
        return Instrument.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="refresh")
    def refresh(self, request, pk=None):
        instrument = self.get_object()
        mappings = list(instrument.provider_mappings.filter(is_confirmed=True))
        if not mappings:
            raise ValidationError({"detail": "El instrumento no tiene un mapeo confirmado."})
        inserted = 0
        try:
            for mapping in mappings:
                inserted += refresh_confirmed_mapping(mapping=mapping)
        except MarketDataSyncError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"instrument_id": instrument.id, "rows_upserted": inserted})


class InstrumentProviderMappingViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InstrumentProviderMappingSerializer

    def get_queryset(self):
        return InstrumentProviderMapping.objects.filter(
            instrument__user=self.request.user
        ).select_related("instrument")


class InstrumentPriceViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InstrumentPriceSerializer

    def get_queryset(self):
        return InstrumentPrice.objects.filter(
            Q(instrument__user=self.request.user)
            | Q(instrument__positions__portfolio__user=self.request.user)
        ).distinct()


class PortfolioPositionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PortfolioPositionSerializer

    def get_queryset(self):
        return (
            PortfolioPosition.objects.filter(portfolio__user=self.request.user)
            .select_related("portfolio", "container", "instrument", "asset", "ledger_account")
            .prefetch_related("ownership_periods__shares")
        )

    def perform_destroy(self, instance: PortfolioPosition) -> None:
        instance.status = PortfolioPosition.Status.ARCHIVED
        instance.save(update_fields=["status", "updated_at"])

    @action(detail=True, methods=["get"], url_path="valuation")
    def valuation(self, request, pk=None):
        return Response(resolve_position_valuation(position=self.get_object()))

    @action(detail=False, methods=["get"], url_path="performance")
    def performance(self, request):
        portfolio, start_date, end_date, member_id = _performance_request(request)
        return Response(
            {
                "period": {"from": start_date.isoformat(), "to": end_date.isoformat()},
                "member_id": member_id,
                "results": build_portfolio_positions(
                    portfolio=portfolio,
                    start_date=start_date,
                    end_date=end_date,
                    member_id=member_id,
                ),
            }
        )


class PositionValuationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PositionValuationSerializer

    def get_queryset(self):
        return PositionValuation.objects.filter(
            position__portfolio__user=self.request.user
        ).select_related("position", "position__portfolio", "legacy_asset_valuation")

    def perform_destroy(self, instance: PositionValuation) -> None:
        if instance.source != PositionValuation.Source.MANUAL:
            raise ValidationError({"detail": "Las valoraciones legacy son de solo lectura."})
        instance.delete()


class PositionOwnershipPeriodViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = PositionOwnershipPeriodSerializer

    def get_queryset(self):
        return (
            PositionOwnershipPeriod.objects.filter(position__portfolio__user=self.request.user)
            .select_related("position", "position__portfolio", "ownership")
            .prefetch_related("shares__member")
        )


class PortfolioMigrationIssueViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PortfolioMigrationIssueSerializer

    def get_queryset(self):
        return PortfolioMigrationIssue.objects.filter(portfolio__user=self.request.user)


class PortfolioBootstrapView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = bootstrap_portfolio_for_user(user=request.user)
        return Response(
            {
                "portfolio_id": result.portfolio_id,
                "created_positions": result.created_positions,
                "existing_positions": result.existing_positions,
                "open_issues": result.open_issues,
            },
            status=status.HTTP_200_OK,
        )


class PortfolioReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(build_portfolio_readiness(user=request.user))


class PortfolioValuationHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(build_valuation_health(user=request.user))


def _performance_request(request):
    try:
        portfolio = Portfolio.objects.get(user=request.user)
    except Portfolio.DoesNotExist as exc:
        raise ValidationError({"detail": "La cartera todavía no existe."}) from exc
    default_from, default_to = default_performance_period(portfolio)
    raw_from = request.query_params.get("date_from")
    raw_to = request.query_params.get("date_to")
    start_date = parse_date(raw_from) if raw_from else default_from
    end_date = parse_date(raw_to) if raw_to else default_to
    if start_date is None or end_date is None:
        raise ValidationError({"detail": "Usa date_from/date_to con formato YYYY-MM-DD."})
    timeline_dates(start_date, end_date)
    raw_member_id = request.query_params.get("member_id")
    try:
        member_id = int(raw_member_id) if raw_member_id else None
    except ValueError as exc:
        raise ValidationError({"member_id": "Debe ser un entero positivo."}) from exc
    if member_id is not None and member_id < 1:
        raise ValidationError({"member_id": "Debe ser un entero positivo."})
    if member_id is not None and not request.user.family_members.filter(id=member_id).exists():
        raise ValidationError({"member_id": "El miembro no pertenece al usuario."})
    return portfolio, start_date, end_date, member_id


class PortfolioOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio, start_date, end_date, member_id = _performance_request(request)
        return Response(
            build_portfolio_overview(
                portfolio=portfolio,
                start_date=start_date,
                end_date=end_date,
                member_id=member_id,
            )
        )


class PortfolioTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio, start_date, end_date, member_id = _performance_request(request)
        return Response(
            {
                "period": {"from": start_date.isoformat(), "to": end_date.isoformat()},
                "member_id": member_id,
                "currency": portfolio.base_currency,
                "results": build_portfolio_timeline(
                    portfolio=portfolio,
                    start_date=start_date,
                    end_date=end_date,
                    member_id=member_id,
                ),
            }
        )


class PortfolioPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio, start_date, end_date, member_id = _performance_request(request)
        return Response(
            build_portfolio_performance(
                portfolio=portfolio,
                start_date=start_date,
                end_date=end_date,
                member_id=member_id,
            )
        )


class PortfolioQualityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio, start_date, end_date, member_id = _performance_request(request)
        return Response(
            build_portfolio_quality(
                portfolio=portfolio,
                start_date=start_date,
                end_date=end_date,
                member_id=member_id,
            )
        )
