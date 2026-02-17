from rest_framework import status
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from .serializers import UserSettingsSerializer
from .services import get_or_create_user_settings, update_user_settings


class UserSettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_settings"

    def get(self, request):
        settings_obj = get_or_create_user_settings(user=request.user)
        data = UserSettingsSerializer(settings_obj).data
        return Response(data)

    def put(self, request):
        get_or_create_user_settings(user=request.user)
        serializer = UserSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = update_user_settings(user=request.user, validated_data=serializer.validated_data)
        return Response(UserSettingsSerializer(updated).data, status=status.HTTP_200_OK)


class CoreAuthModeAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_mode"

    def get(self, request):
        return Response(
            {
                "auth_mode": "core_local",
                "auth_mode_enabled": bool(getattr(settings, "AUTH_MODE_CORE_LOCAL", True)),
                "standalone": True,
            }
        )


class CoreAuthOpsMetricsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_ops_metrics"

    def get(self, request):
        user_model = get_user_model()
        active_tokens = OutstandingToken.objects.count()
        payload = {
            "service": "core",
            "users_total": user_model.objects.count(),
            "users_active": user_model.objects.filter(is_active=True).count(),
            "jwt_outstanding_tokens": active_tokens,
            "auth_mode": "core_local",
        }
        return Response(payload)
