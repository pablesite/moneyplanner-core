import os

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from broker_integrations.models import (
    BotNetResult,
    BrokerCredential,
    DepositWithdrawal,
    ManualCostBasis,
    BrokerSyncRun,
    BrokerTrade,
    IncomeEvent,
)
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
        credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.PIONEX,
            label="Pionex CSV",
            api_key="pionex-key",
            api_secret_encrypted=b"secret",
        )
        content = (
            "date(UTC+0),Received Quantity,Received Currency,Sent Quantity,Sent Currency,tag\n"
            "2025-01-01 00:00:00,0.1,USDT,,,issued_profit\n"
            "2025-01-02 00:00:00,0.2,USDT,,,claimed_profit\n"
            "2025-01-03 00:00:00,1.0,USDT,,,stake\n"
        ).encode("utf-8")
        uploaded = SimpleUploadedFile("staking.csv", content, content_type="text/csv")
        response = self.client.post(
            "/api/v1/broker/csv-import/",
            {
                "broker": "pionex",
                "credential_id": credential.id,
                "file_type": "pionex_staking",
                "file": uploaded,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(response.data["skipped"], 1)
        self.assertEqual(response.data["credential_id"], credential.id)
        self.assertEqual(
            IncomeEvent.objects.filter(
                credential=credential,
                source=IncomeEvent.Source.PIONEX_STAKING_CSV,
            ).count(),
            2,
        )

    def test_csv_import_binance_convert_supported(self):
        credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="Binance CSV",
            api_key="binance-key",
            api_secret_encrypted=b"secret",
        )
        content = (
            "Hora,Billetera,Par,Tipo,Vender,Comprar,Precio,Precio inverso,Fecha actualizada,Estado\n"
            "25-11-23 21:57:59,SPOT,ETHUSDC,Instant,20.00000000 USDC,0.00704773 ETH,x,x,x,Successful\n"
        ).encode("utf-8")
        uploaded = SimpleUploadedFile("binance-convert.csv", content, content_type="text/csv")
        response = self.client.post(
            "/api/v1/broker/csv-import/",
            {
                "broker": "binance",
                "credential_id": credential.id,
                "file_type": "binance_convert",
                "file": uploaded,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(response.data["credential_id"], credential.id)

    def test_csv_import_binance_fiat_deposits_supported(self):
        credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="Binance Fiat CSV",
            api_key="binance-key",
            api_secret_encrypted=b"secret",
        )
        content = (
            "Hora,Método,Monto de depósito,Monto a recibir,Tarifa,Estado,ID de transacción (TXID)\n"
            "25-02-15 00:49:14,Pay by bank app,498.00 EUR,497.5 EUR,0.50 EUR,Successful,dep-1\n"
        ).encode("utf-8")
        uploaded = SimpleUploadedFile(
            "binance-fiat-deposits.csv",
            content,
            content_type="text/csv",
        )
        response = self.client.post(
            "/api/v1/broker/csv-import/",
            {
                "broker": "binance",
                "credential_id": credential.id,
                "file_type": "binance_fiat_deposits",
                "file": uploaded,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(response.data["credential_id"], credential.id)
        self.assertEqual(
            DepositWithdrawal.objects.filter(
                credential=credential,
                source=DepositWithdrawal.Source.BINANCE_CSV,
            ).count(),
            1,
        )

    def test_csv_import_binance_simple_earn_flexible_supported(self):
        credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="Binance Flexible CSV",
            api_key="binance-key",
            api_secret_encrypted=b"secret",
        )
        content = (
            "Fecha de reembolso/canje,Nombre del Producto,Moneda,Principal reembolsado,Método,Canjear en,Estado\n"
            "25-02-07 13:29:20,GMT,GMT,1.02574955,Fast redemption,SPOT,Success\n"
        ).encode("utf-8")
        uploaded = SimpleUploadedFile(
            "binance-simple-earn-flexible.csv",
            content,
            content_type="text/csv",
        )
        response = self.client.post(
            "/api/v1/broker/csv-import/",
            {
                "broker": "binance",
                "credential_id": credential.id,
                "file_type": "binance_simple_earn_flexible",
                "file": uploaded,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["created"], 1)

    def test_csv_import_pionex_deposit_withdraw_creates_deposit_rows(self):
        credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.PIONEX,
            label="Pionex deposits",
            api_key="pionex-key",
            api_secret_encrypted=b"secret",
        )
        content = (
            "date(UTC+0),tx_type,amount,coin,network,txid,fee\n"
            "2025-07-10 20:11:14,DEPOSIT,99.98000000,USDC,BEP20,tx-1,0.00000000\n"
            "2025-10-17 07:29:50,WITHDRAW,0.00429415,BTC,BEP20,tx-2,0.00000700\n"
        ).encode("utf-8")
        uploaded = SimpleUploadedFile(
            "deposit-withdraw.csv",
            content,
            content_type="text/csv",
        )
        response = self.client.post(
            "/api/v1/broker/csv-import/",
            {
                "broker": "pionex",
                "credential_id": credential.id,
                "file_type": "pionex_deposit_withdraw",
                "file": uploaded,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["created"], 2)
        self.assertEqual(response.data["skipped"], 0)
        self.assertEqual(
            DepositWithdrawal.objects.filter(credential=credential).count(),
            2,
        )
        usdc_deposit = DepositWithdrawal.objects.get(
            credential=credential,
            transaction_id="tx-1",
        )
        self.assertIsNotNone(usdc_deposit.cost_eur_per_unit)

    def test_csv_import_rejects_credential_from_other_broker(self):
        credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="Wrong broker",
            api_key="binance-key",
            api_secret_encrypted=b"secret",
        )
        uploaded = SimpleUploadedFile("staking.csv", b"date(UTC+0)\n", content_type="text/csv")
        response = self.client.post(
            "/api/v1/broker/csv-import/",
            {
                "broker": "pionex",
                "credential_id": credential.id,
                "file_type": "pionex_staking",
                "file": uploaded,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("credential_id", response.data["error"]["details"])

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
        self.assertEqual(response.data["schema_version"], 3)
        self.assertEqual(response.data["fiscal_year"], 2025)
        self.assertIn("resumen", response.data)
        self.assertIn("reliability", response.data)
        self.assertIn("resumen_declarable", response.data)

    def test_get_fiscal_report_export_returns_csv_and_pdf(self):
        BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="Fiscal export",
            api_key="fiscal-export-key",
            api_secret_encrypted=b"secret",
        )
        FxRate.objects.create(
            from_currency="USD",
            to_currency="EUR",
            rate="0.90",
            rate_date="2025-01-01",
        )

        csv_response = self.client.get("/api/v1/broker/fiscal-report/export/?year=2025&format=csv")
        self.assertEqual(csv_response.status_code, status.HTTP_200_OK, csv_response.content)
        self.assertTrue(csv_response["Content-Type"].startswith("text/csv"))
        self.assertIn('attachment; filename="fiscal-2025.csv"', csv_response["Content-Disposition"])
        self.assertIn("denominacion,fecha_adquisicion", csv_response.content.decode("utf-8"))

        pdf_response = self.client.get("/api/v1/broker/fiscal-report/export/?year=2025&format=pdf")
        self.assertEqual(pdf_response.status_code, status.HTTP_200_OK, pdf_response.content)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertIn('attachment; filename="fiscal-2025.pdf"', pdf_response["Content-Disposition"])
        self.assertTrue(pdf_response.content.startswith(b"%PDF-"))

    def test_get_fiscal_report_export_rejects_unsupported_format(self):
        BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="Fiscal unsupported",
            api_key="fiscal-unsupported",
            api_secret_encrypted=b"secret",
        )
        response = self.client.get("/api/v1/broker/fiscal-report/export/?year=2025&format=xlsx")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("format", response.data["error"]["details"])

    def test_manual_cost_basis_crud(self):
        create_res = self.client.post(
            "/api/v1/broker/manual-cost-basis/",
            {
                "ownership_id": self.ownership.id,
                "asset": "btc",
                "quantity": "0.5",
                "acquired_at": "2024-01-01T00:00:00Z",
                "cost_eur": "10000",
                "exchange_origin": "external",
                "notes": "legacy",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        row_id = create_res.data["id"]
        self.assertEqual(create_res.data["asset"], "BTC")

        list_res = self.client.get("/api/v1/broker/manual-cost-basis/?asset=BTC")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK, list_res.data)
        self.assertEqual(list_res.data["count"], 1)

        delete_res = self.client.delete(f"/api/v1/broker/manual-cost-basis/{row_id}/")
        self.assertEqual(delete_res.status_code, status.HTTP_204_NO_CONTENT, delete_res.data)
        self.assertFalse(ManualCostBasis.objects.filter(id=row_id).exists())

    def test_sync_runs_and_drilldown_endpoints(self):
        credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.PIONEX,
            label="Drilldown",
            api_key="key",
            api_secret_encrypted=b"secret",
        )
        bot_result = BotNetResult.objects.create(
            credential=credential,
            bot_id="bot-1",
            bot_type="spot_grid",
            label="Bot 1",
            base_asset="BTC",
            quote_asset="USDT",
            realized_profit="1.0",
            period_start="2025-01-01T00:00:00Z",
            period_end="2025-01-02T00:00:00Z",
            raw={
                "buOrderData": {
                    "gridProfit": "1.0",
                    "quoteAmount": "20",
                    "baseAmount": "0.1",
                    "quoteTotalInvestment": "100",
                    "closedPrice": "900",
                }
            },
        )
        trade = BrokerTrade.objects.create(
            credential=credential,
            bot=bot_result,
            source=BrokerTrade.Source.PIONEX_BOT_API,
            trade_id="trade-1",
            symbol="BTC_USDT",
            base_asset="BTC",
            quote_asset="USDT",
            side=BrokerTrade.Side.BUY,
            price="100",
            quantity="0.1",
            fee="0.001",
            fee_asset="BTC",
            timestamp="2025-01-01T00:00:00Z",
            raw={},
        )
        income = IncomeEvent.objects.create(
            credential=credential,
            source=IncomeEvent.Source.PIONEX_DUAL_INVEST_API,
            income_type=IncomeEvent.IncomeType.DUAL_INVEST_YIELD,
            asset="USDT",
            amount="5",
            timestamp="2025-01-01T00:00:00Z",
            raw={},
        )
        sync_run = BrokerSyncRun.objects.create(
            credential=credential,
            year=2025,
            status=BrokerSyncRun.Status.OK,
            stats={"new_trades": 1},
            gaps=[],
            new_trade_ids=[trade.id],
            updated_trade_ids=[],
            new_income_event_ids=[income.id],
            updated_income_event_ids=[],
            new_bot_result_ids=[bot_result.id],
            updated_bot_result_ids=[],
        )

        runs_res = self.client.get(
            f"/api/v1/broker/sync-runs/?credential={credential.id}&year=2025"
        )
        self.assertEqual(runs_res.status_code, status.HTTP_200_OK, runs_res.data)
        self.assertEqual(runs_res.data["count"], 1)

        run_detail_res = self.client.get(f"/api/v1/broker/sync-runs/{sync_run.id}/")
        self.assertEqual(run_detail_res.status_code, status.HTTP_200_OK, run_detail_res.data)
        self.assertEqual(run_detail_res.data["id"], sync_run.id)
        self.assertEqual(run_detail_res.data["trades"]["count"], 1)
        self.assertEqual(run_detail_res.data["income_events"]["count"], 1)
        self.assertEqual(run_detail_res.data["bot_results"]["count"], 1)

        trade_res = self.client.get(f"/api/v1/broker/trades/?sync_run={sync_run.id}")
        self.assertEqual(trade_res.status_code, status.HTTP_200_OK, trade_res.data)
        self.assertEqual(trade_res.data["count"], 1)

        income_res = self.client.get(f"/api/v1/broker/income-events/?sync_run={sync_run.id}")
        self.assertEqual(income_res.status_code, status.HTTP_200_OK, income_res.data)
        self.assertEqual(income_res.data["count"], 1)

        bot_list_res = self.client.get(f"/api/v1/broker/bot-results/?sync_run={sync_run.id}")
        self.assertEqual(bot_list_res.status_code, status.HTTP_200_OK, bot_list_res.data)
        self.assertEqual(bot_list_res.data["count"], 1)
        self.assertEqual(bot_list_res.data["results"][0]["bot_profit_quote"], "1.0")
        self.assertEqual(bot_list_res.data["results"][0]["grid_profit"], "1.0")
        self.assertEqual(bot_list_res.data["results"][0]["total_profit_quote"], "10.0")

        bot_detail_res = self.client.get(f"/api/v1/broker/bot-results/{bot_result.id}/")
        self.assertEqual(bot_detail_res.status_code, status.HTTP_200_OK, bot_detail_res.data)
        self.assertEqual(bot_detail_res.data["id"], bot_result.id)
        self.assertEqual(bot_detail_res.data["fills"]["count"], 1)
        self.assertEqual(bot_detail_res.data["bot_profit_quote"], "1.0")
        self.assertEqual(bot_detail_res.data["grid_profit"], "1.0")
        self.assertEqual(bot_detail_res.data["total_profit_quote"], "10.0")

    def test_trades_endpoint_supports_tax_id_filter(self):
        credential = BrokerCredential.objects.create(
            user=self.user,
            ownership=self.ownership,
            broker=BrokerCredential.Broker.PIONEX,
            label="Trades filter",
            api_key="key",
            api_secret_encrypted=b"secret",
        )
        BrokerTrade.objects.create(
            credential=credential,
            source=BrokerTrade.Source.PIONEX_CSV,
            trade_id="trade-tax-1",
            symbol="ETH_USDT",
            base_asset="ETH",
            quote_asset="USDT",
            side=BrokerTrade.Side.BUY,
            price="100",
            quantity="1",
            fee="0",
            fee_asset="ETH",
            timestamp="2025-01-01T00:00:00Z",
            raw={"tax_id": "s_163"},
        )
        BrokerTrade.objects.create(
            credential=credential,
            source=BrokerTrade.Source.PIONEX_CSV,
            trade_id="trade-tax-2",
            symbol="BTC_USDT",
            base_asset="BTC",
            quote_asset="USDT",
            side=BrokerTrade.Side.SELL,
            price="200",
            quantity="1",
            fee="0",
            fee_asset="USDT",
            timestamp="2025-01-02T00:00:00Z",
            raw={"tax_id": "s_999"},
        )

        response = self.client.get("/api/v1/broker/trades/?credential=%s&tax_id=s_163" % credential.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["trade_id"], "trade-tax-1")
        self.assertEqual(response.data["results"][0]["tax_id"], "s_163")
