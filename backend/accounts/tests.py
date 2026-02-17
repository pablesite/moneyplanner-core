from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from rest_framework import status
from rest_framework.test import APITestCase


class CoreAuthModeApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="core_user", password="pass1234")

    def test_auth_mode_reports_core_local(self):
        response = self.client.get("/api/auth/mode/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["auth_mode"], "core_local")
        self.assertTrue(response.data["standalone"])

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

    @override_settings(CORE_LINKING_SHARED_SECRET="test-shared-secret")
    def test_link_token_returns_one_time_payload(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/link-token/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("link_token", response.data)
        self.assertIn("expires_in_seconds", response.data)
        self.assertEqual(response.data["core_user_ref"], f"core_user:{self.user.id}")
