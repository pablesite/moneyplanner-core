from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounting.services import (
    build_budget_derived_suggestions,
    build_monthly_accounting_summary,
    get_account_balance,
)
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

    def test_get_account_balance_can_be_cut_by_date_and_status(self):
        cash = LedgerAccount.objects.create(
            user=self.user,
            name="Caja",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        income = LedgerAccount.objects.create(
            user=self.user,
            name="Ventas",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        posted_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Cobro febrero",
            status=LedgerTransaction.Status.POSTED,
        )
        draft_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 5),
            value_date=date(2026, 3, 5),
            description="Borrador marzo",
            status=LedgerTransaction.Status.DRAFT,
        )
        for tx, amount in ((posted_tx, Decimal("1000.00")), (draft_tx, Decimal("300.00"))):
            LedgerEntry.objects.create(
                transaction=tx,
                account=cash,
                side=LedgerEntry.Side.DEBIT,
                amount=amount,
                currency="EUR",
            )
            LedgerEntry.objects.create(
                transaction=tx,
                account=income,
                side=LedgerEntry.Side.CREDIT,
                amount=amount,
                currency="EUR",
            )

        self.assertEqual(
            get_account_balance(
                account=cash,
                as_of_date=date(2026, 2, 28),
                status=LedgerTransaction.Status.POSTED,
            ),
            Decimal("1000.00"),
        )
        self.assertEqual(get_account_balance(account=cash), Decimal("1300.00"))

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

    def test_build_budget_derived_suggestions_returns_stable_monthly_series(self):
        income_plan = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("24000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        expense_plan = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Supermercado",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
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
        income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingreso",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gasto",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        tx_income_1 = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 12, 5),
            value_date=date(2025, 12, 5),
            description="Nomina dic",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_income_1,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1500.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_income_1,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1500.00"),
            currency="EUR",
            annual_income_entry=income_plan,
        )

        tx_income_2 = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 5),
            value_date=date(2026, 1, 5),
            description="Nomina ene",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_income_2,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1500.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_income_2,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1500.00"),
            currency="EUR",
            annual_income_entry=income_plan,
        )

        tx_expense = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 3),
            value_date=date(2026, 2, 3),
            description="Supermercado",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("400.00"),
            currency="EUR",
            annual_expense_entry=expense_plan,
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=cash,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("400.00"),
            currency="EUR",
        )

        suggestions = build_budget_derived_suggestions(
            user_id=self.user.id,
            fiscal_year=2026,
            lookback_years=2,
        )
        self.assertEqual(suggestions["window_months"], 24)
        self.assertEqual(len(suggestions["income"]["series"]), 24)
        self.assertEqual(len(suggestions["expense"]["series"]), 24)

        income_sub = suggestions["income"]["subcategories"][0]
        self.assertEqual(income_sub["category"], "salary")
        self.assertEqual(income_sub["subcategory"], "employee_salary")
        self.assertEqual(income_sub["window_total"], "3000.00")
        self.assertEqual(income_sub["suggested_annual"], "1500.00")
        self.assertEqual(income_sub["observed_months"], 2)

        expense_sub = suggestions["expense"]["subcategories"][0]
        self.assertEqual(expense_sub["category"], "consumption_expenses")
        self.assertEqual(expense_sub["subcategory"], "living_expenses")
        self.assertEqual(expense_sub["window_total"], "400.00")
        self.assertEqual(expense_sub["suggested_annual"], "200.00")
        self.assertEqual(expense_sub["observed_months"], 1)


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
                        "flow_family": "income",
                        "category_key": "salary",
                        "subcategory_key": "employee_salary",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        self.assertEqual(len(create_res.data["entries"]), 2)
        classified_entry = next(
            row for row in create_res.data["entries"] if row["account_id"] == self.income_account.id
        )
        self.assertEqual(classified_entry["flow_family"], "income")
        self.assertEqual(classified_entry["category_key"], "salary")
        self.assertEqual(classified_entry["subcategory_key"], "employee_salary")

        accounts_res = self.client.get("/api/accounting/accounts/")
        self.assertEqual(accounts_res.status_code, status.HTTP_200_OK)
        self.assertEqual(accounts_res.data[0]["current_balance"], "2100.00000000")

        entries_res = self.client.get("/api/accounting/entries/")
        self.assertEqual(entries_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(entries_res.data), 2)
        self.assertTrue(any(entry["flow_family"] == "income" for entry in entries_res.data))

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

    def test_account_delete_allows_unlinked_account_without_entries(self):
        transient_account = LedgerAccount.objects.create(
            user=self.user,
            name="Temporal",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            origin=LedgerAccount.Origin.USER,
        )

        response = self.client.delete(f"/api/accounting/accounts/{transient_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        self.assertFalse(LedgerAccount.objects.filter(id=transient_account.id).exists())

    def test_account_delete_removes_related_transactions_and_entries(self):
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 1),
            value_date=date(2026, 4, 1),
            description="Saldo inicial",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10.00"),
            currency="EUR",
        )

        response = self.client.delete(f"/api/accounting/accounts/{self.cash_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        self.assertFalse(LedgerAccount.objects.filter(id=self.cash_account.id).exists())
        self.assertEqual(LedgerEntry.objects.filter(transaction=tx).count(), 0)
        self.assertFalse(LedgerTransaction.objects.filter(id=tx.id).exists())

    def test_account_delete_unlinks_asset_accounting_reference(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Banco enlazado",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("100.00"),
            is_active=True,
        )
        linked_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta enlazada",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
            origin=LedgerAccount.Origin.USER,
        )

        response = self.client.delete(f"/api/accounting/accounts/{linked_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        asset.refresh_from_db()
        self.assertIsNone(asset.accounting_account_id)
        self.assertEqual(asset.tracking_mode, Asset.TrackingMode.MANUAL)

    def test_account_delete_unlinks_liability_accounting_reference(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Pasivo enlazado",
            category=Liability.Category.OTHER,
            tracking_mode=Liability.TrackingMode.ACCOUNTING,
            accounting_account_id=None,
            currency="EUR",
            annual_interest_tae=None,
            amount=Decimal("1000.00"),
            start_date=date(2026, 1, 1),
            is_active=True,
        )
        linked_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta pasivo enlazada",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
            origin=LedgerAccount.Origin.USER,
        )
        liability.accounting_account_id = linked_account.id
        liability.save(update_fields=["accounting_account_id"])

        response = self.client.delete(f"/api/accounting/accounts/{linked_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        liability.refresh_from_db()
        self.assertIsNone(liability.accounting_account_id)
        self.assertEqual(liability.tracking_mode, Liability.TrackingMode.MANUAL)

    def test_account_delete_rejects_system_accounts(self):
        system_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingreso: Nomina",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
        )

        response = self.client.delete(f"/api/accounting/accounts/{system_account.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("detail", response.data["error"]["details"])

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
        income_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] != self.cash_account.id
        )
        self.assertEqual(income_entry["flow_family"], "income")
        self.assertEqual(income_entry["category_key"], "salary")
        self.assertEqual(income_entry["subcategory_key"], "employee_salary")
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
        expense_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] != self.cash_account.id
        )
        self.assertEqual(expense_entry["flow_family"], "expense")
        self.assertEqual(expense_entry["category_key"], "consumption_expenses")
        self.assertEqual(expense_entry["subcategory_key"], "living_expenses")
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

    def test_quick_entry_rejects_partial_functional_classification(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-04-11",
                "value_date": "2026-04-11",
                "description": "Clasificacion incompleta",
                "amount": "90.00",
                "account_id": self.cash_account.id,
                "flow_family": "expense",
                "category_key": "consumption_expenses",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("subcategory_key", response.data["error"]["details"])

    def test_quick_entry_investment_purchase_creates_balanced_entries_with_asset_link(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Fondo indexado",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment_purchase",
                "booking_date": "2026-04-12",
                "value_date": "2026-04-12",
                "description": "Compra fondo abril",
                "amount": "250.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": investment_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data["entries"]), 2)
        debit_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == investment_account.id
        )
        self.assertEqual(debit_entry["side"], "debit")
        self.assertEqual(debit_entry["asset_id"], investment_asset.id)

    def test_quick_entry_debt_payment_creates_principal_and_interest_breakdown(self):
        expense_plan = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Intereses prestamo",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="financial_commitments",
            amount_annual=Decimal("1200.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo coche",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("8000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo prestamo coche",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        interest_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos financieros",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-18",
                "value_date": "2026-04-18",
                "description": "Cuota prestamo abril",
                "amount": "330.00",
                "principal_amount": "300.00",
                "interest_amount": "30.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "interest_account_id": interest_account.id,
                "annual_expense_entry_id": expense_plan.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(len(response.data["entries"]), 3)
        principal_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == liability_account.id
        )
        interest_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == interest_account.id
        )
        self.assertEqual(principal_entry["side"], "debit")
        self.assertEqual(principal_entry["liability_id"], liability.id)
        self.assertEqual(interest_entry["side"], "debit")
        self.assertEqual(interest_entry["annual_expense_entry_id"], expense_plan.id)
        self.assertEqual(interest_entry["flow_family"], "expense")
        self.assertEqual(interest_entry["category_key"], "consumption_expenses")
        self.assertEqual(interest_entry["subcategory_key"], "financial_commitments")

    def test_quick_entry_debt_payment_rejects_mismatched_total_breakdown(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo personal",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("2000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo prestamo personal",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        interest_account = LedgerAccount.objects.create(
            user=self.user,
            name="Intereses tarjeta",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-22",
                "value_date": "2026-04-22",
                "description": "Cuota invalida",
                "amount": "250.00",
                "principal_amount": "200.00",
                "interest_amount": "30.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "interest_account_id": interest_account.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("amount", response.data["error"]["details"])

    def test_account_balances_endpoint_returns_period_aggregates_for_liquidity_accounts(self):
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
            name="Compras",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            amount_annual=Decimal("2400.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        second_cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ahorro",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-01",
                "value_date": "2026-04-01",
                "description": "Nomina abril",
                "amount": "1000.00",
                "account_id": self.cash_account.id,
                "annual_income_entry_id": income_plan.id,
            },
            format="json",
        )
        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-04-05",
                "value_date": "2026-04-05",
                "description": "Compra abril",
                "amount": "200.00",
                "account_id": self.cash_account.id,
                "annual_expense_entry_id": expense_plan.id,
            },
            format="json",
        )
        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-10",
                "value_date": "2026-04-10",
                "description": "Mover ahorro",
                "amount": "300.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": second_cash_account.id,
            },
            format="json",
        )

        response = self.client.get(
            "/api/accounting/accounts/balances/?year=2026&month=4&account_type=asset"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["totals_by_account_type"]["asset"], "800.00")
        self.assertEqual(len(response.data["accounts"]), 2)

        first_account = next(
            row for row in response.data["accounts"] if row["account_id"] == self.cash_account.id
        )
        second_account = next(
            row for row in response.data["accounts"] if row["account_id"] == second_cash_account.id
        )

        self.assertEqual(first_account["current_balance"], "500.00000000")
        self.assertEqual(first_account["period_debit_total"], "1000.00")
        self.assertEqual(first_account["period_credit_total"], "500.00")
        self.assertEqual(first_account["period_net_change"], "500.00")

        self.assertEqual(second_account["current_balance"], "300.00000000")
        self.assertEqual(second_account["period_debit_total"], "300.00")
        self.assertEqual(second_account["period_credit_total"], "0.00")
        self.assertEqual(second_account["period_net_change"], "300.00")

    def test_account_balances_endpoint_requires_year_when_month_is_present(self):
        response = self.client.get("/api/accounting/accounts/balances/?month=4")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("year", response.data["error"]["details"])

    def test_budget_suggestions_endpoint_returns_historical_series(self):
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
            name="Alimentacion",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="living_expenses",
            amount_annual=Decimal("4800.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos hogar",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

        tx_income = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 10),
            value_date=date(2026, 1, 10),
            description="Nomina enero",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_income,
            account=self.cash_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_income,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            annual_income_entry=income_plan,
        )

        tx_expense = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Compra mensual",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("350.00"),
            currency="EUR",
            annual_expense_entry=expense_plan,
        )
        LedgerEntry.objects.create(
            transaction=tx_expense,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("350.00"),
            currency="EUR",
        )

        response = self.client.get("/api/accounting/transactions/budget-suggestions/?year=2026")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["fiscal_year"], 2026)
        self.assertEqual(response.data["lookback_years"], 2)
        self.assertEqual(response.data["window_months"], 24)
        self.assertEqual(len(response.data["income"]["series"]), 24)
        self.assertEqual(len(response.data["expense"]["series"]), 24)
        self.assertEqual(response.data["income"]["subcategories"][0]["category"], "salary")
        self.assertEqual(
            response.data["expense"]["subcategories"][0]["subcategory"],
            "living_expenses",
        )
