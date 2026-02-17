from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .auth_audit import log_auth_event


class CoreTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        username = request.data.get("username", "")
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            log_auth_event(event="login", outcome="failed", username=username, status_code=401)
            raise

        if response.status_code < 400:
            log_auth_event(event="login", outcome="success", username=username)
        else:
            log_auth_event(
                event="login",
                outcome="failed",
                username=username,
                status_code=response.status_code,
            )
        return response


class CoreTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_refresh"
