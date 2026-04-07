import json
from io import StringIO
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounting.services_budget import (
    backfill_ledger_entry_classification,
    build_budget_derived_suggestions,
)
from accounting.services_ledger import (
    ensure_net_worth_opening_balance_transaction,
    get_account_balance,
)
from accounting.services_summaries import (
    build_account_balances_summary,
    build_monthly_accounting_summary,
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

    def test_backfill_ledger_entry_classification_copies_legacy_income_and_expense_links(self):
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
        income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        income_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 5),
            value_date=date(2026, 1, 5),
            description="Ingreso legacy",
        )
        income_entry = LedgerEntry.objects.create(
            transaction=income_tx,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            annual_income_entry=income_plan,
        )
        LedgerEntry.objects.create(
            transaction=income_tx,
            account=cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        expense_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 1, 8),
            value_date=date(2026, 1, 8),
            description="Gasto legacy",
        )
        expense_entry = LedgerEntry.objects.create(
            transaction=expense_tx,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("600.00"),
            currency="EUR",
            annual_expense_entry=expense_plan,
        )
        LedgerEntry.objects.create(
            transaction=expense_tx,
            account=cash,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("600.00"),
            currency="EUR",
        )

        result = backfill_ledger_entry_classification(user_id=self.user.id)

        income_entry.refresh_from_db()
        expense_entry.refresh_from_db()
        self.assertEqual(result.scanned, 2)
        self.assertEqual(result.updated, 2)
        self.assertEqual(result.ambiguous, 0)
        self.assertEqual(income_entry.flow_family, LedgerEntry.FlowFamily.INCOME)
        self.assertEqual(income_entry.category_key, "salary")
        self.assertEqual(income_entry.subcategory_key, "employee_salary")
        self.assertEqual(expense_entry.flow_family, LedgerEntry.FlowFamily.EXPENSE)
        self.assertEqual(expense_entry.category_key, "consumption_expenses")
        self.assertEqual(expense_entry.subcategory_key, "housing_home")

    def test_backfill_ledger_entry_classification_reports_ambiguous_partial_rows(self):
        income_plan = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
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
            booking_date=date(2026, 2, 1),
            value_date=date(2026, 2, 1),
            description="Incompleto",
        )
        entry = LedgerEntry.objects.create(
            transaction=tx,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            annual_income_entry=income_plan,
            category_key="salary",
        )

        result = backfill_ledger_entry_classification(user_id=self.user.id)

        entry.refresh_from_db()
        self.assertEqual(result.scanned, 1)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.ambiguous, 1)
        self.assertEqual(result.ambiguous_reasons, {"partial_new_classification": 1})
        self.assertEqual(entry.flow_family, "")
        self.assertEqual(entry.category_key, "salary")
        self.assertEqual(entry.subcategory_key, "")

    def test_backfill_ledger_entry_classification_supports_dry_run(self):
        income_plan = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
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
            booking_date=date(2026, 3, 1),
            value_date=date(2026, 3, 1),
            description="Dry run",
        )
        entry = LedgerEntry.objects.create(
            transaction=tx,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            annual_income_entry=income_plan,
        )

        result = backfill_ledger_entry_classification(user_id=self.user.id, dry_run=True)

        entry.refresh_from_db()
        self.assertTrue(result.dry_run)
        self.assertEqual(result.updated, 1)
        self.assertEqual(entry.flow_family, "")
        self.assertEqual(entry.category_key, "")
        self.assertEqual(entry.subcategory_key, "")

    def test_management_command_backfill_ledger_classification_prints_summary(self):
        income_plan = AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
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
            booking_date=date(2026, 4, 1),
            value_date=date(2026, 4, 1),
            description="Cmd",
        )
        entry = LedgerEntry.objects.create(
            transaction=tx,
            account=income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1200.00"),
            currency="EUR",
            annual_income_entry=income_plan,
        )
        stdout = StringIO()

        call_command(
            "backfill_ledger_classification",
            "--user-id",
            str(self.user.id),
            stdout=stdout,
        )

        entry.refresh_from_db()
        output = stdout.getvalue()
        self.assertIn("[APPLIED] scanned=1 updated=1 already_classified=0 ambiguous=0", output)
        self.assertIn("ambiguous_reasons: none", output)
        self.assertEqual(entry.flow_family, LedgerEntry.FlowFamily.INCOME)

    def test_build_monthly_summary_aggregates_category_first_entries(self):
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
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
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="salary",
            subcategory_key="employee_salary",
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
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="housing_home",
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

    def test_build_budget_derived_suggestions_returns_stable_monthly_series_from_ledger_taxonomy(
        self,
    ):
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("24000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
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
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="salary",
            subcategory_key="employee_salary",
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
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="salary",
            subcategory_key="employee_salary",
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
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="living_expenses",
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

    def test_build_account_balances_summary_handles_multiple_accounts_and_foreign_currency(self):
        euro_cash = LedgerAccount.objects.create(
            user=self.user,
            name="Caja EUR",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        euro_income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos EUR",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        usd_cash = LedgerAccount.objects.create(
            user=self.user,
            name="Caja USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )
        usd_income = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos USD",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="USD",
        )

        euro_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 3),
            value_date=date(2026, 4, 3),
            description="Ingreso EUR",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=euro_tx,
            account=euro_cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=euro_tx,
            account=euro_income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )

        usd_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 4),
            value_date=date(2026, 4, 4),
            description="Ingreso USD",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=usd_tx,
            account=usd_cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("250.00"),
            currency="USD",
        )
        LedgerEntry.objects.create(
            transaction=usd_tx,
            account=usd_income,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("250.00"),
            currency="USD",
        )

        summary = build_account_balances_summary(
            user_id=self.user.id,
            fiscal_year=2026,
            month=4,
            account_type=LedgerAccount.AccountType.ASSET,
        )

        self.assertEqual(summary["filters"]["year"], 2026)
        self.assertEqual(summary["filters"]["month"], 4)
        self.assertEqual(summary["filters"]["account_type"], LedgerAccount.AccountType.ASSET)
        self.assertEqual(summary["totals_by_account_type"]["asset"], "1250.00")
        self.assertEqual(len(summary["accounts"]), 2)

        accounts_by_id = {row["account_id"]: row for row in summary["accounts"]}
        self.assertEqual(accounts_by_id[euro_cash.id]["currency"], "EUR")
        self.assertEqual(accounts_by_id[euro_cash.id]["current_balance"], "1000.00000000")
        self.assertEqual(accounts_by_id[euro_cash.id]["period_net_change"], "1000.00")
        self.assertEqual(accounts_by_id[usd_cash.id]["currency"], "USD")
        self.assertEqual(accounts_by_id[usd_cash.id]["current_balance"], "250.00000000")
        self.assertEqual(accounts_by_id[usd_cash.id]["period_net_change"], "250.00")

    def test_build_account_balances_summary_with_accounts_of_different_types(self):
        asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Caja",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Tarjeta",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
        )

        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 5, 12),
            value_date=date(2026, 5, 12),
            description="Movimiento mixto",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=asset_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("500.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=liability_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("200.00"),
            currency="EUR",
        )

        summary = build_account_balances_summary(
            user_id=self.user.id,
            fiscal_year=2026,
            month=5,
        )

        accounts_by_id = {row["account_id"]: row for row in summary["accounts"]}
        self.assertEqual(summary["totals_by_account_type"]["asset"], "500.00")
        self.assertEqual(summary["totals_by_account_type"]["liability"], "200.00")
        self.assertEqual(accounts_by_id[asset_account.id]["current_balance"], "500.00000000")
        self.assertEqual(accounts_by_id[liability_account.id]["current_balance"], "200.00000000")

    def test_build_account_balances_summary_includes_foreign_currency_accounts(self):
        usd_cash = LedgerAccount.objects.create(
            user=self.user,
            name="Caja USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )

        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 6, 7),
            value_date=date(2026, 6, 7),
            description="Ingreso USD",
            status=LedgerTransaction.Status.POSTED,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=usd_cash,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("125.00"),
            currency="USD",
        )

        summary = build_account_balances_summary(
            user_id=self.user.id,
            fiscal_year=2026,
            month=6,
        )

        self.assertEqual(len(summary["accounts"]), 1)
        self.assertEqual(summary["accounts"][0]["currency"], "USD")
        self.assertEqual(summary["accounts"][0]["current_balance"], "125.00000000")

    def test_build_account_balances_summary_includes_investment_contributed_totals(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Cartera indexada",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("0.00"),
            is_active=True,
        )
        cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta corriente",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker indexado",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )

        tx_inflow = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 6, 1),
            value_date=date(2026, 6, 1),
            description="Aporte cartera",
            status=LedgerTransaction.Status.POSTED,
            quick_entry_kind="investment",
            investment_direction="inflow",
        )
        LedgerEntry.objects.create(
            transaction=tx_inflow,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("500.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=tx_inflow,
            account=cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("500.00"),
            currency="EUR",
        )

        tx_outflow = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 6, 20),
            value_date=date(2026, 6, 20),
            description="Desinversion parcial",
            status=LedgerTransaction.Status.POSTED,
            quick_entry_kind="investment",
            investment_direction="outflow",
        )
        LedgerEntry.objects.create(
            transaction=tx_outflow,
            account=cash_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("200.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx_outflow,
            account=investment_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("200.00"),
            currency="EUR",
            asset=investment_asset,
        )

        summary = build_account_balances_summary(
            user_id=self.user.id,
            fiscal_year=2026,
            month=6,
            account_type=LedgerAccount.AccountType.ASSET,
        )
        by_id = {row["account_id"]: row for row in summary["accounts"]}
        investment_row = by_id[investment_account.id]
        self.assertEqual(investment_row["investment_inflow_total"], "500.00")
        self.assertEqual(investment_row["investment_outflow_total"], "200.00")
        self.assertEqual(investment_row["investment_net_contributed"], "300.00")

    def test_ensure_net_worth_opening_balance_transaction_creates_once_and_is_idempotent(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Vivienda",
            category=Asset.Category.REAL_ESTATE,
            subcategory=Asset.Subcategory.PRIMARY_HOME,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1234.56"),
            is_active=True,
        )
        account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta vivienda",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )

        first_transaction = ensure_net_worth_opening_balance_transaction(
            user=self.user,
            account=account,
            amount=Decimal("1234.56"),
            booking_date=date(2026, 1, 15),
            asset=asset,
        )
        second_transaction = ensure_net_worth_opening_balance_transaction(
            user=self.user,
            account=account,
            amount=Decimal("1234.56"),
            booking_date=date(2026, 1, 15),
            asset=asset,
        )

        self.assertIsNotNone(first_transaction)
        self.assertEqual(first_transaction.id, second_transaction.id)
        self.assertEqual(
            LedgerTransaction.objects.filter(
                user=self.user,
                origin=LedgerTransaction.Origin.SYSTEM,
                notes=f"net_worth_opening_balance:asset:{asset.id}",
            ).count(),
            1,
        )
        self.assertEqual(LedgerEntry.objects.filter(transaction=first_transaction).count(), 2)
        self.assertTrue(
            LedgerEntry.objects.filter(transaction=first_transaction, account=account).exists()
        )
        self.assertTrue(
            LedgerAccount.objects.filter(
                user=self.user,
                account_type=LedgerAccount.AccountType.EQUITY,
                origin=LedgerAccount.Origin.SYSTEM,
            ).exists()
        )


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

    def test_create_transaction_updates_accounting_asset_start_date_when_booking_is_earlier(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            currency="EUR",
            start_date=date(2026, 1, 1),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Bitcoin account",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        asset.accounting_account_id = investment_account.id
        asset.save(update_fields=["accounting_account_id", "updated_at"])

        response = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2025-10-09",
                "value_date": "2025-10-09",
                "description": "Movimiento antiguo",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": investment_account.id,
                        "side": "debit",
                        "amount": "300.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "300.00",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "capital_gains",
                        "subcategory_key": "sale_financial_assets",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        asset.refresh_from_db()
        self.assertEqual(asset.start_date, date(2025, 10, 9))

    def test_update_transaction_updates_accounting_asset_start_date_when_booking_is_earlier(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            currency="EUR",
            start_date=date(2026, 1, 1),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Bitcoin account",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        asset.accounting_account_id = investment_account.id
        asset.save(update_fields=["accounting_account_id", "updated_at"])

        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 2, 10),
            value_date=date(2026, 2, 10),
            description="Movimiento reciente",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.MANUAL,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("100.00"),
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("100.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

        response = self.client.patch(
            f"/api/accounting/transactions/{tx.id}/",
            {
                "booking_date": "2025-08-15",
                "value_date": "2025-08-15",
                "description": "Movimiento corregido",
                "entries": [
                    {
                        "account_id": investment_account.id,
                        "side": "debit",
                        "amount": "120.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "120.00",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "capital_gains",
                        "subcategory_key": "sale_financial_assets",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        asset.refresh_from_db()
        self.assertEqual(asset.start_date, date(2025, 8, 15))

    def test_update_legacy_multicurrency_transaction_allows_amount_change_with_same_structure(self):
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="Bitcoin",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 10, 9),
            value_date=date(2025, 10, 9),
            description="ST Criptos",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.IMPORT,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INCOME,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=btc_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("0.00283275"),
            currency="BTC",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("300.90"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

        response = self.client.patch(
            f"/api/accounting/transactions/{tx.id}/",
            {
                "booking_date": "2025-10-09",
                "value_date": "2025-10-09",
                "description": "ST Criptos",
                "entries": [
                    {
                        "account_id": btc_account.id,
                        "side": "debit",
                        "amount": "0.00250000",
                        "currency": "BTC",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "265.56",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "capital_gains",
                        "subcategory_key": "sale_financial_assets",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        tx.refresh_from_db()
        btc_entry = tx.entries.get(account=btc_account)
        eur_entry = tx.entries.get(account=self.income_account)
        self.assertEqual(btc_entry.amount, Decimal("0.00250000"))
        self.assertEqual(eur_entry.amount, Decimal("265.56000000"))

    def test_update_investment_allows_cross_currency_structure_change(self):
        btc_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("0.01000000"),
            is_active=True,
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="BTC wallet",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=btc_asset,
        )
        usd_liquidity = LedgerAccount.objects.create(
            user=self.user,
            name="Spot Binance USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 8, 19),
            value_date=date(2025, 8, 19),
            description="ST Criptos",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.IMPORT,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.INFLOW,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=btc_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("0.00013201"),
            currency="BTC",
            asset=btc_asset,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("12.80000000"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

        response = self.client.patch(
            f"/api/accounting/transactions/{tx.id}/",
            {
                "booking_date": "2025-08-19",
                "value_date": "2025-08-19",
                "description": "ST Criptos",
                "quick_entry_kind": "investment",
                "investment_direction": "inflow",
                "entries": [
                    {
                        "account_id": btc_account.id,
                        "side": "debit",
                        "amount": "0.00013201",
                        "currency": "BTC",
                        "asset_id": btc_asset.id,
                    },
                    {
                        "account_id": usd_liquidity.id,
                        "side": "credit",
                        "amount": "14.94",
                        "currency": "USD",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        tx.refresh_from_db()
        self.assertEqual(tx.quick_entry_kind, LedgerTransaction.QuickEntryKind.INVESTMENT)
        self.assertEqual(tx.investment_direction, LedgerTransaction.InvestmentDirection.INFLOW)
        btc_entry = tx.entries.get(account=btc_account)
        usd_entry = tx.entries.get(account=usd_liquidity)
        self.assertEqual(btc_entry.currency, "BTC")
        self.assertEqual(btc_entry.amount, Decimal("0.00013201"))
        self.assertEqual(usd_entry.currency, "USD")
        self.assertEqual(usd_entry.amount, Decimal("14.94000000"))

    def test_update_transfer_allows_cross_currency_structure_change(self):
        eth_account = LedgerAccount.objects.create(
            user=self.user,
            name="MetaMask ETH",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="ETH",
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="Binance BTC",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2025, 10, 17),
            value_date=date(2025, 10, 17),
            description="Swap cripto",
            status=LedgerTransaction.Status.POSTED,
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("50.00000000"),
            currency="EUR",
        )
        eur_destination = LedgerAccount.objects.create(
            user=self.user,
            name="Destino EUR inicial",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=eur_destination,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("50.00000000"),
            currency="EUR",
        )

        response = self.client.patch(
            f"/api/accounting/transactions/{tx.id}/",
            {
                "booking_date": "2025-10-17",
                "value_date": "2025-10-17",
                "description": "Swap cripto",
                "quick_entry_kind": "transfer",
                "entries": [
                    {
                        "account_id": eth_account.id,
                        "side": "credit",
                        "amount": "0.11000000",
                        "currency": "ETH",
                    },
                    {
                        "account_id": btc_account.id,
                        "side": "debit",
                        "amount": "0.00395872",
                        "currency": "BTC",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        tx.refresh_from_db()
        eth_entry = tx.entries.get(account=eth_account)
        btc_entry = tx.entries.get(account=btc_account)
        self.assertEqual(eth_entry.currency, "ETH")
        self.assertEqual(eth_entry.amount, Decimal("0.11000000"))
        self.assertEqual(btc_entry.currency, "BTC")
        self.assertEqual(btc_entry.amount, Decimal("0.00395872"))

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
        self.assertEqual(len(transactions_res.data["results"]), 0)
        self.assertEqual(transactions_res.data["total_count"], 0)
        self.assertIsNone(transactions_res.data["next_cursor"])
        self.assertEqual(len(entries_res.data), 0)

    def test_transactions_list_returns_cursor_envelope_and_activity_kind(self):
        for booking_date, description in (
            ("2026-02-10", "Nomina"),
            ("2026-02-09", "Nomina extra"),
            ("2026-02-08", "Nomina variable"),
        ):
            create_res = self.client.post(
                "/api/accounting/transactions/",
                {
                    "booking_date": booking_date,
                    "value_date": booking_date,
                    "description": description,
                    "status": "posted",
                    "origin": "manual",
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
                            "amount": "100.00",
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

        first_page = self.client.get("/api/accounting/transactions/?page_size=2")
        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(first_page.data["results"]), 2)
        self.assertEqual(first_page.data["total_count"], 3)
        self.assertIsNotNone(first_page.data["next_cursor"])
        self.assertTrue(all("activity_kind" in row for row in first_page.data["results"]))
        self.assertTrue(all(row["activity_kind"] == "income" for row in first_page.data["results"]))

        second_page = self.client.get(
            f"/api/accounting/transactions/?page_size=2&cursor={first_page.data['next_cursor']}"
        )
        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second_page.data["results"]), 1)
        self.assertIsNone(second_page.data["next_cursor"])
        first_page_ids = {row["id"] for row in first_page.data["results"]}
        second_page_ids = {row["id"] for row in second_page.data["results"]}
        self.assertTrue(first_page_ids.isdisjoint(second_page_ids))

    def test_transactions_list_filters_support_combination(self):
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Supermercado",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        savings_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta ahorro",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        create_income = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-10",
                "value_date": "2026-02-10",
                "description": "Nomina febrero",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": self.cash_account.id,
                        "side": "debit",
                        "amount": "2000.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": self.income_account.id,
                        "side": "credit",
                        "amount": "2000.00",
                        "currency": "EUR",
                        "flow_family": "income",
                        "category_key": "salary",
                        "subcategory_key": "employee_salary",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_income.status_code, status.HTTP_201_CREATED, create_income.data)
        create_expense = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-09",
                "value_date": "2026-02-09",
                "description": "Compra supermercado",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": expense_account.id,
                        "side": "debit",
                        "amount": "120.00",
                        "currency": "EUR",
                        "flow_family": "expense",
                        "category_key": "consumption_expenses",
                        "subcategory_key": "housing_home",
                    },
                    {
                        "account_id": self.cash_account.id,
                        "side": "credit",
                        "amount": "120.00",
                        "currency": "EUR",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_expense.status_code, status.HTTP_201_CREATED, create_expense.data)
        create_transfer = self.client.post(
            "/api/accounting/transactions/",
            {
                "booking_date": "2026-02-08",
                "value_date": "2026-02-08",
                "description": "Transferencia ahorro",
                "status": "posted",
                "origin": "manual",
                "entries": [
                    {
                        "account_id": self.cash_account.id,
                        "side": "credit",
                        "amount": "300.00",
                        "currency": "EUR",
                    },
                    {
                        "account_id": savings_account.id,
                        "side": "debit",
                        "amount": "300.00",
                        "currency": "EUR",
                    },
                ],
            },
            format="json",
        )
        self.assertEqual(create_transfer.status_code, status.HTTP_201_CREATED, create_transfer.data)

        filtered = self.client.get(
            "/api/accounting/transactions/?kind=expense&query=super&date_from=2026-02-09&date_to=2026-02-10"
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["total_count"], 1)
        self.assertEqual(filtered.data["results"][0]["activity_kind"], "expense")

        by_account = self.client.get(
            f"/api/accounting/transactions/?account_id={savings_account.id}"
        )
        self.assertEqual(by_account.status_code, status.HTTP_200_OK)
        self.assertEqual(by_account.data["total_count"], 1)
        self.assertEqual(by_account.data["results"][0]["description"], "Transferencia ahorro")

    def test_transactions_list_kind_investment_purchase_excludes_revaluation(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Cartera indexada",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("1000.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker cartera",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto tecnico",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
        )
        investment_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 17),
            value_date=date(2026, 3, 17),
            description="Aporte broker marzo",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
        )
        LedgerEntry.objects.create(
            transaction=investment_tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("30.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=investment_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("30.00"),
            currency="EUR",
        )
        transfer_tagged_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 17),
            value_date=date(2026, 3, 17),
            description="Transfer mal etiquetada sobre inversion",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
        )
        LedgerEntry.objects.create(
            transaction=transfer_tagged_tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("22.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=transfer_tagged_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("22.00"),
            currency="EUR",
        )

        revaluation_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Revalorizacion cartera marzo",
            origin=LedgerTransaction.Origin.SYSTEM,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("15.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("15.00"),
            currency="EUR",
        )

        filtered = self.client.get("/api/accounting/transactions/?kind=investment_purchase")
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["total_count"], 1)
        self.assertEqual(filtered.data["results"][0]["description"], "Aporte broker marzo")
        self.assertEqual(filtered.data["results"][0]["activity_kind"], "investment_purchase")

    def test_transactions_list_kind_debt_payment_excludes_revaluation(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca principal",
            category=Liability.Category.MORTGAGE,
            currency="EUR",
            amount=Decimal("120000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo hipoteca",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto tecnico",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
        )

        debt_payment_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 5),
            value_date=date(2026, 3, 5),
            description="Cuota hipoteca marzo",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.DEBT_PAYMENT,
        )
        LedgerEntry.objects.create(
            transaction=debt_payment_tx,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("500.00"),
            currency="EUR",
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=debt_payment_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("500.00"),
            currency="EUR",
        )

        revaluation_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Revalorizacion pasivo marzo",
            origin=LedgerTransaction.Origin.SYSTEM,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("120.00"),
            currency="EUR",
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("120.00"),
            currency="EUR",
        )

        filtered = self.client.get("/api/accounting/transactions/?kind=debt_payment")
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["total_count"], 1)
        self.assertEqual(filtered.data["results"][0]["description"], "Cuota hipoteca marzo")
        self.assertEqual(filtered.data["results"][0]["activity_kind"], "debt_payment")

    def test_transactions_list_classifies_system_opening_balance_as_opening_balance(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Cuenta inicial",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        opening_account = LedgerAccount.objects.create(
            user=self.user,
            name="Caja inicial",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto tecnico",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 10),
            value_date=date(2026, 3, 10),
            description="Saldo inicial contable: Caja inicial",
            origin=LedgerTransaction.Origin.SYSTEM,
            notes="net_worth_opening_balance:asset:999",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=opening_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            asset=asset,
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )

        response = self.client.get("/api/accounting/transactions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        found = next((row for row in response.data["results"] if row["id"] == opening_tx.id), None)
        self.assertIsNotNone(found)
        self.assertEqual(found["activity_kind"], "opening_balance")

    def test_transactions_list_kind_opening_balance_excludes_revaluation(self):
        asset = Asset.objects.create(
            user=self.user,
            name="Activo apertura",
            category=Asset.Category.CASH,
            subcategory=Asset.Subcategory.BANK_ACCOUNT,
            currency="EUR",
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("1000.00"),
            is_active=True,
        )
        asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Cuenta apertura",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=asset,
        )
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio neto tecnico",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
            origin=LedgerAccount.Origin.SYSTEM,
        )

        opening_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 11),
            value_date=date(2026, 3, 11),
            description="Saldo inicial contable: Cuenta apertura",
            origin=LedgerTransaction.Origin.SYSTEM,
            notes="net_worth_opening_balance:asset:1001",
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=asset_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("1000.00"),
            currency="EUR",
            asset=asset,
        )
        LedgerEntry.objects.create(
            transaction=opening_tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("1000.00"),
            currency="EUR",
        )

        revaluation_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 18),
            value_date=date(2026, 3, 18),
            description="Revalorizacion cartera marzo",
            origin=LedgerTransaction.Origin.SYSTEM,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.REVALUATION,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=asset_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("15.00"),
            currency="EUR",
            asset=asset,
        )
        LedgerEntry.objects.create(
            transaction=revaluation_tx,
            account=equity_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("15.00"),
            currency="EUR",
        )

        opening_filtered = self.client.get("/api/accounting/transactions/?kind=opening_balance")
        self.assertEqual(opening_filtered.status_code, status.HTTP_200_OK, opening_filtered.data)
        self.assertEqual(opening_filtered.data["total_count"], 1)
        self.assertEqual(
            opening_filtered.data["results"][0]["description"],
            "Saldo inicial contable: Cuenta apertura",
        )
        self.assertEqual(opening_filtered.data["results"][0]["activity_kind"], "opening_balance")

        revaluation_filtered = self.client.get("/api/accounting/transactions/?kind=revaluation")
        self.assertEqual(
            revaluation_filtered.status_code,
            status.HTTP_200_OK,
            revaluation_filtered.data,
        )
        self.assertEqual(revaluation_filtered.data["total_count"], 1)
        self.assertEqual(
            revaluation_filtered.data["results"][0]["description"], "Revalorizacion cartera marzo"
        )
        self.assertEqual(revaluation_filtered.data["results"][0]["activity_kind"], "revaluation")

    def test_kind_filters_prioritize_quick_entry_kind_over_legacy_markers(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin test",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="EUR",
            amount=Decimal("100.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="BTC broker test",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo test",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("1000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo test",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )

        investment_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 20),
            value_date=date(2026, 3, 20),
            description="Inversion con marca legacy de ingreso",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
        )
        LedgerEntry.objects.create(
            transaction=investment_tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("10.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=investment_tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("10.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

        transfer_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 21),
            value_date=date(2026, 3, 21),
            description="Transferencia con estructura no canonica",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.TRANSFER,
        )
        LedgerEntry.objects.create(
            transaction=transfer_tx,
            account=investment_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("5.00"),
            currency="EUR",
            asset=investment_asset,
        )
        LedgerEntry.objects.create(
            transaction=transfer_tx,
            account=self.income_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("5.00"),
            currency="EUR",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

        investment_with_liability_marker_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 22),
            value_date=date(2026, 3, 22),
            description="Inversion con marca de deuda legacy",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
        )
        LedgerEntry.objects.create(
            transaction=investment_with_liability_marker_tx,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("7.00"),
            currency="EUR",
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=investment_with_liability_marker_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("7.00"),
            currency="EUR",
        )

        debt_payment_tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 3, 23),
            value_date=date(2026, 3, 23),
            description="Pago deuda test",
            origin=LedgerTransaction.Origin.MANUAL,
            quick_entry_kind=LedgerTransaction.QuickEntryKind.DEBT_PAYMENT,
        )
        LedgerEntry.objects.create(
            transaction=debt_payment_tx,
            account=liability_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("50.00"),
            currency="EUR",
            liability=liability,
        )
        LedgerEntry.objects.create(
            transaction=debt_payment_tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("50.00"),
            currency="EUR",
        )

        income_filtered = self.client.get("/api/accounting/transactions/?kind=income")
        self.assertEqual(income_filtered.status_code, status.HTTP_200_OK, income_filtered.data)
        income_descriptions = {row["description"] for row in income_filtered.data["results"]}
        self.assertNotIn("Inversion con marca legacy de ingreso", income_descriptions)
        self.assertNotIn("Transferencia con estructura no canonica", income_descriptions)

        debt_filtered = self.client.get("/api/accounting/transactions/?kind=debt_payment")
        self.assertEqual(debt_filtered.status_code, status.HTTP_200_OK, debt_filtered.data)
        debt_descriptions = {row["description"] for row in debt_filtered.data["results"]}
        self.assertIn("Pago deuda test", debt_descriptions)
        self.assertNotIn("Inversion con marca de deuda legacy", debt_descriptions)

        transfer_filtered = self.client.get("/api/accounting/transactions/?kind=transfer")
        self.assertEqual(transfer_filtered.status_code, status.HTTP_200_OK, transfer_filtered.data)
        transfer_descriptions = {row["description"] for row in transfer_filtered.data["results"]}
        self.assertIn("Transferencia con estructura no canonica", transfer_descriptions)

    def test_monthly_summary_endpoint(self):
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Vivienda",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
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
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="housing_home",
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

    def test_quick_entry_income_accepts_category_without_annual_link(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-06",
                "value_date": "2026-04-06",
                "description": "Ingreso clasificado sin linea anual",
                "amount": "550.00",
                "account_id": self.cash_account.id,
                "category_key": "salary",
                "subcategory_key": "employee_salary",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        income_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] != self.cash_account.id
        )
        self.assertEqual(income_entry["flow_family"], "income")
        self.assertEqual(income_entry["category_key"], "salary")
        self.assertEqual(income_entry["subcategory_key"], "employee_salary")
        self.assertIsNone(income_entry["annual_income_entry_id"])

    def test_quick_entry_expense_requires_category_when_annual_link_is_missing(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-04-06",
                "value_date": "2026-04-06",
                "description": "Gasto sin clasificar",
                "amount": "90.00",
                "account_id": self.cash_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("subcategory_key", response.data["error"]["details"])

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

    def test_quick_entry_expense_with_explicit_classification_updates_monthly_summary(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-05-04",
                "value_date": "2026-05-04",
                "description": "Compra clasificada",
                "amount": "130.00",
                "account_id": self.cash_account.id,
                "flow_family": "expense",
                "category_key": "consumption_expenses",
                "subcategory_key": "living_expenses",
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

        summary = self.client.get("/api/accounting/transactions/monthly-summary/?year=2026")
        self.assertEqual(summary.status_code, status.HTTP_200_OK, summary.data)
        self.assertEqual(summary.data["months"][4]["expense_total"], "130.00")

    def test_quick_entry_expense_allows_liability_origin_account(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Tarjeta ECI",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            amount=Decimal("0.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Tarjeta ECI Pablo",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-05-06",
                "value_date": "2026-05-06",
                "description": "Parking",
                "amount": "4.95",
                "account_id": liability_account.id,
                "flow_family": "expense",
                "category_key": "consumption_expenses",
                "subcategory_key": "transport_mobility",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["quick_entry_kind"], "expense")
        liability_entry = next(
            row for row in response.data["entries"] if row["account_id"] == liability_account.id
        )
        expense_entry = next(
            row for row in response.data["entries"] if row["flow_family"] == "expense"
        )
        self.assertEqual(liability_entry["side"], "credit")
        self.assertEqual(liability_entry["amount"], "4.95000000")
        self.assertEqual(expense_entry["side"], "debit")
        self.assertEqual(expense_entry["category_key"], "consumption_expenses")
        self.assertEqual(expense_entry["subcategory_key"], "transport_mobility")

    def test_ledger_entry_with_annual_expense_link_is_reflected_in_monthly_summary(self):
        expense_plan = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Alquiler",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="housing_home",
            amount_annual=Decimal("9600.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos legacy",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 6, 10),
            value_date=date(2026, 6, 10),
            description="Gasto legacy",
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("80.00"),
            currency="EUR",
            annual_expense_entry=expense_plan,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("80.00"),
            currency="EUR",
        )

        summary = build_monthly_accounting_summary(user_id=self.user.id, fiscal_year=2026)
        self.assertEqual(summary["months"][5]["expense_total"], "80.00")

    def test_backfill_ledger_entry_classification_preserves_monthly_summaries(self):
        expense_plan = AnnualExpenseEntry.objects.create(
            user=self.user,
            name="Alquiler",
            category=AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
            subcategory="housing_home",
            amount_annual=Decimal("9600.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos legacy",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )
        tx = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 7, 11),
            value_date=date(2026, 7, 11),
            description="Gasto legacy a clasificar",
        )
        entry = LedgerEntry.objects.create(
            transaction=tx,
            account=expense_account,
            side=LedgerEntry.Side.DEBIT,
            amount=Decimal("95.00"),
            currency="EUR",
            annual_expense_entry=expense_plan,
        )
        LedgerEntry.objects.create(
            transaction=tx,
            account=self.cash_account,
            side=LedgerEntry.Side.CREDIT,
            amount=Decimal("95.00"),
            currency="EUR",
        )

        before = build_monthly_accounting_summary(user_id=self.user.id, fiscal_year=2026)
        result = backfill_ledger_entry_classification(user_id=self.user.id)
        entry.refresh_from_db()
        after = build_monthly_accounting_summary(user_id=self.user.id, fiscal_year=2026)

        self.assertEqual(result.scanned, 1)
        self.assertEqual(result.updated, 1)
        self.assertEqual(result.ambiguous, 0)
        self.assertEqual(before, after)
        self.assertEqual(entry.flow_family, LedgerEntry.FlowFamily.EXPENSE)
        self.assertEqual(entry.category_key, "consumption_expenses")
        self.assertEqual(entry.subcategory_key, "housing_home")

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

    def test_quick_entry_transfer_allows_liquidity_to_credit_card_liability(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Tarjeta ECI",
            category=Liability.Category.CREDIT_CARD,
            currency="EUR",
            amount=Decimal("0.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Tarjeta ECI Pablo",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-03",
                "value_date": "2026-04-03",
                "description": "Transferencia a Tarjeta ECI desde ING",
                "amount": "136.47",
                "account_id": self.cash_account.id,
                "counterparty_account_id": liability_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["quick_entry_kind"], "transfer")
        liability_entry = next(
            row for row in response.data["entries"] if row["account_id"] == liability_account.id
        )
        origin_entry = next(
            row for row in response.data["entries"] if row["account_id"] == self.cash_account.id
        )
        self.assertEqual(liability_entry["side"], "debit")
        self.assertEqual(origin_entry["side"], "credit")

    def test_quick_entry_income_rejects_foreign_account_reference(self):
        other_user = get_user_model().objects.create_user(
            username="acct_foreign_income",
            password="pass1234",
        )
        foreign_account = LedgerAccount.objects.create(
            user=other_user,
            name="Cuenta ajena",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-07",
                "value_date": "2026-04-07",
                "description": "Ingreso con cuenta ajena",
                "amount": "50.00",
                "account_id": foreign_account.id,
                "category_key": "salary",
                "subcategory_key": "employee_salary",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("account_id", response.data["error"]["details"])

    def test_quick_entry_income_allows_investment_account_for_reinvested_yield(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Crowdlending position",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CROWDLENDING,
            tracking_mode=Asset.TrackingMode.ACCOUNTING,
            currency="EUR",
            start_date=date(2025, 1, 1),
            annual_interest_tae=Decimal("0.00"),
            amount=Decimal("0.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Crowdlending - ViaInvest / EUR",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )
        investment_asset.accounting_account_id = investment_account.id
        investment_asset.save(update_fields=["accounting_account_id", "updated_at"])

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "income",
                "booking_date": "2026-04-07",
                "value_date": "2026-04-07",
                "description": "Intereses crowdlending",
                "amount": "14.29",
                "account_id": investment_account.id,
                "category_key": "passive_income",
                "subcategory_key": "p2p_lending",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["activity_kind"], "income")
        self.assertEqual(response.data["quick_entry_kind"], "income")
        self.assertEqual(len(response.data["entries"]), 2)
        investment_entry = next(
            row for row in response.data["entries"] if row["account_id"] == investment_account.id
        )
        classified_entry = next(
            row for row in response.data["entries"] if row["flow_family"] == "income"
        )
        self.assertEqual(investment_entry["side"], "debit")
        self.assertEqual(investment_entry["amount"], "14.29000000")
        self.assertEqual(classified_entry["category_key"], "passive_income")
        self.assertEqual(classified_entry["subcategory_key"], "p2p_lending")

    def test_quick_entry_transfer_rejects_foreign_counterparty_reference(self):
        other_user = get_user_model().objects.create_user(
            username="acct_foreign_transfer",
            password="pass1234",
        )
        foreign_counterparty = LedgerAccount.objects.create(
            user=other_user,
            name="Ahorro ajeno",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-08",
                "value_date": "2026-04-08",
                "description": "Transferencia con contrapartida ajena",
                "amount": "75.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": foreign_counterparty.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("counterparty_account_id", response.data["error"]["details"])

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

    def test_quick_entry_adjustment_creates_equity_counterparty_automatically(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "adjustment",
                "booking_date": "2026-04-12",
                "value_date": "2026-04-12",
                "description": "Ajuste conciliacion BTC",
                "amount": "-0.00078100",
                "account_id": self.cash_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["quick_entry_kind"], "adjustment")
        self.assertEqual(response.data["activity_kind"], "adjustment")
        self.assertEqual(len(response.data["entries"]), 2)

        account_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == self.cash_account.id
        )
        self.assertEqual(account_entry["side"], "credit")
        self.assertEqual(account_entry["amount"], "0.00078100")

        equity_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] != self.cash_account.id
        )
        self.assertEqual(equity_entry["side"], "debit")
        self.assertEqual(equity_entry["amount"], "0.00078100")
        equity_account = LedgerAccount.objects.get(id=equity_entry["account_id"])
        self.assertEqual(equity_account.account_type, LedgerAccount.AccountType.EQUITY)
        self.assertEqual(equity_account.currency, self.cash_account.currency)

    def test_quick_entry_adjustment_rejects_non_operational_account(self):
        equity_account = LedgerAccount.objects.create(
            user=self.user,
            name="Patrimonio tecnico",
            account_type=LedgerAccount.AccountType.EQUITY,
            currency="EUR",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "adjustment",
                "booking_date": "2026-04-12",
                "value_date": "2026-04-12",
                "description": "Ajuste invalido",
                "amount": "10.00",
                "account_id": equity_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("account_id", response.data["error"]["details"])

    def test_transactions_filter_kind_adjustment_returns_only_adjustments(self):
        second_asset_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ahorro filtro",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "adjustment",
                "booking_date": "2026-04-12",
                "value_date": "2026-04-12",
                "description": "Ajuste 1",
                "amount": "10.00",
                "account_id": self.cash_account.id,
            },
            format="json",
        )
        self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "transfer",
                "booking_date": "2026-04-13",
                "value_date": "2026-04-13",
                "description": "Transferencia 1",
                "amount": "10.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": second_asset_account.id,
            },
            format="json",
        )

        response = self.client.get("/api/accounting/transactions/?kind=adjustment")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertGreaterEqual(response.data["total_count"], 1)
        self.assertTrue(response.data["results"])
        self.assertTrue(
            all(row["activity_kind"] == "adjustment" for row in response.data["results"])
        )

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

    def test_quick_entry_investment_outflow_reverses_entry_sides_and_persists_direction(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="ETF cartera",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.ETFS,
            currency="EUR",
            amount=Decimal("1500.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker principal",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "outflow",
                "booking_date": "2026-04-14",
                "value_date": "2026-04-14",
                "description": "Desinversion parcial",
                "amount": "180.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": investment_account.id,
                "realized_cost_basis": "150.00",
                "realized_gain_loss": "30.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["quick_entry_kind"], "investment")
        self.assertEqual(response.data["investment_direction"], "outflow")
        self.assertEqual(response.data["realized_cost_basis"], "150.00000000")
        self.assertEqual(response.data["realized_gain_loss"], "30.00000000")
        debit_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == self.cash_account.id
        )
        credit_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == investment_account.id
        )
        self.assertEqual(debit_entry["side"], "debit")
        self.assertEqual(credit_entry["side"], "credit")

    def test_quick_entry_investment_allows_cross_currency_with_destination_amount(self):
        btc_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("0.01000000"),
            is_active=True,
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="BTC Broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=btc_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "inflow",
                "booking_date": "2026-04-16",
                "value_date": "2026-04-16",
                "description": "Compra BTC",
                "amount": "25.00",
                "destination_amount": "0.00042000",
                "account_id": self.cash_account.id,
                "counterparty_account_id": btc_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        cash_credit = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == self.cash_account.id
        )
        btc_debit = next(
            entry for entry in response.data["entries"] if entry["account_id"] == btc_account.id
        )
        self.assertEqual(cash_credit["side"], "credit")
        self.assertEqual(cash_credit["currency"], "EUR")
        self.assertEqual(cash_credit["amount"], "25.00000000")
        self.assertEqual(btc_debit["side"], "debit")
        self.assertEqual(btc_debit["currency"], "BTC")
        self.assertEqual(btc_debit["amount"], "0.00042000")

    def test_quick_entry_investment_cross_currency_requires_destination_amount(self):
        btc_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("0.01000000"),
            is_active=True,
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="BTC Broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=btc_asset,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "inflow",
                "booking_date": "2026-04-16",
                "value_date": "2026-04-16",
                "description": "Compra BTC sin destino",
                "amount": "25.00",
                "account_id": self.cash_account.id,
                "counterparty_account_id": btc_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("destination_amount", response.data["error"]["details"])

    def test_quick_entry_investment_outflow_uses_capital_gains_classification(self):
        btc_asset = Asset.objects.create(
            user=self.user,
            name="Bitcoin",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.CRYPTOCURRENCIES,
            currency="BTC",
            amount=Decimal("0.01000000"),
            is_active=True,
        )
        btc_account = LedgerAccount.objects.create(
            user=self.user,
            name="BTC Broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
            asset=btc_asset,
        )
        usd_liquidity = LedgerAccount.objects.create(
            user=self.user,
            name="Spot USD",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="USD",
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "investment",
                "investment_direction": "outflow",
                "booking_date": "2026-04-16",
                "value_date": "2026-04-16",
                "description": "Venta BTC",
                "amount": "0.00042000",
                "destination_amount": "25.00",
                "account_id": usd_liquidity.id,
                "counterparty_account_id": btc_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        classified_entry = next(
            row for row in response.data["entries"] if row["flow_family"] == "income"
        )
        self.assertEqual(classified_entry["category_key"], "capital_gains")
        self.assertEqual(classified_entry["subcategory_key"], "sale_financial_assets")

    def test_quick_entry_mortgage_payment_uses_fixed_real_estate_classification(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Hipoteca casa",
            category=Liability.Category.MORTGAGE,
            currency="EUR",
            amount=Decimal("120000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo hipoteca",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-20",
                "value_date": "2026-04-20",
                "description": "Pago hipoteca",
                "amount": "500.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "principal_amount": "500.00",
                "interest_amount": "0.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        classified_entry = next(
            row for row in response.data["entries"] if row["flow_family"] == "expense"
        )
        self.assertEqual(classified_entry["category_key"], "real_estate_assets")
        self.assertEqual(classified_entry["subcategory_key"], "mortgage_principal")

    def test_quick_entry_personal_loan_payment_requires_consumption_subcategory(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo coche",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("5000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo prestamo",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-20",
                "value_date": "2026-04-20",
                "description": "Pago prestamo",
                "amount": "400.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "principal_amount": "400.00",
                "interest_amount": "0.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("subcategory_key", response.data["error"]["details"])

    def test_quick_entry_rejects_realized_metadata_outside_investment(self):
        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "expense",
                "booking_date": "2026-04-21",
                "value_date": "2026-04-21",
                "description": "Compra semanal",
                "amount": "55.00",
                "account_id": self.cash_account.id,
                "category_key": "consumption_expenses",
                "subcategory_key": "living_expenses",
                "realized_gain_loss": "5.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("realized_gain_loss", response.data["error"]["details"])

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
                "category_key": "consumption_expenses",
                "subcategory_key": "financial_commitments",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("amount", response.data["error"]["details"])

    def test_quick_entry_debt_payment_keeps_non_consumption_category_for_principal(self):
        liability = Liability.objects.create(
            user=self.user,
            name="Prestamo movil",
            category=Liability.Category.PERSONAL_LOAN,
            currency="EUR",
            amount=Decimal("2000.00"),
        )
        liability_account = LedgerAccount.objects.create(
            user=self.user,
            name="Pasivo prestamo movil",
            account_type=LedgerAccount.AccountType.LIABILITY,
            currency="EUR",
            liability=liability,
        )

        response = self.client.post(
            "/api/accounting/transactions/quick-entry/",
            {
                "movement_type": "debt_payment",
                "booking_date": "2026-04-23",
                "value_date": "2026-04-23",
                "description": "Cuota movil",
                "amount": "120.00",
                "principal_amount": "120.00",
                "interest_amount": "0.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "category_key": "tangible_assets",
                "subcategory_key": "technology_devices",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        principal_entry = next(
            entry
            for entry in response.data["entries"]
            if entry["account_id"] == liability_account.id
        )
        self.assertEqual(principal_entry["flow_family"], "expense")
        self.assertEqual(principal_entry["category_key"], "tangible_assets")
        self.assertEqual(principal_entry["subcategory_key"], "technology_devices")

    def test_quick_entry_debt_payment_requires_category_for_interest_when_no_annual_link(self):
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
                "description": "Cuota sin clasificar",
                "amount": "250.00",
                "principal_amount": "200.00",
                "interest_amount": "50.00",
                "account_id": self.cash_account.id,
                "liability_account_id": liability_account.id,
                "interest_account_id": interest_account.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("subcategory_key", response.data["error"]["details"])

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
        AnnualIncomeEntry.objects.create(
            user=self.user,
            name="Nomina",
            category=AnnualIncomeEntry.Category.SALARY,
            subcategory="employee_salary",
            amount_annual=Decimal("12000.00"),
            fiscal_year=2026,
            currency="EUR",
        )
        AnnualExpenseEntry.objects.create(
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
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="salary",
            subcategory_key="employee_salary",
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
            flow_family=LedgerEntry.FlowFamily.EXPENSE,
            category_key="consumption_expenses",
            subcategory_key="living_expenses",
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


class MoneyWizImportAPITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="moneywiz_user",
            password="pass1234",
        )
        self.client.force_authenticate(self.user)
        LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )

    def _build_csv(self) -> bytes:
        return (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2026-04-01;Nomina abril;;salary;Banco;;1500;;1500\n"
            "2026-04-02;Compra supermercado;;food;Banco;;120;120;\n"
            "2026-04-03;Mover ahorro;;transfer;Banco;Ahorro;300;;\n"
            "2026-04-04;Compra fondo;;investment;Banco;;250;250;\n"
            "2026-04-05;Pago hipoteca;;mortgage;Banco;;330;330;\n"
        ).encode("utf-8")

    def test_moneywiz_preview_reports_rows_and_detected_accounts(self):
        upload = SimpleUploadedFile("moneywiz.csv", self._build_csv(), content_type="text/csv")
        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["row_count"], 5)
        self.assertEqual(response.data["stats"]["income"], 1)
        self.assertEqual(response.data["stats"]["expense"], 1)
        self.assertEqual(response.data["stats"]["transfer"], 1)
        self.assertEqual(response.data["stats"]["investment_purchase"], 1)
        self.assertEqual(response.data["stats"]["debt_payment"], 1)
        self.assertTrue(any(row["movement_type"] == "transfer" for row in response.data["rows"]))
        self.assertTrue(
            any(account["name"] == "Ahorro" for account in response.data["detected_accounts"])
        )

    def test_moneywiz_commit_creates_transactions_and_is_idempotent(self):
        upload = SimpleUploadedFile("moneywiz.csv", self._build_csv(), content_type="text/csv")
        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/commit/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["created_count"], 5)
        self.assertEqual(LedgerTransaction.objects.filter(user=self.user).count(), 5)
        self.assertTrue(
            LedgerAccount.objects.filter(
                user=self.user,
                name="Ahorro",
                account_type=LedgerAccount.AccountType.ASSET,
            ).exists()
        )
        self.assertTrue(
            LedgerAccount.objects.filter(
                user=self.user,
                account_type=LedgerAccount.AccountType.LIABILITY,
            ).exists()
        )

        second_upload = SimpleUploadedFile(
            "moneywiz.csv",
            self._build_csv(),
            content_type="text/csv",
        )
        second_response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/commit/",
            {"file": second_upload},
            format="multipart",
        )

        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED, second_response.data)
        self.assertEqual(second_response.data["created_count"], 0)
        self.assertEqual(second_response.data["skipped_existing_count"], 5)
        self.assertEqual(LedgerTransaction.objects.filter(user=self.user).count(), 5)

    def test_moneywiz_commit_updates_monthly_summary_and_marks_import_origin(self):
        upload = SimpleUploadedFile("moneywiz.csv", self._build_csv(), content_type="text/csv")
        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/commit/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        summary = self.client.get("/api/accounting/transactions/monthly-summary/?year=2026")
        self.assertEqual(summary.status_code, status.HTTP_200_OK, summary.data)
        april = summary.data["months"][3]
        self.assertEqual(april["income_total"], "1500.00")
        self.assertEqual(april["expense_total"], "120.00")

        imported_rows = LedgerTransaction.objects.filter(
            user=self.user,
            origin=LedgerTransaction.Origin.IMPORT,
            import_source="moneywiz",
        )
        self.assertEqual(imported_rows.count(), 5)
        self.assertTrue(imported_rows.exclude(import_fingerprint="").exists())

    def test_delete_imported_removes_only_import_transactions_of_authenticated_user(self):
        LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 10),
            value_date=date(2026, 4, 10),
            description="Importado MoneyWiz",
            origin=LedgerTransaction.Origin.IMPORT,
            import_source="moneywiz",
            import_fingerprint="fp-import-1",
        )
        LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 11),
            value_date=date(2026, 4, 11),
            description="Manual",
            origin=LedgerTransaction.Origin.MANUAL,
        )
        other_user = get_user_model().objects.create_user(
            username="moneywiz_other_user",
            password="pass1234",
        )
        LedgerTransaction.objects.create(
            user=other_user,
            booking_date=date(2026, 4, 12),
            value_date=date(2026, 4, 12),
            description="Importado otro usuario",
            origin=LedgerTransaction.Origin.IMPORT,
            import_source="moneywiz",
            import_fingerprint="fp-import-2",
        )

        response = self.client.post("/api/accounting/transactions/delete-imported/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["deleted_count"], 1)
        self.assertFalse(
            LedgerTransaction.objects.filter(
                user=self.user,
                origin=LedgerTransaction.Origin.IMPORT,
            ).exists()
        )
        self.assertTrue(
            LedgerTransaction.objects.filter(
                user=self.user,
                origin=LedgerTransaction.Origin.MANUAL,
            ).exists()
        )
        self.assertTrue(
            LedgerTransaction.objects.filter(
                user=other_user,
                origin=LedgerTransaction.Origin.IMPORT,
            ).exists()
        )

    def test_delete_imported_returns_zero_when_user_has_no_import_transactions(self):
        LedgerTransaction.objects.create(
            user=self.user,
            booking_date=date(2026, 4, 11),
            value_date=date(2026, 4, 11),
            description="Manual",
            origin=LedgerTransaction.Origin.MANUAL,
        )

        response = self.client.post("/api/accounting/transactions/delete-imported/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["deleted_count"], 0)
        self.assertEqual(LedgerTransaction.objects.filter(user=self.user).count(), 1)

    def test_moneywiz_preview_myinvestor_premium_is_not_investment_purchase(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2026-03-03;Myinvestor Premium;;Inversiones Gastos > Suscripciones;MyInvestor;;7,99;7,99;\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["row_count"], 1)
        self.assertEqual(response.data["stats"]["expense"], 1)
        self.assertEqual(response.data["stats"]["investment_purchase"], 0)
        self.assertEqual(response.data["rows"][0]["movement_type"], "expense")

    def test_moneywiz_preview_transfer_token_without_transfers_column_is_not_transfer(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2026-03-03;transfer_0049_traspaso;;Gastos > Corrientes > Vivienda;Banco;;;25;\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["row_count"], 1)
        self.assertEqual(response.data["stats"]["expense"], 1)
        self.assertEqual(response.data["stats"]["transfer"], 0)
        self.assertEqual(response.data["rows"][0]["movement_type"], "expense")

    def test_moneywiz_preview_traspaso_token_without_transfers_column_is_not_transfer(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2026-03-03;traspaso_de_ana;;Gastos > Corrientes > Vivienda;Banco;;;15;\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["row_count"], 1)
        self.assertEqual(response.data["stats"]["expense"], 1)
        self.assertEqual(response.data["stats"]["transfer"], 0)
        self.assertEqual(response.data["rows"][0]["movement_type"], "expense")

    def test_moneywiz_preview_dividendos_stock_is_income(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2026-03-03;dividendos_stock;;Inversiones Ingresos > St Stocks;Broker;;; ;12,50\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["row_count"], 1)
        self.assertEqual(response.data["stats"]["income"], 1)
        self.assertEqual(response.data["stats"]["investment_purchase"], 0)
        self.assertEqual(response.data["rows"][0]["movement_type"], "income")

    def test_moneywiz_preview_transferencia_token_without_transfers_column_is_not_transfer(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2026-03-03;transferencia_de_monedero_ana_a_;;Gastos > Corrientes > Vivienda;Banco;;;8,50;\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["row_count"], 1)
        self.assertEqual(response.data["stats"]["expense"], 1)
        self.assertEqual(response.data["stats"]["transfer"], 0)
        self.assertEqual(response.data["rows"][0]["movement_type"], "expense")

    def test_moneywiz_preview_synthetic_token_in_transfers_column_is_not_transfer(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2026-03-03;Cuota;;Gastos > Corrientes > Vivienda;Banco;transferencia_de_monedero_ana_a_;;8,50;\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["row_count"], 1)
        self.assertEqual(response.data["stats"]["expense"], 1)
        self.assertEqual(response.data["stats"]["transfer"], 0)
        self.assertEqual(response.data["rows"][0]["movement_type"], "expense")

    def test_moneywiz_preview_traspaso_de_text_without_transfers_column_is_not_transfer(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2018-03-31;Traspaso De Ana;;Otro;Monedero Personal;;200;;; \n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["row_count"], 1)
        self.assertEqual(response.data["stats"]["transfer"], 0)
        self.assertEqual(response.data["rows"][0]["movement_type"], "income")

    def test_moneywiz_preview_synthetic_transfers_token_does_not_fallback_to_description_transfer(
        self,
    ):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2026-03-03;Transferencia de Monedero Ana A;;Otro;Monedero Personal;transferencia_de_monedero_ana_a_;;8,50;\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["row_count"], 1)
        self.assertEqual(response.data["stats"]["transfer"], 0)
        self.assertEqual(response.data["rows"][0]["movement_type"], "expense")

    def test_moneywiz_preview_transfer_description_with_category_is_not_transfer(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2023-08-01;Transferencia de Monedero Ana a Ana Santander;;Gastos > Otro general;Monedero Ana;;;38,90;\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["row_count"], 1)
        self.assertEqual(response.data["stats"]["transfer"], 0)
        self.assertEqual(response.data["stats"]["expense"], 1)
        self.assertEqual(response.data["rows"][0]["movement_type"], "expense")

    def test_moneywiz_commit_debt_mirror_does_not_pair_when_principal_exceeds_outflow(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2026-01-10;Liquidacion credito;;Liquidacion credito;Hipoteca;;;56,21;\n"
            "2026-01-10;Pago hipoteca;;Gastos > Corrientes > Vivienda;Banco;;;42,69;\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        preview = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        movement_types = [row["movement_type"] for row in preview.data["rows"]]
        self.assertEqual(movement_types.count("debt_payment"), 1)
        self.assertEqual(movement_types.count("expense"), 1)

        upload_commit = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")
        commit = self.client.post(
            "/api/accounting/transactions/import-moneywiz/commit/",
            {"file": upload_commit},
            format="multipart",
        )
        self.assertEqual(commit.status_code, status.HTTP_201_CREATED, commit.data)
        self.assertEqual(commit.data["created_count"], 2)

    def test_moneywiz_commit_rejects_account_map_with_currency_mismatch(self):
        btc_asset = LedgerAccount.objects.create(
            user=self.user,
            name="Wallet BTC",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
        )
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes);Currency\n"
            "2026-03-03;Ingreso wallet;;Pasivos > Activos financieros > Dividendos;Wallet BTC;;;58,48;;EUR\n"
        ).encode("utf-8")
        upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")

        response = self.client.post(
            "/api/accounting/transactions/import-moneywiz/commit/",
            {
                "file": upload,
                "account_id_map": json.dumps({"Wallet BTC": btc_asset.id}),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertIn("account_id_map", response.data.get("error", {}).get("details", {}))

    def test_moneywiz_transfer_mirror_rows_are_collapsed_into_one_transaction(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2023-11-28;Transferencia a MyInvestor Ahorro;;Transfer;Ana Santander;MyInvestor Ahorro;;;10000\n"
            "2023-11-28;Transferencia de Ana Santander;;Transfer;MyInvestor Ahorro;Ana Santander;;10000;\n"
        ).encode("utf-8")

        preview_upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")
        preview = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": preview_upload},
            format="multipart",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        self.assertEqual(preview.data["row_count"], 2)
        self.assertEqual(preview.data["stats"]["transfer"], 1)
        self.assertEqual(preview.data["mirror_row_count"], 1)

        commit_upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")
        commit = self.client.post(
            "/api/accounting/transactions/import-moneywiz/commit/",
            {"file": commit_upload},
            format="multipart",
        )
        self.assertEqual(commit.status_code, status.HTTP_201_CREATED, commit.data)
        self.assertEqual(commit.data["created_count"], 1)

        tx = LedgerTransaction.objects.get(user=self.user)
        self.assertEqual(tx.description, "Transferencia a MyInvestor Ahorro")

    def test_moneywiz_investment_sale_mirror_collapses_into_investment_outflow(self):
        csv_bytes = (
            "sep=;\n"
            "Date;Description;Memo;Category;Account;Transfers;Amount;Amount (Expenses);Amount (Incomes)\n"
            "2026-03-15;Venta fondos indexados;;Inversiones Gastos > Fondos;Banco;;;;1000\n"
            "2026-03-15;Venta fondos indexados;;Inversiones Ingresos > Fondos;Broker;;;1000;\n"
        ).encode("utf-8")

        preview_upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")
        preview = self.client.post(
            "/api/accounting/transactions/import-moneywiz/preview/",
            {"file": preview_upload},
            format="multipart",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        self.assertEqual(preview.data["stats"]["investment_purchase"], 1)
        self.assertEqual(preview.data["stats"]["income"], 0)
        self.assertEqual(preview.data["mirror_row_count"], 1)
        active_rows = [row for row in preview.data["rows"] if not row["mirror"]]
        self.assertEqual(len(active_rows), 1)
        self.assertEqual(active_rows[0]["movement_type"], "investment_purchase")
        self.assertEqual(active_rows[0]["movement_direction"], "outflow")
        self.assertEqual(active_rows[0]["counterparty_name"], "Broker")

        commit_upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")
        commit = self.client.post(
            "/api/accounting/transactions/import-moneywiz/commit/",
            {"file": commit_upload},
            format="multipart",
        )
        self.assertEqual(commit.status_code, status.HTTP_201_CREATED, commit.data)
        self.assertEqual(commit.data["created_count"], 1)

        tx = LedgerTransaction.objects.get(user=self.user)
        self.assertEqual(tx.quick_entry_kind, "investment")
        self.assertEqual(tx.investment_direction, "outflow")

        second_upload = SimpleUploadedFile("moneywiz.csv", csv_bytes, content_type="text/csv")
        second_commit = self.client.post(
            "/api/accounting/transactions/import-moneywiz/commit/",
            {"file": second_upload},
            format="multipart",
        )
        self.assertEqual(second_commit.status_code, status.HTTP_201_CREATED, second_commit.data)
        self.assertEqual(second_commit.data["created_count"], 0)
