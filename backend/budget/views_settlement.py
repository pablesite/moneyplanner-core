from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers_settlement import (
    SettlementActivationSerializer,
    SettlementConfigurationWriteSerializer,
)
from .services_settlement import (
    activate_settlement_profile,
    build_settlement_readiness,
    disable_settlement_profile,
    get_or_create_settlement_profile,
    replace_settlement_configuration,
)


def serialize_settlement_configuration(profile) -> dict[str, object]:
    accounts = list(profile.accounts.select_related("asset", "member").order_by("id"))
    return {
        "is_enabled": profile.is_enabled,
        "activation_date": profile.activation_date,
        "base_currency": profile.base_currency,
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


class SettlementReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        try:
            fiscal_year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
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
            )
        )


class SettlementActivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SettlementActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = activate_settlement_profile(
            user=request.user,
            activation_date=serializer.validated_data.get("activation_date", timezone.localdate()),
        )
        return Response(serialize_settlement_configuration(profile))


class SettlementDisableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = disable_settlement_profile(user=request.user)
        return Response(serialize_settlement_configuration(profile))
