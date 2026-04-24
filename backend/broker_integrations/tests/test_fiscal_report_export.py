from django.test import SimpleTestCase

from broker_integrations.services.fiscal_report_export import export_csv, export_pdf


class FiscalReportExportTests(SimpleTestCase):
    def test_export_csv_includes_matched_and_gap_rows(self):
        report = {
            "fiscal_year": 2025,
            "ganancias_perdidas_trades": [
                {
                    "denominacion": "BTC",
                    "sales": [
                        {
                            "sell_trade_id": 10,
                            "sell_date": "2025-03-01",
                            "sell_exchange": "binance",
                            "quantity_sold": 1.0,
                            "proceeds_eur": 1000.0,
                            "fee_eur": 10.0,
                            "gap_quantity": 0.2,
                            "gap_reason": "missing_data",
                            "matched_lots": [
                                {
                                    "buy_trade_id": 1,
                                    "manual_cost_basis_id": None,
                                    "buy_date": "2025-01-01",
                                    "buy_exchange": "pionex",
                                    "quantity_consumed": 0.5,
                                    "cost_eur": 400.0,
                                    "fee_eur_allocated": 5.0,
                                    "gain_loss_eur": 95.0,
                                    "hold_days": 59,
                                },
                                {
                                    "buy_trade_id": None,
                                    "manual_cost_basis_id": 99,
                                    "buy_date": "2024-12-01",
                                    "buy_exchange": "manual",
                                    "quantity_consumed": 0.3,
                                    "cost_eur": 210.0,
                                    "fee_eur_allocated": 3.0,
                                    "gain_loss_eur": 87.0,
                                    "hold_days": 90,
                                },
                            ],
                        }
                    ],
                }
            ],
            "capital_mobiliario": [],
            "ganancias_perdidas_bots": [],
            "resumen": {},
            "avisos": [],
        }

        content = export_csv(report).decode("utf-8")
        lines = [line for line in content.splitlines() if line.strip()]
        self.assertEqual(len(lines), 4)
        self.assertIn("denominacion,fecha_adquisicion", lines[0])
        self.assertIn("trade", lines[1])
        self.assertIn("manual_cost_basis", lines[2])
        self.assertIn("gap:missing_data", lines[3])

    def test_export_pdf_returns_pdf_bytes(self):
        report = {
            "fiscal_year": 2025,
            "ganancias_perdidas_trades": [],
            "capital_mobiliario": [],
            "ganancias_perdidas_bots": [],
            "resumen": {
                "total_capital_mobiliario_eur": 0,
                "total_ganancias_eur": 0,
                "total_perdidas_eur": 0,
                "neto_ganancias_perdidas_eur": 0,
            },
            "avisos": [],
        }
        content = export_pdf(report)
        self.assertTrue(content.startswith(b"%PDF-"))
