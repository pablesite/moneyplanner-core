from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry


class AnnualIncomeApiEntriesTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="income_api_user", password="pass1234"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_list_and_totals_for_annual_income(self):
        create_res = self.client.post(
            "/api/budget/annual-income/",
            {
                "name": "CTN",
                "category": "salary",
                "subcategory": "employee_salary",
                "owner_name": "Pablo",
                "income_type": "recurrent",
                "amount_annual": "32460.00",
                "fiscal_year": 2026,
                "currency": "eur",
                "notes": "Nomina principal",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data["currency"], "EUR")
        self.assertEqual(create_res.data["fiscal_year"], 2026)
        self.assertEqual(create_res.data["time_profile"], "structural_recurrent")
        self.assertEqual(create_res.data["cashflow_role"], "operating")

        list_res = self.client.get("/api/budget/annual-income/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["name"], "CTN")

        totals_res = self.client.get("/api/budget/annual-income/totals/")
        self.assertEqual(totals_res.status_code, status.HTTP_200_OK)
        self.assertEqual(totals_res.data["total_annual"], "32460.00")

    def test_list_and_totals_can_be_filtered_by_fiscal_year(self):
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Ingreso 2025",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("1000.00"),
            fiscal_year=2025,
            currency="EUR",
        )
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Ingreso 2026",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("2000.00"),
            fiscal_year=2026,
            currency="EUR",
        )

        list_res = self.client.get("/api/budget/annual-income/?year=2025")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["name"], "Ingreso 2025")

        totals_res = self.client.get("/api/budget/annual-income/totals/?year=2025")
        self.assertEqual(totals_res.status_code, status.HTTP_200_OK)
        self.assertEqual(totals_res.data["total_annual"], "1000.00")

    def test_create_rejects_invalid_subcategory(self):
        create_res = self.client.post(
            "/api/budget/annual-income/",
            {
                "name": "Linea invalida",
                "category": "salary",
                "subcategory": "inheritance",
                "income_type": "one_off",
                "amount_annual": "1000.00",
                "currency": "EUR",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_queryset_is_user_scoped(self):
        other_user = get_user_model().objects.create_user(
            username="income_other_user", password="pass1234"
        )
        AnnualIncomeEntry.objects.create(
            user=other_user,
            name="Otro ingreso",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("100.00"),
            currency="EUR",
        )
        own = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Mi ingreso",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("200.00"),
            currency="EUR",
        )
        list_res = self.client.get("/api/budget/annual-income/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["id"], own.id)


class AnnualExpenseApiEntriesTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="expense_api_user", password="pass1234"
        )
        self.client.force_authenticate(user=self.user)

    def test_create_list_and_totals_for_annual_expense(self):
        create_res = self.client.post(
            "/api/budget/annual-expense/",
            {
                "name": "Alimentacion",
                "category": "consumption_expenses",
                "subcategory": "living_expenses",
                "owner_name": "Pablo",
                "expense_type": "recurrent",
                "amount_annual": "5500.00",
                "fiscal_year": 2026,
                "currency": "eur",
                "notes": "Supermercado",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data["currency"], "EUR")
        self.assertEqual(create_res.data["fiscal_year"], 2026)
        self.assertEqual(create_res.data["time_profile"], "structural_recurrent")
        self.assertEqual(create_res.data["cashflow_role"], "operating")

        list_res = self.client.get("/api/budget/annual-expense/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["name"], "Alimentacion")

        totals_res = self.client.get("/api/budget/annual-expense/totals/")
        self.assertEqual(totals_res.status_code, status.HTTP_200_OK)
        self.assertEqual(totals_res.data["total_annual"], "5500.00")

    def test_list_and_totals_can_be_filtered_by_fiscal_year(self):
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Gasto 2025",
            category="consumption_expenses",
            subcategory="living_expenses",
            amount_annual=Decimal("1000.00"),
            fiscal_year=2025,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Gasto 2026",
            category="consumption_expenses",
            subcategory="living_expenses",
            amount_annual=Decimal("2000.00"),
            fiscal_year=2026,
            currency="EUR",
        )

        list_res = self.client.get("/api/budget/annual-expense/?year=2025")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["name"], "Gasto 2025")

        totals_res = self.client.get("/api/budget/annual-expense/totals/?year=2025")
        self.assertEqual(totals_res.status_code, status.HTTP_200_OK)
        self.assertEqual(totals_res.data["total_annual"], "1000.00")

    def test_create_rejects_invalid_subcategory(self):
        create_res = self.client.post(
            "/api/budget/annual-expense/",
            {
                "name": "Linea invalida",
                "category": "consumption_expenses",
                "subcategory": "crypto",
                "expense_type": "one_off",
                "amount_annual": "1000.00",
                "currency": "EUR",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_queryset_is_user_scoped(self):
        other_user = get_user_model().objects.create_user(
            username="expense_other_user", password="pass1234"
        )
        AnnualExpenseEntry.objects.create(
            user=other_user,
            name="Otro gasto",
            category="consumption_expenses",
            subcategory="living_expenses",
            amount_annual=Decimal("100.00"),
            currency="EUR",
        )
        own = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Mi gasto",
            category="consumption_expenses",
            subcategory="living_expenses",
            amount_annual=Decimal("200.00"),
            currency="EUR",
        )
        list_res = self.client.get("/api/budget/annual-expense/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["id"], own.id)

    def test_create_one_off_expense_requires_target_month(self):
        create_res = self.client.post(
            "/api/budget/annual-expense/",
            {
                "name": "Seguro anual coche",
                "category": "consumption_expenses",
                "subcategory": "transport_mobility",
                "expense_type": "one_off",
                "amount_annual": "600.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("target_month", create_res.data["error"]["details"])
