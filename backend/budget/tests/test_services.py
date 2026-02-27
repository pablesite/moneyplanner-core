from django.core.exceptions import ValidationError
from django.test import TestCase

from budget.services import (
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
