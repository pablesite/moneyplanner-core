from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from budget.models import (
    AnnualExpenseEntry,
    AnnualExpenseMonthlyCheckin,
    AnnualIncomeEntry,
    AnnualIncomeMonthlyCheckin,
)
from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction


class AnnualIncomeApiCheckinsTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="income_api_checkins_user", password="pass1234"
        )
        self.client.force_authenticate(user=self.user)

    def test_income_checkin_crud_and_monthly_summary(self):
        recurring = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category="salary",
            subcategory="employee_salary",
            income_type="recurrent",
            time_profile="structural_recurrent",
            amount_annual=Decimal("24000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        one_off = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Bonus",
            category="salary",
            subcategory="bonus_commission",
            income_type="one_off",
            time_profile="one_off",
            target_month=5,
            amount_annual=Decimal("3000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )

        create_checkin = self.client.post(
            "/api/budget/annual-income-checkins/",
            {
                "annual_income_entry_id": recurring.id,
                "fiscal_year": 2026,
                "month": 2,
                "status": "adjusted",
                "executed_amount": "2100.00",
                "note": "Pagas extraorrdinarias prorrateadas",
            },
            format="json",
        )
        self.assertEqual(create_checkin.status_code, status.HTTP_201_CREATED, create_checkin.data)
        self.assertEqual(create_checkin.data["executed_amount"], "2100.00")

        list_checkins = self.client.get("/api/budget/annual-income-checkins/?year=2026&month=2")
        self.assertEqual(list_checkins.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_checkins.data), 1)
        self.assertEqual(list_checkins.data[0]["annual_income_entry_id"], recurring.id)

        invalid_one_off = self.client.post(
            "/api/budget/annual-income-checkins/",
            {
                "annual_income_entry_id": one_off.id,
                "fiscal_year": 2026,
                "month": 4,
                "status": "confirmed",
                "executed_amount": "3000.00",
            },
            format="json",
        )
        self.assertEqual(invalid_one_off.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("month", invalid_one_off.data["error"]["details"])

        valid_one_off = self.client.post(
            "/api/budget/annual-income-checkins/",
            {
                "annual_income_entry_id": one_off.id,
                "fiscal_year": 2026,
                "month": 5,
                "status": "confirmed",
                "executed_amount": "3000.00",
            },
            format="json",
        )
        self.assertEqual(valid_one_off.status_code, status.HTTP_201_CREATED, valid_one_off.data)

        summary_res = self.client.get("/api/budget/annual-income/monthly-summary/?year=2026")
        self.assertEqual(summary_res.status_code, status.HTTP_200_OK)
        self.assertEqual(summary_res.data["planned_total"], "27000.00")
        self.assertEqual(summary_res.data["executed_total"], "5100.00")
        self.assertEqual(summary_res.data["pending_total"], "22000.00")
        months = {row["month"]: row for row in summary_res.data["months"]}
        self.assertEqual(months[2]["planned"], "2000.00")
        self.assertEqual(months[2]["executed"], "2100.00")
        self.assertEqual(months[2]["pending"], "0.00")
        self.assertEqual(months[5]["planned"], "5000.00")
        self.assertEqual(months[5]["executed"], "3000.00")
        self.assertEqual(months[5]["pending"], "2000.00")
        self.assertEqual(months[1]["planned"], "2000.00")
        self.assertEqual(months[1]["pending"], "2000.00")
        self.assertTrue(summary_res.data["has_executed_data"])

    def test_income_checkin_skipped_nulls_executed_amount(self):
        income = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Alquiler",
            category="passive_income",
            subcategory="real_estate_rent",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        res = self.client.post(
            "/api/budget/annual-income-checkins/",
            {
                "annual_income_entry_id": income.id,
                "fiscal_year": 2026,
                "month": 3,
                "status": "skipped",
                "executed_amount": "10.00",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertIsNone(res.data["executed_amount"])
        self.assertIsNone(AnnualIncomeMonthlyCheckin.objects.get(id=res.data["id"]).executed_amount)

    def test_income_checkin_update_preserves_and_clears_confirmed_at_by_status(self):
        income = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        create_res = self.client.post(
            "/api/budget/annual-income-checkins/",
            {
                "annual_income_entry_id": income.id,
                "fiscal_year": 2026,
                "month": 2,
                "status": "confirmed",
                "executed_amount": "1000.00",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertIsNotNone(create_res.data["confirmed_at"])
        checkin_id = create_res.data["id"]

        skipped_res = self.client.patch(
            f"/api/budget/annual-income-checkins/{checkin_id}/",
            {"status": "skipped"},
            format="json",
        )
        self.assertEqual(skipped_res.status_code, status.HTTP_200_OK, skipped_res.data)
        self.assertIsNone(skipped_res.data["confirmed_at"])

        adjusted_res = self.client.patch(
            f"/api/budget/annual-income-checkins/{checkin_id}/",
            {"status": "adjusted", "executed_amount": "950.00"},
            format="json",
        )
        self.assertEqual(adjusted_res.status_code, status.HTTP_200_OK, adjusted_res.data)
        self.assertIsNotNone(adjusted_res.data["confirmed_at"])
        self.assertEqual(adjusted_res.data["executed_amount"], "950.00")

    def test_income_monthly_summary_requires_year_with_canonical_error_shape(self):
        response = self.client.get("/api/budget/annual-income/monthly-summary/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("year", response.data["error"]["details"])

    def test_income_monthly_summary_invalid_year_uses_canonical_error_shape(self):
        response = self.client.get("/api/budget/annual-income/monthly-summary/?year=nope")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("year", response.data["error"]["details"])

    def test_income_monthly_summary_prefers_categorized_ledger_and_reports_mixed_coverage(self):
        recurring = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("24000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        AnnualIncomeMonthlyCheckin.objects.create(
            user=self.user,
            annual_income_entry=recurring,
            fiscal_year=2026,
            month=2,
            status="adjusted",
            executed_amount=Decimal("1950.00"),
        )
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 31),
            value_date=date(2026, 1, 31),
            description="Nomina enero",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("2000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("2000.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="salary",
            subcategory_key="employee_salary",
        )

        response = self.client.get("/api/budget/annual-income/monthly-summary/?year=2026")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["executed_total"], "3950.00")
        self.assertEqual(response.data["months_with_ledger"], 1)
        self.assertEqual(response.data["months_with_fallback"], 1)
        self.assertEqual(response.data["coverage_mode"], "mixed")
        months = {row["month"]: row for row in response.data["months"]}
        self.assertEqual(months[1]["executed"], "2000.00")
        self.assertEqual(months[1]["coverage_mode"], "ledger")
        self.assertEqual(months[2]["executed"], "1950.00")
        self.assertEqual(months[2]["coverage_mode"], "checkin")

    def test_income_monthly_summary_uses_legacy_link_as_fallback_when_new_classification_missing(
        self,
    ):
        recurring = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category="salary",
            subcategory="employee_salary",
            amount_annual=Decimal("24000.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 31),
            value_date=date(2026, 1, 31),
            description="Nomina enero",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("2000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("2000.00"),
            currency="EUR",
            annual_income_entry=recurring,
        )

        response = self.client.get("/api/budget/annual-income/monthly-summary/?year=2026")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["executed_total"], "2000.00")
        self.assertFalse(response.data["has_ledger_data"])
        self.assertEqual(response.data["months_with_fallback"], 1)
        self.assertEqual(response.data["coverage_mode"], "checkin")
        months = {row["month"]: row for row in response.data["months"]}
        self.assertEqual(months[1]["executed"], "2000.00")
        self.assertEqual(months[1]["coverage_mode"], "checkin")


class AnnualExpenseApiCheckinsTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="expense_api_checkins_user", password="pass1234"
        )
        self.client.force_authenticate(user=self.user)

    def test_expense_checkin_crud_and_monthly_summary(self):
        recurring = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Supermercado",
            category="consumption_expenses",
            subcategory="living_expenses",
            expense_type="recurrent",
            time_profile="structural_recurrent",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        one_off = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Seguro anual",
            category="consumption_expenses",
            subcategory="transport_mobility",
            expense_type="one_off",
            time_profile="one_off",
            target_month=3,
            amount_annual=Decimal("600.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )

        create_checkin_1 = self.client.post(
            "/api/budget/annual-expense-checkins/",
            {
                "annual_expense_entry_id": recurring.id,
                "fiscal_year": 2026,
                "month": 1,
                "status": "confirmed",
                "executed_amount": "110.00",
                "note": "Ajuste enero",
            },
            format="json",
        )
        self.assertEqual(
            create_checkin_1.status_code, status.HTTP_201_CREATED, create_checkin_1.data
        )
        self.assertEqual(create_checkin_1.data["executed_amount"], "110.00")

        create_checkin_2 = self.client.post(
            "/api/budget/annual-expense-checkins/",
            {
                "annual_expense_entry_id": one_off.id,
                "fiscal_year": 2026,
                "month": 3,
                "status": "adjusted",
                "executed_amount": "650.00",
            },
            format="json",
        )
        self.assertEqual(
            create_checkin_2.status_code, status.HTTP_201_CREATED, create_checkin_2.data
        )

        invalid_one_off_month = self.client.post(
            "/api/budget/annual-expense-checkins/",
            {
                "annual_expense_entry_id": one_off.id,
                "fiscal_year": 2026,
                "month": 4,
                "status": "confirmed",
                "executed_amount": "600.00",
            },
            format="json",
        )
        self.assertEqual(invalid_one_off_month.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("month", invalid_one_off_month.data["error"]["details"])

        list_checkins = self.client.get("/api/budget/annual-expense-checkins/?year=2026")
        self.assertEqual(list_checkins.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_checkins.data), 2)

        summary_res = self.client.get("/api/budget/annual-expense/monthly-summary/?year=2026")
        self.assertEqual(summary_res.status_code, status.HTTP_200_OK)
        self.assertEqual(summary_res.data["planned_total"], "1800.00")
        self.assertEqual(summary_res.data["executed_total"], "760.00")
        self.assertEqual(summary_res.data["pending_total"], "1100.00")
        months = {row["month"]: row for row in summary_res.data["months"]}
        self.assertEqual(months[1]["planned"], "100.00")
        self.assertEqual(months[1]["executed"], "110.00")
        self.assertEqual(months[1]["pending"], "0.00")
        self.assertEqual(months[3]["planned"], "700.00")
        self.assertEqual(months[3]["executed"], "650.00")
        self.assertEqual(months[3]["pending"], "100.00")
        self.assertTrue(summary_res.data["has_executed_data"])

    def test_expense_checkin_skipped_nulls_executed_amount(self):
        expense = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Gym",
            category="consumption_expenses",
            subcategory="health_wellbeing",
            amount_annual=Decimal("480.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        res = self.client.post(
            "/api/budget/annual-expense-checkins/",
            {
                "annual_expense_entry_id": expense.id,
                "fiscal_year": 2026,
                "month": 2,
                "status": "skipped",
                "executed_amount": "10.00",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertIsNone(res.data["executed_amount"])
        self.assertEqual(
            AnnualExpenseMonthlyCheckin.objects.get(id=res.data["id"]).executed_amount,
            None,
        )

    def test_expense_checkin_update_preserves_and_clears_confirmed_at_by_status(self):
        expense = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Supermercado",
            category="consumption_expenses",
            subcategory="living_expenses",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        create_res = self.client.post(
            "/api/budget/annual-expense-checkins/",
            {
                "annual_expense_entry_id": expense.id,
                "fiscal_year": 2026,
                "month": 2,
                "status": "confirmed",
                "executed_amount": "100.00",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertIsNotNone(create_res.data["confirmed_at"])
        checkin_id = create_res.data["id"]

        skipped_res = self.client.patch(
            f"/api/budget/annual-expense-checkins/{checkin_id}/",
            {"status": "skipped"},
            format="json",
        )
        self.assertEqual(skipped_res.status_code, status.HTTP_200_OK, skipped_res.data)
        self.assertIsNone(skipped_res.data["confirmed_at"])

        adjusted_res = self.client.patch(
            f"/api/budget/annual-expense-checkins/{checkin_id}/",
            {"status": "adjusted", "executed_amount": "95.00"},
            format="json",
        )
        self.assertEqual(adjusted_res.status_code, status.HTTP_200_OK, adjusted_res.data)
        self.assertIsNotNone(adjusted_res.data["confirmed_at"])
        self.assertEqual(adjusted_res.data["executed_amount"], "95.00")

    def test_expense_monthly_summary_requires_year_with_canonical_error_shape(self):
        response = self.client.get("/api/budget/annual-expense/monthly-summary/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("year", response.data["error"]["details"])

    def test_expense_monthly_summary_invalid_year_uses_canonical_error_shape(self):
        response = self.client.get("/api/budget/annual-expense/monthly-summary/?year=nope")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertIn("year", response.data["error"]["details"])

    def test_expense_monthly_summary_prefers_categorized_ledger_over_checkin_for_same_slot(self):
        expense = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Supermercado",
            category="consumption_expenses",
            subcategory="living_expenses",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
            is_active=True,
        )
        AnnualExpenseMonthlyCheckin.objects.create(
            user=self.user,
            annual_expense_entry=expense,
            fiscal_year=2026,
            month=3,
            status="adjusted",
            executed_amount=Decimal("90.00"),
        )
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 15),
            value_date=date(2026, 3, 15),
            description="Compra marzo",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("120.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="living_expenses",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=cash,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("120.00"),
            currency="EUR",
        )

        response = self.client.get("/api/budget/annual-expense/monthly-summary/?year=2026")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["executed_total"], "120.00")
        self.assertTrue(response.data["has_ledger_data"])
        self.assertEqual(response.data["coverage_mode"], "ledger")
        month = next(row for row in response.data["months"] if row["month"] == 3)
        self.assertEqual(month["executed"], "120.00")
        self.assertEqual(month["ledger_confirmed"], 1)
        self.assertEqual(month["fallback_confirmed"], 0)
        self.assertEqual(month["coverage_mode"], "ledger")
