from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import CoreAuthModeAPIView, UserSettingsAPIView

urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("mode/", CoreAuthModeAPIView.as_view(), name="core_auth_mode"),
    path("settings/", UserSettingsAPIView.as_view(), name="user_settings"),
]
