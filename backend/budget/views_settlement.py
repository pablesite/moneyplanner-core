from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers_settlement import (
    SettlementActivationSerializer,
    SettlementConfigurationWriteSerializer,
    SettlementRebaselineSerializer,
    SettlementReserveAdjustmentSerializer,
)
from .services_settlement import (
    activate_settlement_profile,
    build_settlement_readiness,
    can_rebaseline_settlement_profile,
    disable_settlement_profile,
    get_or_create_settlement_profile,
    replace_settlement_configuration,
    rebaseline_settlement_profile,
    set_operating_reserve_adjustment,
)


def serialize_settlement_configuration(profile) -> dict[str, object]:
    accounts = list(profile.accounts.select_related("asset", "member").order_by("id"))
    start_date = (
        profile.activation_date + timedelta(days=1) if profile.activation_date is not None else None
    )
    return {
        "is_enabled": profile.is_enabled,
        "activation_date": profile.activation_date,
        "baseline_date": profile.activation_date,
        "start_date": start_date,
        "can_rebaseline": can_rebaseline_settlement_profile(profile=profile),
        "base_currency": profile.base_currency,
        # Keep the JSON contract consistent with the other money values consumed by the UI.
        "operating_reserve_adjustment": str(profile.operating_reserve_adjustment),
        "readiness_status": profile.readiness_status,
        "readiness_checked_at": profile.readiness_checked_at,
        "accounts": [
            {
                "id": account.id,
                "asset_id": account.asset_id,
                "asset_name": account.asset.name,
                "role": account.role,
                "member_id": account.member_id,
                "member_name": account.member.name if account.member else None,
                "currency": account.currency,
                "is_primary": account.is_primary,
                "accepted_physical_balance": account.accepted_physical_balance,
                "modeled_balance_at_activation": account.modeled_balance_at_activation,
                "wallet_difference": (
                    account.modeled_balance_at_activation - account.accepted_physical_balance
                    if account.modeled_balance_at_activation is not None
                    and account.accepted_physical_balance is not None
                    else None
                ),
            }
            for account in accounts
        ],
        "opening_adjustments": [
            {
                "id": adjustment.id,
                "account_id": adjustment.account_id,
                "asset_id": adjustment.account.asset_id,
                "member_id": adjustment.member_id,
                "member_name": adjustment.member.name,
                "amount": adjustment.amount,
                "kind": adjustment.kind,
                "note": adjustment.note,
            }
            for adjustment in profile.opening_adjustments.select_related(
                "account", "member"
            ).order_by("id")
        ],
        "opening_balances": [
            {
                "account_id": balance.account_id,
                "asset_id": balance.account.asset_id,
                "member_id": balance.member_id,
                "member_name": balance.member.name,
                "amount": balance.amount,
                "currency": balance.currency,
            }
            for balance in profile.opening_balances.select_related("account", "member").order_by(
                "account_id", "member_id"
            )
        ],
        "normalization_transactions": [
            {
                "transaction_id": row.transaction_id,
                "booking_date": row.transaction.booking_date,
                "description": row.transaction.description,
            }
            for row in profile.wallet_normalizations.select_related("transaction").order_by(
                "transaction__booking_date", "transaction_id"
            )
        ],
    }


class SettlementConfigurationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_or_create_settlement_profile(user=request.user)
        return Response(serialize_settlement_configuration(profile))

    def put(self, request):
        serializer = SettlementConfigurationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = replace_settlement_configuration(
            user=request.user,
            payload=serializer.validated_data,
        )
        return Response(serialize_settlement_configuration(profile))


class SettlementReserveAdjustmentView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = SettlementReserveAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = set_operating_reserve_adjustment(
            user=request.user,
            amount=serializer.validated_data["operating_reserve_adjustment"],
        )
        return Response(serialize_settlement_configuration(profile))


class SettlementReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        balance_date_raw = request.query_params.get("balance_date")
        balance_date = parse_date(balance_date_raw) if balance_date_raw else None
        if balance_date_raw and balance_date is None:
            return Response(
                {"detail": "balance_date debe ser una fecha valida en formato YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            fiscal_year = int(
                request.query_params.get(
                    "year", balance_date.year if balance_date is not None else today.year
                )
            )
            month = int(
                request.query_params.get(
                    "month", balance_date.month if balance_date is not None else today.month
                )
            )
            if fiscal_year < 1 or month < 1 or month > 12:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {"detail": "year y month deben formar un periodo valido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            build_settlement_readiness(
                user=request.user,
                fiscal_year=fiscal_year,
                month=month,
                balance_date=balance_date,
            )
        )


class SettlementActivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SettlementActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        start_date = serializer.validated_data.get("start_date")
        if start_date is None:
            legacy_baseline = serializer.validated_data.get("activation_date")
            start_date = (
                legacy_baseline + timedelta(days=1)
                if legacy_baseline is not None
                else timezone.localdate()
            )
        profile = activate_settlement_profile(user=request.user, start_date=start_date)
        return Response(serialize_settlement_configuration(profile))


class SettlementRebaselineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SettlementRebaselineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = rebaseline_settlement_profile(
            user=request.user,
            payload=serializer.validated_data,
        )
        return Response(serialize_settlement_configuration(profile))


class SettlementDisableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = disable_settlement_profile(user=request.user)
        return Response(serialize_settlement_configuration(profile))
