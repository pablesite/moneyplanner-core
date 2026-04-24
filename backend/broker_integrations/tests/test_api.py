import os

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from broker_integrations.models import BrokerCredential, IncomeEvent
from core.models import FxRate
from memberships.models import FamilyMember, Ownership


class BrokerIntegrationsApiTests(APITestCase):
    def setUp(self):
        os.environ["BROKER_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        self.user = get_user_model().objects.create_user(
            username="broker_user",
            password="pass1234",
        )
        self.client.force_authenticate(user=self.user)
        member = FamilyMember.objects.create(
            user=self.user,
            name="Primary",
            role=FamilyMember.Role.ADULT,
        )
        self.ownership = Ownership.objects.create(
            user=self.user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=member,
        )

    def test_credentials_create_list_delete(self):
        create_res = self.client.post(
            "/api/v1/broker/credentials/",
            {
                "broker": "pionex",
                "label": "Main",
                "ownership_id": self.ownership.id,
                "api_key": "abc12345",
                "api_secret": "secret123",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertTrue(BrokerCredential.objects.filter(user=self.user, label="Main").exists())
        credential_id = create_res.data["id"]
        self.assertTrue(create_res.data["has_secret"])
        self.assertIn("*", create_res.data["api_key_masked"])

        list_res = self.client.get("/api/v1/broker/credentials/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK, list_res.data)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["id"], credential_id)

        delete_res = self.client.delete(f"/api/v1/broker/credentials/{credential_id}/")
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT, delete_res.data)
        self.assertFalse(BrokerCredential.objects.filter(id=credential_id).exists())

    def test_csv_import_staking_creates_income_events(self):
        content = (
            "date(UTC+0),Received Quantity,Received Currency,Sent Quantity,Sent Currency,tag\n"
            "2025-01-01 00:00:00,0.1,USDT,,,issued_profit\n"
            "2025-01-02 00:00:00,0.2,USDT,,,claimed_profit\n"
            "2025-01-03 00:00:00,1.0,USDT,,,stake\n"
        ).encode("utf-8")
        uploaded = SimpleUploadedFile("staking.csv", content, content_type="text/csv")
        response = self.client.post(
            "/api/v1/broker/csv-import/",
            {"broker": "pionex", "file_type": "pionex_staking", "file": uploaded},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(response.data["skipped"], 1)
        self.assertEqual(
            IncomeEvent.objects.filter(source=IncomeEvent.Source.PIONEX_STAKING_CSV).count(),
            2,
        )

    def test_csv_import_binance_convert_supported(self):
        content = (
            "Hora,Billetera,Par,Tipo,Vender,Comprar,Precio,Precio inverso,Fecha actualizada,Estado\n"
            "25-11-23 21:57:59,SPOT,ETHUSDC,Instant,20.00000000 USDC,0.00704773 ETH,x,x,x,Successful\n"
        ).encode("utf-8")
        uploaded = SimpleUploadedFile("binance-convert.csv", content, content_type="text/csv")
        response = self.client.post(
            "/api/v1/broker/csv-import/",
            {"broker": "binance", "file_type": "binance_convert", "file": uploaded},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["created"], 1)

    def test_get_fiscal_report_returns_payload(self):
        BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="Fiscal",
            api_key="fiscal-key",
            api_secret_encrypted=b"secret",
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate="0.90",
            rate_date="2025-01-01",
        )
        response = self.client.get("/api/v1/broker/fiscal-report/?year=2025")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["fiscal_year"], 2025)
        self.assertIn("resumen", response.data)
