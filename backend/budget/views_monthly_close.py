from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MonthlyClose
from .serializers_settlement import (
    SettlementExecutionSerializer,
    SettlementReconciliationSerializer,
)
from .services_monthly_close import (
    _get_uncovered_expense_entries_for_month,
    _get_uncovered_income_entries_for_month,
    apply_distribution_to_checkins,
    compute_monthly_close_state,
    compute_smart_distribution,
    finalize_monthly_close,
    lock_monthly_close,
    reopen_monthly_close,
)
from .services_settlement_execution import (
    accept_settlement_recommendation,
    apply_all_settlement_recommendations,
    apply_settlement_recommendation,
    cancel_settlement_recommendation,
    reconcile_settlement_recommendation,
    reverse_settlement_recommendation,
    settlement_reconciliation_candidates,
)


def _get_or_create_draft(*, user, fiscal_year: int, month: int) -> MonthlyClose:
    mc, _ = MonthlyClose.objects.get_or_create(
        user=user,
        fiscal_year=fiscal_year,
        month=month,
        defaults={"status": MonthlyClose.Status.DRAFT},
    )
    return mc


class MonthlyCloseView(APIView):
    """GET and PATCH the monthly close record for a given year/month."""

    permission_classes = [IsAuthenticated]

    def get(self, request, year: int, month: int) -> Response:
        state = compute_monthly_close_state(
            user=request.user,
            fiscal_year=year,
            month=month,
        )
        return Response(state)

    def patch(self, request, year: int, month: int) -> Response:
        mc = _get_or_create_draft(user=request.user, fiscal_year=year, month=month)

        if mc.status == MonthlyClose.Status.LOCKED:
            return Response(
                {"detail": "No se puede modificar un cierre bloqueado."},
                status=status.HTTP_409_CONFLICT,
            )

        notes = request.data.get("notes")
        if notes is not None:
            mc.notes = str(notes)
            mc.save(update_fields=["notes", "updated_at"])

        accept_suggestions = request.data.get("accept_suggestions", False)
        if accept_suggestions:
            uncovered_income = _get_uncovered_income_entries_for_month(
                user=request.user, fiscal_year=year, month=month
            )
            uncovered_expense = _get_uncovered_expense_entries_for_month(
                user=request.user, fiscal_year=year, month=month
            )
            if uncovered_income or uncovered_expense:
                income_dist, expense_dist = compute_smart_distribution(
                    uncovered_income=[(e.id, amt) for e, amt in uncovered_income],
                    uncovered_expense=[(e.id, amt) for e, amt in uncovered_expense],
                )
                apply_distribution_to_checkins(
                    user=request.user,
                    fiscal_year=year,
                    month=month,
                    income_distribution=income_dist,
                    expense_distribution=expense_dist,
                )

        state = compute_monthly_close_state(user=request.user, fiscal_year=year, month=month)
        return Response(state)


class MonthlyCloseFinalizeView(APIView):
    """POST to transition DRAFT → FINALIZED."""

    permission_classes = [IsAuthenticated]

    def post(self, request, year: int, month: int) -> Response:
        mc = _get_or_create_draft(user=request.user, fiscal_year=year, month=month)
        try:
            mc = finalize_monthly_close(monthly_close=mc, user=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        state = compute_monthly_close_state(user=request.user, fiscal_year=year, month=month)
        return Response(state, status=status.HTTP_200_OK)


class MonthlyCloseReopenView(APIView):
    """POST to transition FINALIZED → DRAFT."""

    permission_classes = [IsAuthenticated]

    def post(self, request, year: int, month: int) -> Response:
        try:
            mc = MonthlyClose.objects.get(user=request.user, fiscal_year=year, month=month)
        except MonthlyClose.DoesNotExist:
            return Response(
                {"detail": "No existe cierre mensual para este periodo."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            reopen_monthly_close(monthly_close=mc)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        state = compute_monthly_close_state(user=request.user, fiscal_year=year, month=month)
        return Response(state, status=status.HTTP_200_OK)


class MonthlyCloseLockView(APIView):
    """POST to transition FINALIZED → LOCKED."""

    permission_classes = [IsAuthenticated]

    def post(self, request, year: int, month: int) -> Response:
        try:
            mc = MonthlyClose.objects.get(user=request.user, fiscal_year=year, month=month)
        except MonthlyClose.DoesNotExist:
            return Response(
                {"detail": "No existe cierre mensual para este periodo."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            lock_monthly_close(monthly_close=mc)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        state = compute_monthly_close_state(user=request.user, fiscal_year=year, month=month)
        return Response(state, status=status.HTTP_200_OK)


class MonthlyClosePlanImpactView(APIView):
    """GET the financial-plan impact for a finalized monthly close."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int) -> Response:
        from plan.services_monthly_close import MonthlyClosePlanService

        try:
            monthly_close = MonthlyClose.objects.get(pk=pk, user=request.user)
        except MonthlyClose.DoesNotExist:
            return Response(
                {"detail": "No existe cierre mensual."}, status=status.HTTP_404_NOT_FOUND
            )

        impact = MonthlyClosePlanService().impact(monthly_close=monthly_close)
        if impact is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(impact)


class MonthlyCloseSettlementApplyAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int) -> Response:
        serializer = SettlementExecutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = apply_all_settlement_recommendations(
            user=request.user,
            close_id=pk,
            execution_date=serializer.validated_data["execution_date"],
        )
        return Response({"recommendations": rows}, status=status.HTTP_200_OK)


class MonthlyCloseSettlementRecommendationActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int, recommendation_id: int, action: str) -> Response:
        common = {
            "user": request.user,
            "close_id": pk,
            "recommendation_id": recommendation_id,
        }
        if action == "accept":
            result = accept_settlement_recommendation(**common)
        elif action == "cancel":
            result = cancel_settlement_recommendation(**common)
        elif action == "reconcile":
            serializer = SettlementReconciliationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            result = reconcile_settlement_recommendation(
                **common, transaction_id=serializer.validated_data["transaction_id"]
            )
        elif action in {"apply", "reverse"}:
            serializer = SettlementExecutionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            service = (
                apply_settlement_recommendation
                if action == "apply"
                else reverse_settlement_recommendation
            )
            result = service(
                **common,
                execution_date=serializer.validated_data["execution_date"],
                amount=serializer.validated_data.get("amount"),
                idempotency_key=serializer.validated_data["idempotency_key"],
            )
        else:
            return Response({"detail": "Acción no soportada."}, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_200_OK)


class MonthlyCloseSettlementCandidatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int, recommendation_id: int) -> Response:
        rows = settlement_reconciliation_candidates(
            user=request.user,
            close_id=pk,
            recommendation_id=recommendation_id,
        )
        return Response({"candidates": rows}, status=status.HTTP_200_OK)
