from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction

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

    def test_historical_summary_includes_archived_asset_with_ledger_activity(self):
        deposit = Asset.objects.create(
            user=self.user,
            name="Deposito cerrado",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.SHORT_TERM_DEPOSIT,
            amount=Decimal("0.00"),
            currency="EUR",
            start_date=date(2026, 1, 1),
            is_active=False,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
        )
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Deposito cerrado",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=deposit,
        )
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 7, 1),
            value_date=date(2026, 7, 1),
            description="Apertura deposito",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("5000.00"),
        )

        summary = build_liquidity_monthly_summary(user=self.user, fiscal_year=2026, month=7)

        self.assertEqual(summary["rows"][0]["asset_name"], "Deposito cerrado")
