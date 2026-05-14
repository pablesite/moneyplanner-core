from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Asset, Liability, LiabilityValuation, LiquidityMonthlyCheckin
from ..services_liquidity import build_liquidity_monthly_summary


class NetWorthLiquidityServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="nw_liquidity_user",
            password="pass1234",
        )

    def test_monthly_summary_combines_cash_assets_and_credit_card_liabilities(self):
        cash = Asset.objects.create(
            user=self.user,
            name="Cuenta corriente",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            amount=Decimal("1000.00"),
            currency="EUR",
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        card = Liability.objects.create(
            user=self.user,
            name="Tarjeta",
            category=Liability.Category.CREDIT_CARD,
            amount=Decimal("300.00"),
            currency="EUR",
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        LiquidityMonthlyCheckin.objects.create(
            user=self.user,
            asset=cash,
            fiscal_year=2026,
            month=2,
            closing_balance_real=Decimal("1200.00"),
            note="Cierre revisado",
        )
        LiabilityValuation.objects.create(
            user=self.user,
            liability=card,
            valuation_date=date(2026, 2, 28),
            value=Decimal("250.00"),
            note="Saldo tarjeta",
        )

        summary = build_liquidity_monthly_summary(user=self.user, fiscal_year=2026, month=2)

        self.assertEqual(summary["planned_total"], "700.00")
        self.assertEqual(summary["executed_total"], "950.00")
        self.assertEqual(summary["gross_asset_executed_total"], "1200.00")
        self.assertEqual(summary["liquid_liability_executed_total"], "250.00")
        self.assertEqual(summary["coverage_confirmed"], 2)
        self.assertEqual([row["row_type"] for row in summary["rows"]], ["asset", "liability"])
