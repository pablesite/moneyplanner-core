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

from .models import ExternalIdentity
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

    def test_link_token_requires_auth(self):
        response = self.client.get("/api/auth/link-token/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_link_token_returns_400_when_feature_disabled(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/link-token/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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

        refresh_res = self.client.post(
            "/api/auth/refresh/",
            {"refresh": refresh},
            format="json",
        )
        self.assertEqual(refresh_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_res.data)


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


class CoreAccountServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="svc_user", password="pass1234")

    def test_get_or_create_user_settings_creates_and_reuses(self):
        settings_a = get_or_create_user_settings(user=self.user)
        settings_b = get_or_create_user_settings(user=self.user)
        self.assertEqual(settings_a.id, settings_b.id)
        self.assertEqual(settings_a.base_currency, "EUR")

    def test_update_user_settings_persists_values(self):
        updated = update_user_settings(user=self.user, validated_data={"base_currency": "USD"})
        self.assertEqual(updated.base_currency, "USD")
