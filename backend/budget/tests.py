from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AnnualIncomeEntry
from .services import INCOME_TAXONOMY, validate_annual_income_taxonomy


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
                "currency": "eur",
                "notes": "Nomina principal",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_res.data["currency"], "EUR")

        list_res = self.client.get("/api/budget/annual-income/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["name"], "CTN")

        totals_res = self.client.get("/api/budget/annual-income/totals/")
        self.assertEqual(totals_res.status_code, status.HTTP_200_OK)
        self.assertEqual(totals_res.data["total_annual"], "32460.00")

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
