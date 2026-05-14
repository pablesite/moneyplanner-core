from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Liability
from ..services_liabilities_core import (
    build_liability_installment_schedule_simple,
    estimate_liability_monthly_payment_simple,
    estimate_liability_outstanding_amount_simple,
)


class NetWorthLiabilityServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="nw_liability_user",
            password="pass1234",
        )

    def test_zero_interest_payment_and_outstanding_amount_use_payment_start_date(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo coche",
            category=Liability.Category.PERSONAL_LOAN,
            amount=Decimal("1200.00"),
            principal_amount=Decimal("1200.00"),
            annual_interest_tae=Decimal("0.00"),
            term_months=12,
            start_date=date(2026, 1, 15),
            payment_start_date=date(2026, 1, 31),
            payment_frequency=Liability.PaymentFrequency.MONTHLY,
            rate_type=Liability.RateType.FIXED,
            amortization_system=Liability.AmortizationSystem.FRENCH,
            currency="EUR",
        )

        schedule = build_liability_installment_schedule_simple(liability=liability)
        outstanding = estimate_liability_outstanding_amount_simple(
            liability=liability,
            as_of_date=date(2026, 3, 31),
        )

        self.assertEqual(len(schedule), 12)
        self.assertEqual(schedule[0], (date(2026, 1, 31), Decimal("100.00000000")))
        self.assertEqual(schedule[1][0], date(2026, 2, 28))
        self.assertEqual(outstanding, Decimal("900.00000000"))

    def test_monthly_payment_rejects_non_monthly_frequency(self):
        payment = estimate_liability_monthly_payment_simple(
            amount=Decimal("1200.00"),
            annual_interest_tae=Decimal("0.00"),
            term_months=12,
            payment_frequency=Liability.PaymentFrequency.QUARTERLY,
            rate_type=Liability.RateType.FIXED,
            amortization_system=Liability.AmortizationSystem.FRENCH,
        )

        self.assertIsNone(payment)
