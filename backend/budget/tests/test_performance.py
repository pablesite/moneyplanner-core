from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import UserSettings
from budget.models import AnnualExpenseEntry, AnnualIncomeEntry


class MonthlyClosePerformanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="monthly_close_perf_user",
            password="pass1234",
        )
        UserSettings.objects.update_or_create(
            user=self.user,
            defaults={"base_currency": "EUR", "inflation_region": "ES"},
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_monthly_close_avoids_deferred_taxonomy_queries_for_many_entries(self):
        AnnualIncomeEntry.objects.bulk_create(
            [
                AnnualIncomeEntry(
                    user=self.user,
                    name=f"Ingreso {idx}",
                    category=AnnualIncomeEntry.Category.SALARY,
                    subcategory="salary",
                    amount_annual=Decimal("12000.00"),
                    fiscal_year=2026,
                    currency="EUR",
                    is_active=True,
                )
                for idx in range(20)
            ]
        )
        AnnualExpenseEntry.objects.bulk_create(
            [
                AnnualExpenseEntry(
                    user=self.user,
                    name=f"Gasto {idx}",
                    category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
                    subcategory="groceries",
                    amount_annual=Decimal("6000.00"),
                    fiscal_year=2026,
                    currency="EUR",
                    is_active=True,
                )
                for idx in range(40)
            ]
        )

        with CaptureQueriesContext(connection) as captured_queries:
            response = self.client.get("/api/budget/monthly-close/2026/5/")

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(captured_queries), 40)
        self.assertEqual(response.data["income"]["planned"], "20000.00")
        self.assertEqual(response.data["expense"]["planned"], "20000.00")
