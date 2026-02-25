from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AnnualExpenseEntry, AnnualIncomeEntry
from .serializers import AnnualExpenseEntrySerializer, AnnualIncomeEntrySerializer
from .services import (
    EXPENSE_TAXONOMY,
    INCOME_TAXONOMY,
    validate_annual_expense_taxonomy,
    validate_annual_income_taxonomy,
)


class BudgetServicesTests(TestCase):
    def test_validate_annual_income_taxonomy(self):
        validate_annual_income_taxonomy(
            category="salary",
            subcategory="employee_salary",
        )
        with self.assertRaises(ValidationError):
            validate_annual_income_taxonomy(category="salary", subcategory="inheritance")
        with self.assertRaises(ValidationError):
            validate_annual_income_taxonomy(category="unknown", subcategory="other")

    def test_income_taxonomy_has_fallback_subcategories(self):
        for category, options in INCOME_TAXONOMY.items():
            self.assertTrue(options, msg=f"{category} must define subcategories")
            has_fallback = any(opt.startswith("other") or opt == "other" for opt in options)
            self.assertTrue(has_fallback, msg=f"{category} must define fallback subcategory")

    def test_validate_annual_expense_taxonomy(self):
        validate_annual_expense_taxonomy(
            category="consumption_expenses",
            subcategory="living_expenses",
        )
        with self.assertRaises(ValidationError):
            validate_annual_expense_taxonomy(category="consumption_expenses", subcategory="crypto")
        with self.assertRaises(ValidationError):
            validate_annual_expense_taxonomy(category="unknown", subcategory="other")

    def test_expense_taxonomy_has_fallback_subcategories(self):
        for category, options in EXPENSE_TAXONOMY.items():
            self.assertTrue(options, msg=f"{category} must define subcategories")
            has_fallback = any(opt.startswith("other") or opt == "other" for opt in options)
            self.assertTrue(has_fallback, msg=f"{category} must define fallback subcategory")


class AnnualIncomeApiTests(APITestCase):
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


class AnnualExpenseApiTests(APITestCase):
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


class BudgetSerializerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="budget_serializer_user", password="pass1234"
        )

    def test_income_serializer_normalizes_currency(self):
        serializer = AnnualIncomeEntrySerializer(
            data={
                "name": "Nomina",
                "category": "salary",
                "subcategory": "employee_salary",
                "income_type": "recurrent",
                "amount_annual": "12000.00",
                "fiscal_year": 2026,
                "currency": "eur",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["currency"], "EUR")
        self.assertEqual(serializer.validated_data["time_profile"], "structural_recurrent")
        self.assertEqual(serializer.validated_data["cashflow_role"], "operating")

    def test_income_serializer_rejects_invalid_amount_currency_and_year(self):
        serializer = AnnualIncomeEntrySerializer(
            data={
                "name": "Nomina",
                "category": "salary",
                "subcategory": "employee_salary",
                "income_type": "recurrent",
                "amount_annual": "0.00",
                "fiscal_year": 1800,
                "currency": "EURO",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("amount_annual", serializer.errors)
        self.assertIn("fiscal_year", serializer.errors)
        self.assertIn("currency", serializer.errors)

    def test_income_serializer_validates_partial_update_with_instance_values(self):
        entry = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category="salary",
            subcategory="employee_salary",
            income_type="recurrent",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        serializer = AnnualIncomeEntrySerializer(
            entry,
            data={"subcategory": "inheritance"},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_income_serializer_requires_term_end_year_for_term_recurrent(self):
        serializer = AnnualIncomeEntrySerializer(
            data={
                "name": "Bonus temporal",
                "category": "salary",
                "subcategory": "bonus_commission",
                "income_type": "recurrent",
                "time_profile": "term_recurrent",
                "amount_annual": "3000.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("term_end_year", serializer.errors)

    def test_expense_serializer_accepts_temporary_commitment_fields(self):
        serializer = AnnualExpenseEntrySerializer(
            data={
                "name": "Clinica fertilidad cuota",
                "category": "consumption_expenses",
                "subcategory": "financial_commitments",
                "expense_type": "recurrent",
                "time_profile": "term_recurrent",
                "cashflow_role": "temporary_commitment",
                "event_group": "fertilidad_2026",
                "term_end_year": 2027,
                "amount_annual": "12000.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["expense_type"], "recurrent")
        self.assertEqual(serializer.validated_data["cashflow_role"], "temporary_commitment")

    def test_expense_serializer_normalizes_term_recurrent_cashflow_role_to_temporary_commitment(
        self,
    ):
        serializer = AnnualExpenseEntrySerializer(
            data={
                "name": "Cuota coche",
                "category": "tangible_assets",
                "subcategory": "vehicle_purchase",
                "expense_type": "recurrent",
                "time_profile": "term_recurrent",
                "cashflow_role": "asset_purchase",
                "term_end_year": 2027,
                "amount_annual": "3600.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["cashflow_role"], "temporary_commitment")

    def test_expense_serializer_normalizes_invalid_structural_cashflow_role(self):
        serializer = AnnualExpenseEntrySerializer(
            data={
                "name": "Gasto hogar",
                "category": "consumption_expenses",
                "subcategory": "living_expenses",
                "expense_type": "recurrent",
                "time_profile": "structural_recurrent",
                "cashflow_role": "asset_purchase",
                "amount_annual": "1200.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["cashflow_role"], "operating")

    def test_expense_serializer_normalizes_invalid_one_off_cashflow_role(self):
        serializer = AnnualExpenseEntrySerializer(
            data={
                "name": "Evento puntual",
                "category": "consumption_expenses",
                "subcategory": "other_consumption_expenses",
                "expense_type": "one_off",
                "time_profile": "one_off",
                "cashflow_role": "temporary_commitment",
                "amount_annual": "400.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["cashflow_role"], "other")

    def test_expense_serializer_validates_partial_update_with_instance_values(self):
        entry = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Alimentacion",
            category="consumption_expenses",
            subcategory="living_expenses",
            expense_type="recurrent",
            amount_annual=Decimal("5500.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        serializer = AnnualExpenseEntrySerializer(
            entry,
            data={"subcategory": "crypto"},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
