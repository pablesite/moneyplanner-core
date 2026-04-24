from io import BytesIO

from django.test import TestCase

from broker_integrations.csv_importers import (
    import_binance_convert,
    import_binance_recurring,
    import_binance_transactions,
)
from broker_integrations.models import BrokerTrade, IncomeEvent


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
