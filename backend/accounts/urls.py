from django.urls import path

from .auth_views import CoreLogoutView, CoreTokenObtainPairView, CoreTokenRefreshView, RegisterView
from .views import (
    CoreAdminUsersAPIView,
    CoreAuthModeAPIView,
    CoreAuthOpsMetricsAPIView,
    CoreLinkTokenAPIView,
    UserSettingsAPIView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", CoreTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", CoreTokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", CoreLogoutView.as_view(), name="logout"),
    path("me/", UserSettingsAPIView.as_view(), name="user_me"),
    path("mode/", CoreAuthModeAPIView.as_view(), name="core_auth_mode"),
    path("ops/metrics/", CoreAuthOpsMetricsAPIView.as_view(), name="core_auth_ops_metrics"),
    path("admin/users/", CoreAdminUsersAPIView.as_view(), name="core_admin_users"),
    path("link-token/", CoreLinkTokenAPIView.as_view(), name="core_link_token"),
    path("settings/", UserSettingsAPIView.as_view(), name="user_settings"),
]
