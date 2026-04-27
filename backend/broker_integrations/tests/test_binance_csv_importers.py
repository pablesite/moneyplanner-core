from io import BytesIO
from datetime import datetime, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from broker_integrations.csv_importers import (
    import_binance_convert,
    import_binance_fiat_deposits,
    import_binance_simple_earn_flexible,
    import_binance_recurring,
    import_binance_transactions,
)
from broker_integrations.models import BrokerCredential, BrokerTrade, DepositWithdrawal, IncomeEvent
from memberships.models import FamilyMember, Ownership


class BinanceCsvImportersTests(TestCase):
    def test_import_binance_transactions_creates_income_and_trade(self):
        content = (
            "ID de usuario,Hora,Cuenta,Operación,Moneda,Cambiar,Comentario\n"
            "1,25-01-01 10:00:00,Spot,Simple Earn Flexible Interest,USDT,0.5,Binance Earn\n"
            "1,25-01-01 10:10:00,Spot,Referral Commission,USDC,1.25,Referral\n"
            "1,25-01-02 12:00:00,Spot,Transaction Buy,BTC,0.001,Recurring buy\n"
            "1,25-01-02 12:00:01,Spot,Transaction Spend,USDC,-50,Recurring buy\n"
            "1,25-01-02 12:00:01,Spot,Transaction Fee,BTC,-0.000001,Recurring buy\n"
            "1,25-01-02 13:00:00,Spot,Deposit,BTC,1.0,Ignore\n"
        ).encode("utf-8")
        result = import_binance_transactions(uploaded_file=BytesIO(content), credential=None)
        self.assertEqual(result["created"], 3)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(IncomeEvent.objects.count(), 2)
        self.assertEqual(BrokerTrade.objects.count(), 1)

        trade = BrokerTrade.objects.get()
        self.assertEqual(trade.source, BrokerTrade.Source.BINANCE_CSV)
        self.assertEqual(trade.base_asset, "BTC")
        self.assertEqual(trade.quote_asset, "USDC")
        self.assertGreater(trade.price, 0)

    def test_import_binance_convert_filters_successful_rows(self):
        content = (
            "Hora,Billetera,Par,Tipo,Vender,Comprar,Precio,Precio inverso,Fecha actualizada,Estado\n"
            "25-11-23 21:57:59,SPOT,ETHUSDC,Instant,20.00000000 USDC,0.00704773 ETH,x,x,x,Successful\n"
            "25-11-23 21:58:00,SPOT,BTCUSDC,Instant,20.00000000 USDC,0.00704773 BTC,x,x,x,Failed\n"
        ).encode("utf-8")
        result = import_binance_convert(uploaded_file=BytesIO(content), credential=None)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(BrokerTrade.objects.count(), 1)
        trade = BrokerTrade.objects.get()
        self.assertEqual(trade.side, BrokerTrade.Side.SELL)
        self.assertEqual(trade.base_asset, "USDC")
        self.assertEqual(trade.quote_asset, "ETH")
        self.assertEqual(trade.quantity, 20)

    def test_import_binance_recurring_dedups_existing_convert_trade(self):
        convert_content = (
            "Hora,Billetera,Par,Tipo,Vender,Comprar,Precio,Precio inverso,Fecha actualizada,Estado\n"
            "25-11-27 00:10:41,SPOT,BTCUSDC,Instant,25.00000000 USDC,0.00027627 BTC,x,x,x,Successful\n"
        ).encode("utf-8")
        recurring_content = (
            "Fecha de creación,Billetera,Frecuencia,Por hora,Monto original,Moneda original,Monto final,"
            "Moneda final,Precio,Precio inverso,Fecha de liquidación,ID del plan,Estado\n"
            "25-11-27 00:10:41,SPOT_FUNDING,WEEKLY,- -,25,USDC,0.00027627,BTC,x,x,25-11-27 00:10:41,11751419,SUCCESS\n"
        ).encode("utf-8")

        convert_result = import_binance_convert(
            uploaded_file=BytesIO(convert_content), credential=None
        )
        recurring_result = import_binance_recurring(
            uploaded_file=BytesIO(recurring_content), credential=None
        )

        self.assertEqual(convert_result["created"], 1)
        self.assertEqual(recurring_result["updated"], 1)
        self.assertEqual(BrokerTrade.objects.count(), 1)

    def test_import_binance_fiat_deposits_creates_costed_eur_deposits(self):
        content = (
            "Hora,Método,Monto de depósito,Monto a recibir,Tarifa,Estado,ID de transacción (TXID)\n"
            "25-02-15 00:49:14,Pay by bank app,498.00 EUR,497.5 EUR,0.50 EUR,Successful,dep-1\n"
            "25-02-15 00:44:00,Pay by bank app,498.00 EUR,497.5 EUR,0.50 EUR,Failed,dep-2\n"
        ).encode("utf-8")

        result = import_binance_fiat_deposits(uploaded_file=BytesIO(content), credential=None)

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["skipped"], 1)
        deposit = DepositWithdrawal.objects.get()
        self.assertEqual(deposit.source, DepositWithdrawal.Source.BINANCE_CSV)
        self.assertEqual(deposit.direction, DepositWithdrawal.Direction.DEPOSIT)
        self.assertEqual(deposit.asset, "EUR")
        self.assertEqual(deposit.amount, 497.5)
        self.assertEqual(deposit.cost_eur_per_unit, Decimal("1.0010050251"))

    def test_import_binance_simple_earn_flexible_imports_only_unknown_redemptions(self):
        user = get_user_model().objects.create_user(username="binance-flex-user")
        member = FamilyMember.objects.create(
            user=user,
            name="Primary",
            role=FamilyMember.Role.ADULT,
        )
        ownership = Ownership.objects.create(
            user=user,
            kind=Ownership.Kind.INDIVIDUAL,
            member=member,
        )
        credential = BrokerCredential.objects.create(
            user=user,
            ownership=ownership,
            broker=BrokerCredential.Broker.BINANCE,
            label="binance-flex",
            api_key="k",
            api_secret_encrypted=b"s",
        )
        BrokerTrade.objects.create(
            credential=credential,
            source=BrokerTrade.Source.BINANCE_CSV,
            trade_id="buy-usdc-known",
            symbol="USDCUSDT",
            base_asset="USDC",
            quote_asset="USDT",
            side=BrokerTrade.Side.BUY,
            price=Decimal("1"),
            quantity=Decimal("10"),
            fee=Decimal("0"),
            fee_asset="",
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            raw={},
        )
        content = (
            "Fecha de reembolso/canje,Nombre del Producto,Moneda,Principal reembolsado,Método,Canjear en,Estado\n"
            "25-02-07 13:29:20,GMT,GMT,1.02574955,Fast redemption,SPOT,Success\n"
            "25-02-07 13:29:43,USDT,USDT,21.32737552,Fast redemption,SPOT,Success\n"
            "25-07-10 22:09:45,USDC,USDC,100,Fast redemption,SPOT,Success\n"
        ).encode("utf-8")

        result = import_binance_simple_earn_flexible(
            uploaded_file=BytesIO(content),
            credential=credential,
        )

        self.assertEqual(result["created"], 2)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(
            list(
                DepositWithdrawal.objects.filter(source=DepositWithdrawal.Source.BINANCE_CSV)
                .values_list("asset", flat=True)
                .order_by("asset")
            ),
            ["GMT", "USDT"],
        )
