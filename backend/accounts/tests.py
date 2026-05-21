from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from datetime import timedelta
from rest_framework_simplejwt.settings import api_settings
from rest_framework import status
from rest_framework.test import APITestCase
from uuid import uuid4
import jwt
from unittest.mock import patch

from .models import ExternalIdentity, UserSettings
from .services import get_or_create_user_settings, update_user_settings


class CoreAuthModeApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="core_user", password="pass1234")

    def test_auth_mode_reports_core_local(self):
        response = self.client.get("/api/auth/mode/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["auth_mode"], "core_local")
        self.assertTrue(response.data["standalone"])
        self.assertIn("exit_ready", response.data)

    def test_auth_ops_metrics_requires_auth(self):
        response = self.client.get("/api/auth/ops/metrics/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_ops_metrics_returns_core_snapshot(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/ops/metrics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["service"], "core")
        self.assertEqual(response.data["auth_mode"], "core_local")
        self.assertIn("users_total", response.data)
        self.assertIn("jwt_outstanding_tokens", response.data)

    def test_token_login_rejects_invalid_credentials_with_unauthorized(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": self.user.username, "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "unauthorized")
        self.assertIn("message", response.data["error"])
        self.assertIn("details", response.data["error"])

    def test_link_token_requires_auth(self):
        response = self.client.get("/api/auth/link-token/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_link_token_returns_400_when_feature_disabled(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/link-token/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "feature_disabled")
        self.assertIn("message", response.data["error"])
        self.assertIn("details", response.data["error"])

    @override_settings(CORE_LINKING_SHARED_SECRET="test-shared-secret-32-bytes-minimum")
    def test_link_token_returns_one_time_payload(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/link-token/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("link_token", response.data)
        self.assertIn("expires_in_seconds", response.data)
        self.assertEqual(response.data["core_user_ref"], f"core_user:{self.user.id}")

    def test_session_compatibility_token_and_refresh(self):
        token_res = self.client.post(
            "/api/auth/token/",
            {"username": self.user.username, "password": "pass1234"},
            format="json",
        )
        self.assertEqual(token_res.status_code, status.HTTP_200_OK)
        access = token_res.data["access"]
        refresh = token_res.data["refresh"]

        settings_res = self.client.get(
            "/api/auth/settings/",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(settings_res.status_code, status.HTTP_200_OK)

        me_res = self.client.get(
            "/api/auth/me/",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(me_res.status_code, status.HTTP_200_OK)
        self.assertEqual(me_res.data["base_currency"], settings_res.data["base_currency"])
        self.assertEqual(me_res.data["inflation_region"], settings_res.data["inflation_region"])

        refresh_res = self.client.post(
            "/api/auth/refresh/",
            {"refresh": refresh},
            format="json",
        )
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_res.data)

    def test_settings_put_updates_existing_row(self):
        settings_obj, _ = UserSettings.objects.get_or_create(
            user=self.user, defaults={"base_currency": "EUR", "inflation_region": "ES"}
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            "/api/auth/settings/",
            {"base_currency": "USD", "inflation_region": "ES-MD"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["base_currency"], "USD")
        self.assertEqual(response.data["inflation_region"], "ES-MD")

        refreshed = UserSettings.objects.get(user=self.user)
        self.assertEqual(refreshed.id, settings_obj.id)
        self.assertEqual(refreshed.base_currency, "USD")
        self.assertEqual(refreshed.inflation_region, "ES-MD")

    def test_settings_get_creates_row_on_demand(self):
        UserSettings.objects.filter(user=self.user).delete()
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/settings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["base_currency"], "EUR")
        self.assertEqual(response.data["inflation_region"], "ES")
        self.assertTrue(UserSettings.objects.filter(user=self.user).exists())

    @patch("accounts.views.sync_market_data")
    def test_settings_put_triggers_fx_warmup_when_base_currency_changes(self, sync_market_data_mock):
        UserSettings.objects.update_or_create(
            user=self.user, defaults={"base_currency": "EUR", "inflation_region": "ES"}
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            "/api/auth/settings/",
            {"base_currency": "ETH", "inflation_region": "ES-MD"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        sync_market_data_mock.assert_called_once_with(datasets=["fx"], mode="reconcile")

    @patch("accounts.views.sync_market_data")
    def test_settings_put_does_not_trigger_fx_warmup_without_currency_change(
        self, sync_market_data_mock
    ):
        UserSettings.objects.update_or_create(
            user=self.user, defaults={"base_currency": "EUR", "inflation_region": "ES"}
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            "/api/auth/settings/",
            {"base_currency": "EUR", "inflation_region": "ES-MD"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        sync_market_data_mock.assert_not_called()


@override_settings(
    AUTH_ACCEPT_SAAS_TOKENS=True,
    SAAS_JWT_ISSUER="moneyplanner-saas",
    SAAS_JWT_AUDIENCE="moneyplanner-saas-api",
    SAAS_JWT_SIGNING_KEY="saas-signing-secret-32-bytes-minimum",
)
class CoreCrossStackSaasTokenTests(APITestCase):
    def _build_saas_access_token(self, *, saas_user_id: int) -> str:
        now = timezone.now()
        payload = {
            "token_type": "access",
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "iat": int(now.timestamp()),
            "jti": str(uuid4()),
            api_settings.USER_ID_CLAIM: saas_user_id,
            "iss": "moneyplanner-saas",
            "aud": "moneyplanner-saas-api",
        }
        return jwt.encode(
            payload, "saas-signing-secret-32-bytes-minimum", algorithm=api_settings.ALGORITHM
        )

    def test_saas_token_can_access_core_settings(self):
        token = self._build_saas_access_token(saas_user_id=42)
        response = self.client.get(
            "/api/auth/settings/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["base_currency"], "EUR")
        self.assertEqual(response.data["inflation_region"], "ES")

        mapped = ExternalIdentity.objects.get(
            provider=ExternalIdentity.Provider.SAAS,
            external_user_id="42",
        )
        self.assertEqual(mapped.user.username, "saas_user_42")

    def test_saas_token_never_reuses_core_user_id(self):
        core_user = get_user_model().objects.create_user(username="root", password="pass1234")
        token = self._build_saas_access_token(saas_user_id=core_user.id)
        response = self.client.get(
            "/api/auth/settings/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        mapped = ExternalIdentity.objects.get(
            provider=ExternalIdentity.Provider.SAAS,
            external_user_id=str(core_user.id),
        )
        self.assertNotEqual(mapped.user.id, core_user.id)
        self.assertNotEqual(mapped.user.username, core_user.username)


class CoreLogoutTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="logout_user", password="pass1234"
        )

    def _obtain_tokens(self):
        res = self.client.post(
            "/api/auth/token/",
            {"username": self.user.username, "password": "pass1234"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return res.data["access"], res.data["refresh"]

    def test_logout_requires_auth(self):
        response = self.client.post("/api/auth/logout/", {"refresh": "anything"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_missing_refresh_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_blacklists_refresh_token(self):
        access, refresh = self._obtain_tokens()

        logout_res = self.client.post(
            "/api/auth/logout/",
            {"refresh": refresh},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(logout_res.status_code, status.HTTP_204_NO_CONTENT)

        refresh_res = self.client.post(
            "/api/auth/refresh/",
            {"refresh": refresh},
            format="json",
        )
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_invalid_token_still_returns_204(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/auth/logout/", {"refresh": "not-a-valid-token"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class CoreAccountServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc_user", password="pass1234")

    def test_get_or_create_user_settings_creates_and_reuses(self):
        settings_a = get_or_create_user_settings(user=self.user)
        settings_b = get_or_create_user_settings(user=self.user)
        self.assertEqual(settings_a.id, settings_b.id)
        self.assertEqual(settings_a.base_currency, "EUR")
        self.assertEqual(settings_a.inflation_region, "ES")

    def test_update_user_settings_persists_values(self):
        updated = update_user_settings(
            user=self.user,
            validated_data={"base_currency": "USD", "inflation_region": "ES-AN"},
        )
        self.assertEqual(updated.base_currency, "USD")
        self.assertEqual(updated.inflation_region, "ES-AN")
