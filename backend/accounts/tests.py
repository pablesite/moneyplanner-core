from django.contrib.auth import get_user_model
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
