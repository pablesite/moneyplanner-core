from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from net_worth.models import Liability


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

    def test_create_one_off_income_requires_target_month(self):
        create_res = self.client.post(
            "/api/budget/annual-income/",
            {
                "name": "Reserva vivienda",
                "category": "capital_gains",
                "subcategory": "sale_real_estate",
                "income_type": "one_off",
                "time_profile": "one_off",
                "amount_annual": "8240.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("target_month", create_res.data["error"]["details"])

    def test_create_recurrent_income_accepts_optional_target_month(self):
        create_res = self.client.post(
            "/api/budget/annual-income/",
            {
                "name": "Paga extra anual",
                "category": "salary",
                "subcategory": "bonus_commission",
                "income_type": "recurrent",
                "time_profile": "structural_recurrent",
                "target_month": 7,
                "amount_annual": "3000.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data["target_month"], 7)

    def test_create_income_accepts_zero_amount(self):
        create_res = self.client.post(
            "/api/budget/annual-income/",
            {
                "name": "Ingreso en pausa",
                "category": "salary",
                "subcategory": "employee_salary",
                "income_type": "recurrent",
                "time_profile": "structural_recurrent",
                "amount_annual": "0.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data["amount_annual"], "0.00")

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

    def test_create_expense_accepts_zero_amount(self):
        create_res = self.client.post(
            "/api/budget/annual-expense/",
            {
                "name": "Partida en pausa",
                "category": "consumption_expenses",
                "subcategory": "living_expenses",
                "expense_type": "recurrent",
                "time_profile": "structural_recurrent",
                "amount_annual": "0.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data["amount_annual"], "0.00")

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

    def test_year_filter_avoids_duplicate_autogenerated_liability_entries(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo coche",
            category="personal_loan",
            amount=Decimal("10000.00"),
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            source_liability=liability,
            is_system_generated=True,
            name="Compromiso pasivo: Prestamo coche",
            category="consumption_expenses",
            subcategory="financial_commitments",
            expense_type="recurrent",
            time_profile="term_recurrent",
            cashflow_role="temporary_commitment",
            event_group=f"liability_{liability.id}",
            term_end_year=2027,
            amount_annual=Decimal("7000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            source_liability=liability,
            is_system_generated=True,
            name="Compromiso pasivo: Prestamo coche",
            category="consumption_expenses",
            subcategory="financial_commitments",
            expense_type="recurrent",
            time_profile="term_recurrent",
            cashflow_role="temporary_commitment",
            event_group=f"liability_{liability.id}",
            term_end_year=2027,
            amount_annual=Decimal("3000.00"),
            fiscal_year=2027,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Suscripcion",
            category="consumption_expenses",
            subcategory="living_expenses",
            expense_type="recurrent",
            time_profile="structural_recurrent",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
        )

        list_res = self.client.get("/api/budget/annual-expense/?year=2027")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        returned_ids = {row["fiscal_year"] for row in list_res.data if row["is_system_generated"]}
        self.assertEqual(returned_ids, {2027})
