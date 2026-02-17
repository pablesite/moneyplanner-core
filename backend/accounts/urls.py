from django.urls import path

from .auth_views import CoreTokenObtainPairView, CoreTokenRefreshView
from .views import CoreAuthModeAPIView, UserSettingsAPIView

urlpatterns = [
    path("token/", CoreTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", CoreTokenRefreshView.as_view(), name="token_refresh"),
    path("mode/", CoreAuthModeAPIView.as_view(), name="core_auth_mode"),
    path("settings/", UserSettingsAPIView.as_view(), name="user_settings"),
]
