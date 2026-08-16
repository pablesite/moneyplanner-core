from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q

from .models import (
    ContainerCashAccount,
    Instrument,
    InvestmentContainer,
    Portfolio,
    PortfolioMigrationIssue,
    PortfolioPosition,
    PositionOwnershipPeriod,
)
from .serializers import (
    ContainerCashAccountSerializer,
    InstrumentSerializer,
    InvestmentContainerSerializer,
    PortfolioMigrationIssueSerializer,
    PortfolioPositionSerializer,
    PortfolioSerializer,
    PositionOwnershipPeriodSerializer,
)
from .services import bootstrap_portfolio_for_user, build_portfolio_readiness


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
        if self.action in {"list", "retrieve"}:
            return Instrument.objects.filter(Q(user=self.request.user) | Q(user__isnull=True))
        return Instrument.objects.filter(user=self.request.user)


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
