from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from budget.serializers import AnnualExpenseEntrySerializer, AnnualIncomeEntrySerializer


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
                "target_month": 6,
                "amount_annual": "400.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["cashflow_role"], "other")

    def test_expense_serializer_requires_target_month_for_one_off(self):
        serializer = AnnualExpenseEntrySerializer(
            data={
                "name": "Seguro",
                "category": "consumption_expenses",
                "subcategory": "transport_mobility",
                "expense_type": "one_off",
                "time_profile": "one_off",
                "cashflow_role": "tax_fee",
                "amount_annual": "400.00",
                "fiscal_year": 2026,
                "currency": "EUR",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("target_month", serializer.errors)

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

    def test_expense_serializer_keeps_event_group_and_term_end_year_for_system_generated_liability(
        self,
    ):
        entry = AnnualExpenseEntry(
            user=self.user,
            source_liability_id=123,
            is_system_generated=True,
            name="Hipoteca",
            category="real_estate_assets",
            subcategory="mortgage_principal",
            expense_type="recurrent",
            time_profile="term_recurrent",
            cashflow_role="temporary_commitment",
            event_group="liability_123",
            term_end_year=2032,
            amount_annual=Decimal("7200.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        serializer = AnnualExpenseEntrySerializer(
            entry,
            data={
                "time_profile": "term_recurrent",
                "event_group": "manual_override",
                "term_end_year": 2040,
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["event_group"], "liability_123")
        self.assertEqual(serializer.validated_data["term_end_year"], 2032)
