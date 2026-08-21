from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction as db_transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from memberships.models import Ownership

from core.market_data import MarketDataSyncError

from .benchmark import build_portfolio_benchmark, build_portfolio_risk
from .decisions import build_decision_log
from .exposure import build_exposure
from .allocation import (
    build_allocation,
    build_cash_value,
    build_scopes,
    build_contribution,
    confirm_basket,
    create_basket,
    discard_basket,
)
from .models import (
    AllocationStrategy,
    ContainerCashAccount,
    ContributionBasket,
    ContributionCommitment,
    PositionAllocationRule,
    PositionExposure,
    Instrument,
    InstrumentPrice,
    InstrumentProviderMapping,
    InvestmentContainer,
    Portfolio,
    PortfolioMigrationIssue,
    PositionClassBreakdown,
    PortfolioImportBatch,
    PortfolioPosition,
    PositionValuation,
    PositionOwnershipPeriod,
)
from .serializers import (
    AllocationStrategySerializer,
    ContainerCashAccountSerializer,
    ContributionBasketSerializer,
    ContributionCommitmentSerializer,
    PositionAllocationRuleSerializer,
    PositionExposureSerializer,
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
    build_holding_threads,
    build_portfolio_overview,
    build_portfolio_performance,
    build_portfolio_positions,
    build_portfolio_quality,
    build_portfolio_timeline,
    default_performance_period,
    load_performance_context,
    timeline_context_start,
    timeline_dates,
)
from .services import (
    bootstrap_portfolio_for_user,
    build_portfolio_readiness,
    discover_missing_positions,
)
from .valuations import (
    build_valuation_health,
    resolve_position_valuation,
    sync_ledger_valuations,
)
from .imports import confirm_import, preview_import, serialize_batch, upload_csv
from .operations import confirm_operation, operation_options, preview_operation


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

    def perform_destroy(self, instance: ContainerCashAccount) -> None:
        # Una cesta guardada apunta a este efectivo, asi que borrarlo dejaria la
        # propuesta hablando de algo que ya no existe. Antes salia como un 500 sin
        # mensaje y el usuario se quedaba sin saber que hacer: cambiar la cuenta del
        # contenedor resuelve el caso real, que es mudar el efectivo de plataforma.
        try:
            instance.delete()
        except ProtectedError as exc:
            baskets = sorted(
                {
                    line.basket.booking_date.isoformat()
                    for line in instance.basket_lines.select_related("basket")
                }
            )
            raise ValidationError(
                {
                    "detail": (
                        "Este efectivo aparece en cestas ya guardadas ("
                        + ", ".join(baskets)
                        + "), asi que desenlazarlo dejaria esas propuestas sin destino. "
                        "Si has movido el dinero a otra plataforma, cambia la cuenta del "
                        "contenedor en vez de desenlazarla."
                    )
                }
            ) from exc


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
        from django.utils import timezone

        instance.closed_on = timezone.localdate()
        instance.asset.is_active = False
        instance.asset.save(update_fields=["is_active", "updated_at"])
        instance.save(update_fields=["status", "closed_on", "updated_at"])

    @action(detail=True, methods=["post"], url_path="archive")
    def archive(self, request, pk=None):
        position = self.get_object()
        self.perform_destroy(position)
        return Response(self.get_serializer(position).data)

    @action(detail=True, methods=["post"], url_path="reopen")
    def reopen(self, request, pk=None):
        position = self.get_object()
        position.status = PortfolioPosition.Status.ACTIVE
        position.closed_on = None
        position.asset.is_active = True
        position.asset.save(update_fields=["is_active", "updated_at"])
        position.save(update_fields=["status", "closed_on", "updated_at"])
        return Response(self.get_serializer(position).data)

    @action(detail=True, methods=["post"], url_path="confirm-setup")
    def confirm_setup(self, request, pk=None):
        from django.utils import timezone

        position = self.get_object()
        data = {
            "tracking_style": request.data.get("tracking_style", position.tracking_style),
            "history_mode": request.data.get("history_mode", position.history_mode),
            "history_start_date": request.data.get("history_start_date"),
        }
        # Container and asset class describe what the position *is*, and until now the
        # bootstrap's guess could not be corrected from the UI at all: every migrated
        # position stayed in "Inversiones legacy" and most in the "Otros" class, which
        # left the composition chart saying nothing.
        if request.data.get("container_id"):
            data["container_id"] = request.data["container_id"]
        serializer = self.get_serializer(position, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(setup_confirmed_at=timezone.now())
        asset_class = str(request.data.get("asset_class") or "").strip()
        if asset_class:
            self._reclassify(position=position, asset_class=asset_class)
            serializer = self.get_serializer(self.get_object())
        if "class_breakdown" in request.data:
            self._set_class_breakdown(position=position, rows=request.data["class_breakdown"])
            serializer = self.get_serializer(self.get_object())
        return Response(serializer.data)

    @staticmethod
    def _set_class_breakdown(*, position: PortfolioPosition, rows) -> None:
        """Reemplaza el reparto interno de la posición, o lo borra si llega vacío.

        Una cartera de roboadvisor no es de una sola clase: contarla entera en la
        dominante desplaza la composición tanto como pese. Se valida que sume 100 porque
        un reparto parcial haría desaparecer valor del gráfico sin avisar.
        """
        if not isinstance(rows, list):
            raise ValidationError({"class_breakdown": "Debe ser una lista."})
        parsed: list[tuple[str, Decimal]] = []
        for row in rows:
            asset_class = str((row or {}).get("asset_class") or "").strip()
            if asset_class not in Instrument.AssetClass.values:
                raise ValidationError({"class_breakdown": "Clase de activo no válida."})
            try:
                percent = Decimal(str((row or {}).get("percent")))
            except (InvalidOperation, TypeError):
                raise ValidationError({"class_breakdown": "Porcentaje no válido."}) from None
            if percent <= 0 or percent > 100:
                raise ValidationError({"class_breakdown": "Cada porcentaje va entre 0 y 100."})
            parsed.append((asset_class, percent))
        if len({asset_class for asset_class, _ in parsed}) != len(parsed):
            raise ValidationError({"class_breakdown": "No se puede repetir una clase."})
        if parsed and sum(percent for _, percent in parsed) != Decimal("100"):
            raise ValidationError({"class_breakdown": "El reparto debe sumar 100%."})
        with db_transaction.atomic():
            position.class_breakdown.all().delete()
            PositionClassBreakdown.objects.bulk_create(
                [
                    PositionClassBreakdown(
                        position=position, asset_class=asset_class, percent=percent
                    )
                    for asset_class, percent in parsed
                ]
            )

    @staticmethod
    def _reclassify(*, position: PortfolioPosition, asset_class: str) -> None:
        """Record the class on the position, not on the instrument.

        Canonical instruments are shared across portfolios, so writing the class there
        would reclassify someone else's positions — which is why crypto could not be
        classified at all. Storing the choice on the position lets every position be
        classified and leaves the instrument's own class as the default.
        """
        if asset_class not in Instrument.AssetClass.values:
            raise ValidationError({"asset_class": "Clase de activo no válida."})
        if position.asset_class_override == asset_class:
            return
        position.asset_class_override = asset_class
        position.save(update_fields=["asset_class_override", "updated_at"])

    @action(detail=True, methods=["get"], url_path="valuation")
    def valuation(self, request, pk=None):
        return Response(resolve_position_valuation(position=self.get_object()))

    @action(detail=False, methods=["post"], url_path="resync-valuations")
    def resync_valuations(self, request):
        """Pull into the portfolio whatever the rest of the app already knows.

        Revaluations booked through the app sync themselves on commit, but data that
        reaches the database underneath the ORM (a restore, a bulk load) fires no signal
        and leaves positions frozen. This is the explicit way out of that drift.

        It also picks up investment assets created in Patrimonio that never became a
        position. That used to require re-running the bootstrap, which nothing in the UI
        did, so an asset with its movements already booked simply never showed up in the
        portfolio and the button that promised to update it did not.
        """
        discovered = discover_missing_positions(user=request.user)
        positions = list(self.get_queryset())
        created = sum(sync_ledger_valuations(position=position) for position in positions)
        return Response(
            {
                "positions_checked": len(positions),
                "valuations_created": created,
                "positions_created": discovered,
            }
        )

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
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = PositionOwnershipPeriodSerializer

    def get_queryset(self):
        queryset = (
            PositionOwnershipPeriod.objects.filter(position__portfolio__user=self.request.user)
            .select_related("position", "position__portfolio", "ownership")
            .prefetch_related("shares__member")
        )
        position_id = str(self.request.query_params.get("position_id") or "").strip()
        if position_id:
            if not position_id.isdigit():
                raise ValidationError({"position_id": "Debe ser un entero."})
            queryset = queryset.filter(position_id=int(position_id))
        return queryset

    def perform_destroy(self, instance: PositionOwnershipPeriod) -> None:
        """Deshacer un tramo devuelve la titularidad al anterior.

        Los periodos son inmutables, así que corregir una fecha mal puesta pasa por
        borrar y volver a escribir. Si al crearlo se cerró el tramo previo, borrarlo sin
        reabrirlo dejaría la posición sin titularidad desde esa fecha.
        """
        with db_transaction.atomic():
            previous = (
                PositionOwnershipPeriod.objects.filter(
                    position_id=instance.position_id,
                    end_date=instance.start_date - timedelta(days=1),
                )
                .order_by("-start_date")
                .first()
            )
            later_exists = PositionOwnershipPeriod.objects.filter(
                position_id=instance.position_id, start_date__gt=instance.start_date
            ).exists()
            instance.delete()
            if previous is not None and not later_exists:
                previous.end_date = None
                previous.save(update_fields=["end_date"])


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


class PortfolioHoldingThreadsView(APIView):
    """Los hilos economicos: el mismo activo bajo la misma titularidad, cambie o no de custodio."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio, start_date, end_date, _member_id = _performance_request(request)
        return Response(
            build_holding_threads(
                portfolio=portfolio,
                start_date=start_date,
                end_date=end_date,
                context=None,
            )
        )


def _holding_currency(position) -> str:
    """En qué está denominada la posición, que es por lo que filtra la cartera."""
    account = position.ledger_account if position.ledger_account_id else None
    return (account.currency if account else position.asset.currency).strip().upper()


class PortfolioWorkspaceView(APIView):
    """Everything `/cartera` needs for one period, off a single context load.

    The five read endpoints each rebuilt the whole context — 0.6s of queries apiece on a
    real portfolio — so changing a filter paid for it five times over. Loading it once
    here cuts that to two: the timeline needs its own, because its contributed series
    runs from inception while the rest is scoped to the selected window.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio, start_date, end_date, member_id = _performance_request(request)
        # Un solo contexto, ancho hasta el origen: el timeline lo necesita así y el resto
        # de constructores acota por ventana al usar los flujos, de modo que cargarlo dos
        # veces solo servía para pagar el doble.
        context = load_performance_context(
            portfolio=portfolio,
            start_date=timeline_context_start(portfolio=portfolio, start_date=start_date),
            end_date=end_date,
        )
        shared = {
            "portfolio": portfolio,
            "start_date": start_date,
            "end_date": end_date,
            "member_id": member_id,
        }
        period = {"from": start_date.isoformat(), "to": end_date.isoformat()}
        # Un filtro de inventario reduce de qué habla la pantalla entera: hero, evolución
        # y calidad incluidos. Antes solo afectaba a la tabla y a un bloque aparte, y el
        # hero seguía describiendo la cartera completa, que es justo lo que confundía.
        scope_ids = self._scope_ids(request, context=context)
        scoped = {"scope_ids": scope_ids} if scope_ids is not None else {}
        # El bloque de métricas y la lista de posiciones los consumen dos salidas cada uno:
        # se calculan una vez y se reparten.
        performance = build_portfolio_performance(**shared, context=context, **scoped)
        position_rows = build_portfolio_positions(**shared, context=context)
        return Response(
            {
                "scope": None if scope_ids is None else sorted(scope_ids),
                "overview": build_portfolio_overview(
                    **shared,
                    context=context,
                    **scoped,
                    performance=performance,
                    position_rows=position_rows,
                ),
                "performance": performance,
                "positions": {
                    "period": period,
                    "member_id": member_id,
                    "results": position_rows,
                },
                "timeline": {
                    "period": period,
                    "member_id": member_id,
                    "currency": portfolio.base_currency,
                    "results": build_portfolio_timeline(**shared, context=context, **scoped),
                },
                # El efectivo enlazado cuenta en el valor de la cartera, asi que la
                # composicion tiene que poder incluirlo: sin esto el grafico sumaba menos
                # que el hero y la liquidez no aparecia por ninguna parte. Con un filtro
                # de inventario activo queda fuera, porque no es de ninguna clase ni de
                # ninguna posicion concreta.
                "cash": {
                    "value": str(
                        (
                            build_cash_value(context=context, on_date=end_date, member_id=member_id)
                            if scope_ids is None
                            else Decimal("0")
                        ).quantize(Decimal("0.01"))
                    ),
                },
                "quality": build_portfolio_quality(
                    **shared, context=context, **scoped, performance=performance
                ),
            }
        )

    @staticmethod
    def _scope_ids(request, *, context) -> set[int] | None:
        """Las posiciones que el filtro de inventario deja dentro, o None si no hay filtro.

        `instrument_id` + `ownership_id` componen el hilo economico: el mismo activo bajo la
        misma titularidad, aunque haya cambiado de custodio. Un traspaso entre dos custodios
        del hilo es interno al scope y se anula solo, que es lo que devuelve la serie
        continua en lugar de una historia que empieza el dia de la ultima mudanza.
        """
        container_id = str(request.query_params.get("container_id") or "").strip()
        asset_class = str(request.query_params.get("asset_class") or "").strip()
        currency = str(request.query_params.get("currency") or "").strip().upper()
        instrument_id = str(request.query_params.get("instrument_id") or "").strip()
        ownership_id = str(request.query_params.get("ownership_id") or "").strip()
        if not container_id and not asset_class and not currency:
            if not instrument_id and not ownership_id:
                return None
        selected = context.positions
        if container_id:
            if not container_id.isdigit():
                raise ValidationError({"container_id": "Debe ser un entero."})
            selected = [row for row in selected if row.container_id == int(container_id)]
        if asset_class:
            if asset_class not in Instrument.AssetClass.values:
                raise ValidationError({"asset_class": "Clase de activo no válida."})
            selected = [row for row in selected if row.effective_asset_class == asset_class]
        if currency:
            selected = [row for row in selected if _holding_currency(row) == currency]
        if instrument_id:
            if not instrument_id.isdigit():
                raise ValidationError({"instrument_id": "Debe ser un entero."})
            selected = [row for row in selected if row.instrument_id == int(instrument_id)]
        if ownership_id:
            if not ownership_id.isdigit():
                raise ValidationError({"ownership_id": "Debe ser un entero."})
            wanted = int(ownership_id)
            selected = [
                row
                for row in selected
                if any(
                    period.ownership_id == wanted
                    for period in context.ownership_periods.get(row.id, [])
                )
            ]
        return {row.id for row in selected}


class PortfolioOperationOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio = Portfolio.objects.get(user=request.user)
        return Response(operation_options(portfolio=portfolio))


class PortfolioOperationPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        portfolio = Portfolio.objects.get(user=request.user)
        return Response(preview_operation(portfolio=portfolio, payload=dict(request.data)))


class PortfolioOperationConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        portfolio = Portfolio.objects.get(user=request.user)
        result = confirm_operation(portfolio=portfolio, payload=dict(request.data))
        return Response(result, status=status.HTTP_201_CREATED)


class PortfolioImportUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            raise ValidationError({"file": "Selecciona un fichero CSV."})
        portfolio = Portfolio.objects.get(user=request.user)
        batch, duplicate = upload_csv(portfolio=portfolio, uploaded_file=uploaded_file)
        payload = serialize_batch(batch)
        payload["duplicate_file"] = duplicate
        return Response(
            payload, status=status.HTTP_200_OK if duplicate else status.HTTP_201_CREATED
        )


class PortfolioImportDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _batch(self, request, batch_id: int) -> PortfolioImportBatch:
        try:
            return PortfolioImportBatch.objects.prefetch_related("rows").get(
                id=batch_id, portfolio__user=request.user
            )
        except PortfolioImportBatch.DoesNotExist as exc:
            raise ValidationError({"detail": "La importación no existe."}) from exc

    def get(self, request, batch_id: int):
        return Response(serialize_batch(self._batch(request, batch_id)))


class PortfolioImportPreviewView(PortfolioImportDetailView):
    def post(self, request, batch_id: int):
        batch = self._batch(request, batch_id)
        mapping = request.data.get("mapping")
        if not isinstance(mapping, dict):
            raise ValidationError({"mapping": "Indica el mapeo de columnas."})
        preview_import(portfolio=batch.portfolio, batch=batch, mapping=mapping)
        batch.refresh_from_db()
        return Response(serialize_batch(self._batch(request, batch_id)))


class PortfolioImportConfirmView(PortfolioImportDetailView):
    def post(self, request, batch_id: int):
        batch = self._batch(request, batch_id)
        row_ids = request.data.get("row_ids")
        if row_ids is not None and not isinstance(row_ids, list):
            raise ValidationError({"row_ids": "Debe ser una lista."})
        confirm_import(portfolio=batch.portfolio, batch=batch, row_ids=row_ids)
        return Response(serialize_batch(self._batch(request, batch_id)))


class AllocationStrategyViewSet(viewsets.ModelViewSet):
    """La politica de cada ambito de titularidad."""

    permission_classes = [IsAuthenticated]
    serializer_class = AllocationStrategySerializer

    def get_queryset(self):
        queryset = (
            AllocationStrategy.objects.filter(portfolio__user=self.request.user)
            .select_related("ownership")
            .prefetch_related("targets")
        )
        ownership_id = str(self.request.query_params.get("ownership_id") or "").strip()
        if ownership_id:
            if not ownership_id.isdigit():
                raise ValidationError({"ownership_id": "Debe ser un entero."})
            queryset = queryset.filter(ownership_id=int(ownership_id))
        return queryset


class PositionAllocationRuleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PositionAllocationRuleSerializer

    def get_queryset(self):
        return PositionAllocationRule.objects.filter(
            position__portfolio__user=self.request.user
        ).select_related("position")


class ContributionCommitmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ContributionCommitmentSerializer

    def get_queryset(self):
        # Un compromiso puede colgar de una posicion o de un contenedor: filtrar solo por
        # la primera dejaba fuera de la lista los minimos de plataforma.
        return ContributionCommitment.objects.filter(
            Q(position__portfolio__user=self.request.user)
            | Q(container__portfolio__user=self.request.user)
        ).select_related("position", "container")


class ContributionBasketViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Cestas de aportacion. Se crean resolviendo, no escribiendo lineas a mano."""

    permission_classes = [IsAuthenticated]
    serializer_class = ContributionBasketSerializer

    def get_queryset(self):
        rows = (
            ContributionBasket.objects.filter(portfolio__user=self.request.user)
            .select_related("ownership", "strategy")
            .prefetch_related("lines__position__asset", "lines__cash_account__container")
        )
        # La pantalla pregunta por un ambito y por lo que queda pendiente de decidir; el
        # historico completo de propuestas descartadas no es lo que se va a mirar.
        ownership_id = self.request.query_params.get("ownership_id")
        if str(ownership_id or "").isdigit():
            rows = rows.filter(ownership_id=int(ownership_id))
        wanted = [
            value
            for value in str(self.request.query_params.get("status") or "").split(",")
            if value in ContributionBasket.Status.values
        ]
        if wanted:
            rows = rows.filter(status__in=wanted)
        return rows

    def create(self, request):
        portfolio, ownership, on_date = _allocation_request(request)
        amount = _positive_amount(request.data.get("amount"))
        basket = create_basket(
            portfolio=portfolio,
            ownership=ownership,
            amount=amount,
            on_date=on_date,
            source_account_id=request.data.get("source_account_id") or None,
        )
        return Response(self.get_serializer(basket).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        basket = confirm_basket(
            basket=self.get_object(),
            line_ids=request.data.get("line_ids") or None,
            source_account_id=request.data.get("source_account_id") or None,
        )
        return Response(self.get_serializer(basket).data)

    @action(detail=True, methods=["post"])
    def discard(self, request, pk=None):
        return Response(self.get_serializer(discard_basket(basket=self.get_object())).data)


def _allocation_request(request) -> tuple[Portfolio, Ownership, date]:
    """Ambito y fecha de una peticion de asignacion."""
    portfolio = Portfolio.objects.filter(user=request.user).first()
    if portfolio is None:
        raise ValidationError({"portfolio": "Todavia no hay cartera."})
    raw = request.query_params.get("ownership_id") or request.data.get("ownership_id")
    if not str(raw or "").strip().isdigit():
        raise ValidationError({"ownership_id": "Indica el ambito de titularidad."})
    try:
        ownership = Ownership.objects.get(id=int(raw), user=request.user)
    except Ownership.DoesNotExist as exc:
        raise ValidationError({"ownership_id": "La titularidad no es tuya."}) from exc
    raw_date = request.query_params.get("on_date") or request.data.get("on_date")
    on_date = parse_date(str(raw_date)) if raw_date else timezone.localdate()
    if on_date is None:
        raise ValidationError({"on_date": "Fecha no valida."})
    return portfolio, ownership, on_date


def _benchmark_period(request, portfolio: Portfolio) -> tuple[date, date, int | None]:
    """El periodo de una lectura de benchmark o riesgo.

    Comparte contrato con rendimiento —`date_from`, `date_to`, `member_id`— para que la
    vista pueda pedir las tres cosas con los mismos parametros y el usuario no vea dos
    periodos distintos en la misma pantalla.
    """
    raw_from = request.query_params.get("date_from")
    raw_to = request.query_params.get("date_to")
    default_from, default_to = default_performance_period(portfolio)
    start_date = parse_date(str(raw_from)) if raw_from else default_from
    end_date = parse_date(str(raw_to)) if raw_to else default_to
    if start_date is None or end_date is None:
        raise ValidationError({"date_from": "Fecha no valida."})
    raw_member = request.query_params.get("member_id")
    member_id = int(raw_member) if str(raw_member or "").isdigit() else None
    return start_date, end_date, member_id


def _positive_amount(raw) -> Decimal:
    # Se escribe a mano y en español: "1.500,50" es lo que teclea cualquiera aquí, y
    # rechazarlo por la coma seria hacerle traducir a la maquina lo que la maquina ya
    # sabe leer.
    text = str(raw).strip().replace("€", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        amount = Decimal(text)
    except (TypeError, InvalidOperation) as exc:
        raise ValidationError({"amount": "Importe no valido."}) from exc
    if amount <= 0:
        raise ValidationError({"amount": "Debe ser mayor que cero."})
    return amount


class PortfolioAllocationView(APIView):
    """Actual frente a objetivo para un ambito, por clase y por posicion."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio, ownership, on_date = _allocation_request(request)
        return Response(build_allocation(portfolio=portfolio, ownership=ownership, on_date=on_date))


class PortfolioBenchmarkView(APIView):
    """La cartera contra su propia politica, mes a mes.

    El benchmark principal es estrategico: responde a "desviarme del plan, ayudo o no",
    que es la pregunta que el usuario puede accionar. Un indice global responde a otra
    —si merecio la pena elegir estos productos— y viaja como secundario opcional.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio, ownership, _ = _allocation_request(request)
        start_date, end_date, member_id = _benchmark_period(request, portfolio)
        return Response(
            build_portfolio_benchmark(
                portfolio=portfolio,
                ownership=ownership,
                start_date=start_date,
                end_date=end_date,
                member_id=member_id,
            )
        )


class PortfolioRiskView(APIView):
    """Volatilidad, caida maxima, mejor/peor mes y Sharpe, cada uno con su cobertura."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio, ownership, _ = _allocation_request(request)
        start_date, end_date, member_id = _benchmark_period(request, portfolio)
        return Response(
            build_portfolio_risk(
                portfolio=portfolio,
                ownership=ownership,
                start_date=start_date,
                end_date=end_date,
                member_id=member_id,
            )
        )


class PortfolioDecisionsView(APIView):
    """Que propuso el sistema, que se hizo y como quedo la desviacion."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio, ownership, on_date = _allocation_request(request)
        return Response(
            build_decision_log(portfolio=portfolio, ownership=ownership, on_date=on_date)
        )


class PositionExposureViewSet(viewsets.ModelViewSet):
    """Como se reparte por dentro cada posicion. Se declara a mano, con su fecha."""

    permission_classes = [IsAuthenticated]
    serializer_class = PositionExposureSerializer

    def get_queryset(self):
        rows = PositionExposure.objects.filter(
            position__portfolio__user=self.request.user
        ).select_related("position")
        position_id = self.request.query_params.get("position_id")
        if str(position_id or "").isdigit():
            rows = rows.filter(position_id=int(position_id))
        return rows


class PortfolioExposureView(APIView):
    """Exposicion agregada de la cartera, con lo que queda sin declarar."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio = Portfolio.objects.filter(user=request.user).first()
        if portfolio is None:
            raise ValidationError({"portfolio": "Todavia no hay cartera."})
        raw = request.query_params.get("on_date")
        on_date = parse_date(str(raw)) if raw else timezone.localdate()
        if on_date is None:
            raise ValidationError({"on_date": "Fecha no valida."})
        return Response(build_exposure(portfolio=portfolio, on_date=on_date))


class AllocationScopesView(APIView):
    """Los ambitos que tienen posiciones, de mayor a menor."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        portfolio = Portfolio.objects.filter(user=request.user).first()
        if portfolio is None:
            return Response([])
        raw = request.query_params.get("on_date")
        on_date = parse_date(str(raw)) if raw else timezone.localdate()
        if on_date is None:
            raise ValidationError({"on_date": "Fecha no valida."})
        return Response(build_scopes(portfolio=portfolio, on_date=on_date))


class ContributionSolveView(APIView):
    """Simula el reparto de una aportacion sin guardar nada."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        portfolio, ownership, on_date = _allocation_request(request)
        return Response(
            build_contribution(
                portfolio=portfolio,
                ownership=ownership,
                amount=_positive_amount(request.data.get("amount")),
                on_date=on_date,
            )
        )
