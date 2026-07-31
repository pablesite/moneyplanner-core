from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import AnnualExpenseEntry
from net_worth.models import Liability
from net_worth.services_liabilities_budget import (
    _estimate_accounting_cancellation_principal,
)


class AccountingLiabilityCancellationForecastTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cancellation-forecast",
            password="test-pass",
        )
        self.liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca con saldo contable",
            category=Liability.Category.MORTGAGE,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            currency="EUR",
            start_date=date(2016, 2, 21),
            annual_interest_tae=Decimal("2.00"),
            amount=Decimal("63000.00"),
            principal_amount=Decimal("21744.49"),
            term_months=360,
            cancellation_forecast_enabled=True,
            cancellation_date=date(2026, 11, 15),
        )

    @patch(
        "net_worth.services_liabilities_budget.get_effective_liability_amount",
        return_value=Decimal("20383.30"),
    )
    @patch(
        "net_worth.services_liabilities_budget.timezone.localdate",
        return_value=date(2026, 7, 31),
    )
    def test_uses_current_balance_and_remaining_budget_installments(
        self,
        _mock_today,
        _mock_effective_amount,
    ):
        AnnualExpenseEntry.objects.create(
            user=self.user,
            source_liability=self.liability,
            is_system_generated=True,
            name="Compromiso pasivo: Hipoteca",
            category=AnnualExpenseEntry.Category.REAL_ESTATE_ASSETS,
            subcategory="mortgage_principal",
            expense_type=AnnualExpenseEntry.ExpenseType.RECURRENT,
            time_profile=AnnualExpenseEntry.TimeProfile.TERM_RECURRENT,
            cashflow_role=AnnualExpenseEntry.CashflowRole.TEMPORARY_COMMITMENT,
            event_group=f"liability_{self.liability.id}",
            term_end_month=10,
            term_end_year=2026,
            amount_annual=Decimal("2554.90"),
            fiscal_year=2026,
        )

        result = _estimate_accounting_cancellation_principal(
            liability=self.liability,
            cancellation_date=date(2026, 11, 15),
        )

        self.assertEqual(result, Decimal("19717.63829551"))

    @patch(
        "net_worth.services_liabilities_budget.get_effective_liability_amount",
        return_value=Decimal("20383.30"),
    )
    @patch(
        "net_worth.services_liabilities_budget.timezone.localdate",
        return_value=date(2026, 7, 31),
    )
    def test_keeps_current_balance_when_no_future_installments_exist(
        self,
        _mock_today,
        _mock_effective_amount,
    ):
        result = _estimate_accounting_cancellation_principal(
            liability=self.liability,
            cancellation_date=date(2026, 11, 15),
        )

        self.assertEqual(result, Decimal("20383.30000000"))
