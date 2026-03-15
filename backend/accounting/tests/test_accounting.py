from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounting.services import build_monthly_accounting_summary, get_account_balance
from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from net_worth.models import Asset, Liability


class AccountingServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="acct_user", password="pass1234")

    def test_get_account_balance_uses_account_nature(self):
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Caja",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income = LedgerAccount.objects.create(
            user=self.user,
            name="Nomina",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Cobro",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )

        self.assertEqual(get_account_balance(account=cash), Decimal("1000.00"))
        self.assertEqual(get_account_balance(account=income), Decimal("1000.00"))

    def test_build_monthly_summary_aggregates_linked_budget_entries(self):
        income_plan = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        expense_plan = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Alquiler",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="housing_home",
            amount_annual=Decimal("7200.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        expense = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        tx_income = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 5),
            value_date=date(2026, 1, 5),
            description="Nomina enero",
        )
        LedgerEntry.objects.create(
            transaction=tx_income,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_income,
            account=income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            annual_income_entry=income_plan,
        )

        tx_expense = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 8),
            value_date=date(2026, 1, 8),
            description="Alquiler enero",
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=expense,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("600.00"),
            currency="EUR",
            annual_expense_entry=expense_plan,
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=cash,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("600.00"),
            currency="EUR",
        )

        summary = build_monthly_accounting_summary(user_id=self.user.id, fiscal_year=2026)
        january = summary["months"][0]
        self.assertEqual(january["income_total"], "1000.00")
        self.assertEqual(january["expense_total"], "600.00")


class AccountingApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="acct_api_user",
            password="pass1234",
        )
        self.client.force_authenticate(user=self.user)
        self.cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta corriente",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        self.income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos salariales",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )

    def test_create_balanced_transaction_and_list_entries(self):
        create_res = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-15",
                "value_date": "2026-02-15",
                "description": "Nomina febrero",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": self.cash_account.id,
                        "side": "debit",
                        "amount": "2100.00",
                        "currency": "eur",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "2100.00",
                        "currency": "EUR",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(len(create_res.data["entries"]), 2)

        accounts_res = self.client.get("/api/accounting/accounts/")
        self.assertEqual(accounts_res.status_code, status.HTTP_200_OK)
        self.assertEqual(accounts_res.data[0]["current_balance"], "2100.00000000")

        entries_res = self.client.get("/api/accounting/entries/")
        self.assertEqual(entries_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(entries_res.data), 2)

    def test_create_transaction_rejects_unbalanced_entries(self):
        response = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-15",
                "value_date": "2026-02-15",
                "description": "Asiento invalido",
                "entries": [
                    {
                        "account_id": self.cash_account.id,
                        "side": "debit",
                        "amount": "100.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "80.00",
                        "currency": "EUR",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("entries", response.data["error"]["details"])

    def test_account_create_validates_owned_asset_and_currency(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Banco",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("100.00"),
            is_active=True,
        )
        create_res = self.client.post(
            "/api/accounting/accounts/",
            {
                "name": "Cuenta liquidez",
                "account_type": "asset",
                "currency": "eur",
                "origin": "user",
                "asset_id": asset.id,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(create_res.data["asset_id"], asset.id)

    def test_queryset_is_user_scoped(self):
        other_user = get_user_model().objects.create_user(
            username="acct_other",
            password="pass1234",
        )
        other_account = LedgerAccount.objects.create(
            user=other_user,
            name="Otra cuenta",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=other_user,
            booking_date=date(2026, 1, 1),
            value_date=date(2026, 1, 1),
            description="Ajeno",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=other_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=other_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10.00"),
            currency="EUR",
        )

        accounts_res = self.client.get("/api/accounting/accounts/")
        transactions_res = self.client.get("/api/accounting/transactions/")
        entries_res = self.client.get("/api/accounting/entries/")

        self.assertEqual(accounts_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(accounts_res.data), 2)
        self.assertEqual(len(transactions_res.data), 0)
        self.assertEqual(len(entries_res.data), 0)

    def test_monthly_summary_endpoint(self):
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Vivienda",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        expense_entry = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Alquiler",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="housing_home",
            amount_annual=Decimal("8400.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 2),
            value_date=date(2026, 3, 2),
            description="Alquiler marzo",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("700.00"),
            currency="EUR",
            annual_expense_entry=expense_entry,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("700.00"),
            currency="EUR",
        )

        response = self.client.get("/api/accounting/transactions/monthly-summary/?year=2026")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["months"][2]["expense_total"], "700.00")

    def test_account_create_rejects_foreign_liability_reference(self):
        other_user = get_user_model().objects.create_user(
            username="liab_other",
            password="pass1234",
        )
        liability = Liability.objects.create(
            user=other_user,
            name="Prestamo ajeno",
            category=Liability.Category.OTHER,
            currency="EUR",
            amount=Decimal("50.00"),
        )
        response = self.client.post(
            "/api/accounting/accounts/",
            {
                "name": "Deuda",
                "account_type": "liability",
                "currency": "EUR",
                "liability_id": liability.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("liability_id", response.data["error"]["details"])

    def test_quick_entry_income_creates_balanced_transaction_with_system_income_account(self):
        income_plan = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("24000.00"),
            fiscal_year=2026,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-01",
                "value_date": "2026-04-01",
                "description": "Nomina abril",
                "amount": "2000.00",
                "account_id": self.cash_account.id,
                "annual_income_entry_id": income_plan.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data["entries"]), 2)
        self.assertTrue(
            LedgerAccount.objects.filter(
                user=self.user,
                account_type=LedgerAccount.AccountType.INCOME,
                origin=LedgerAccount.Origin.SYSTEM,
                name="Ingreso: Nomina",
            ).exists()
        )
        self.cash_account.refresh_from_db()
        self.assertEqual(
            LedgerEntry.objects.filter(transaction_id=response.data["id"]).count(),
            2,
        )
        self.assertEqual(
            self.client.get("/api/accounting/accounts/").data[0]["current_balance"], "2000.00000000"
        )

    def test_quick_entry_expense_uses_expense_counterpart_and_updates_monthly_summary(self):
        income_plan = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("18000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        expense_plan = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Supermercado",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            amount_annual=Decimal("3600.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-01",
                "value_date": "2026-04-01",
                "description": "Saldo inicial",
                "amount": "1500.00",
                "account_id": self.cash_account.id,
                "annual_income_entry_id": income_plan.id,
            },
            format="json",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-04-02",
                "value_date": "2026-04-02",
                "description": "Compra semanal",
                "amount": "120.00",
                "account_id": self.cash_account.id,
                "annual_expense_entry_id": expense_plan.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(
            LedgerAccount.objects.filter(
                user=self.user,
                account_type=LedgerAccount.AccountType.EXPENSE,
                origin=LedgerAccount.Origin.SYSTEM,
                name="Gasto: Supermercado",
            ).exists()
        )

        summary = self.client.get("/api/accounting/transactions/monthly-summary/?year=2026")
        self.assertEqual(summary.status_code, status.HTTP_200_OK, summary.data)
        self.assertEqual(summary.data["months"][3]["income_total"], "1500.00")
        self.assertEqual(summary.data["months"][3]["expense_total"], "120.00")

    def test_quick_entry_transfer_requires_different_liquidity_account(self):
        second_cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ahorro",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

        valid_response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-03",
                "value_date": "2026-04-03",
                "description": "Mover a ahorro",
                "amount": "300.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": second_cash_account.id,
            },
            format="json",
        )
        self.assertEqual(valid_response.status_code, status.HTTP_201_CREATED, valid_response.data)

        invalid_response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-03",
                "value_date": "2026-04-03",
                "description": "Duplicada",
                "amount": "10.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": self.cash_account.id,
            },
            format="json",
        )
        self.assertEqual(
            invalid_response.status_code, status.HTTP_400_BAD_REQUEST, invalid_response.data
        )
        self.assertIn("counterparty_account_id", invalid_response.data["error"]["details"])
