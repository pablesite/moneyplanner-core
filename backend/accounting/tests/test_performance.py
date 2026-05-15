from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from accounting.services_summaries import (
    build_account_balances_summary,
    build_daily_balance_series,
    build_monthly_accounting_summary,
)
from net_worth.models import Asset


class AccountingSummaryPerformanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="acct_perf_user",
            password="pass1234",
        )
        self.cash_account = LedgerAccount.objects.create(
            user=self.user,
            name="Banco",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        self.income_account = LedgerAccount.objects.create(
            user=self.user,
            name="Ingresos",
            account_type=LedgerAccount.AccountType.INCOME,
            currency="EUR",
        )
        self.expense_account = LedgerAccount.objects.create(
            user=self.user,
            name="Gastos",
            account_type=LedgerAccount.AccountType.EXPENSE,
            currency="EUR",
        )

    def test_monthly_summary_uses_stable_query_count_with_high_entry_volume(self):
        transactions = [
            LedgerTransaction(
                user=self.user,
                booking_date=date(2026, (idx % 12) + 1, 15),
                value_date=date(2026, (idx % 12) + 1, 15),
                description=f"Movimiento {idx}",
            )
            for idx in range(2400)
        ]
        LedgerTransaction.objects.bulk_create(transactions)
        transactions = list(LedgerTransaction.objects.filter(user=self.user).order_by("id"))
        entries = []
        amount = Decimal("10.00")
        for idx, transaction in enumerate(transactions):
            is_income = idx % 2 == 0
            entries.append(
                LedgerEntry(
                    transaction=transaction,
                    account=self.cash_account,
                    side=LedgerEntry.Side.DEBIT if is_income else LedgerEntry.Side.CREDIT,
                    amount=amount,
                    currency="EUR",
                )
            )
            entries.append(
                LedgerEntry(
                    transaction=transaction,
                    account=self.income_account if is_income else self.expense_account,
                    side=LedgerEntry.Side.CREDIT if is_income else LedgerEntry.Side.DEBIT,
                    amount=amount,
                    currency="EUR",
                    flow_family=LedgerEntry.FlowFamily.INCOME
                    if is_income
                    else LedgerEntry.FlowFamily.EXPENSE,
                    category_key="salary" if is_income else "consumption_expenses",
                    subcategory_key="employee_salary" if is_income else "living_expenses",
                )
            )
        LedgerEntry.objects.bulk_create(entries, batch_size=1000)

        with CaptureQueriesContext(connection) as captured_queries:
            summary = build_monthly_accounting_summary(user_id=self.user.id, fiscal_year=2026)

        self.assertLessEqual(len(captured_queries), 2)
        self.assertEqual(len(summary["months"]), 12)
        self.assertEqual(summary["months"][0]["income_total"], "2000.00")
        self.assertEqual(summary["months"][0]["uncategorized_total"], "2000.00")
        self.assertEqual(summary["months"][1]["expense_total"], "2000.00")
        self.assertEqual(summary["months"][1]["uncategorized_total"], "2000.00")

    def test_daily_balance_series_uses_grouped_queries_with_high_entry_volume(self):
        transactions = [
            LedgerTransaction(
                user=self.user,
                booking_date=date(2025, 12, 15) if idx < 1200 else date(2026, 1, (idx % 31) + 1),
                value_date=date(2025, 12, 15) if idx < 1200 else date(2026, 1, (idx % 31) + 1),
                description=f"Movimiento diario {idx}",
            )
            for idx in range(2400)
        ]
        LedgerTransaction.objects.bulk_create(transactions)
        transactions = list(LedgerTransaction.objects.filter(user=self.user).order_by("id"))
        amount = Decimal("10.00")
        entries = []
        for transaction in transactions:
            entries.append(
                LedgerEntry(
                    transaction=transaction,
                    account=self.cash_account,
                    side=LedgerEntry.Side.DEBIT,
                    amount=amount,
                    currency="EUR",
                )
            )
            entries.append(
                LedgerEntry(
                    transaction=transaction,
                    account=self.income_account,
                    side=LedgerEntry.Side.CREDIT,
                    amount=amount,
                    currency="EUR",
                )
            )
        LedgerEntry.objects.bulk_create(entries, batch_size=1000)

        with CaptureQueriesContext(connection) as captured_queries:
            summary = build_daily_balance_series(
                user_id=self.user.id,
                date_from=date(2026, 1, 1),
                date_to=date(2026, 1, 31),
            )

        self.assertLessEqual(len(captured_queries), 5)
        self.assertEqual(len(summary["rows"]), 31)
        self.assertEqual(summary["rows"][0]["assets_total"], "12390.00")
        self.assertEqual(summary["rows"][-1]["assets_total"], "24000.00")

    def test_account_balances_summary_uses_grouped_queries_with_high_entry_volume(self):
        investment_asset = Asset.objects.create(
            user=self.user,
            name="Fondo indexado",
            category=Asset.Category.INVESTMENTS,
            subcategory=Asset.Subcategory.FUNDS,
            currency="EUR",
            amount=Decimal("0.00"),
            is_active=True,
        )
        investment_account = LedgerAccount.objects.create(
            user=self.user,
            name="Broker",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
            asset=investment_asset,
        )
        transactions = [
            LedgerTransaction(
                user=self.user,
                booking_date=date(2025, 12, 15) if idx < 1200 else date(2026, 1, (idx % 31) + 1),
                value_date=date(2025, 12, 15) if idx < 1200 else date(2026, 1, (idx % 31) + 1),
                description=f"Balance movimiento {idx}",
            )
            for idx in range(2400)
        ]
        transactions.append(
            LedgerTransaction(
                user=self.user,
                booking_date=date(2026, 1, 5),
                value_date=date(2026, 1, 5),
                description="Aporte inversion",
                quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            )
        )
        transactions.append(
            LedgerTransaction(
                user=self.user,
                booking_date=date(2026, 1, 20),
                value_date=date(2026, 1, 20),
                description="Retiro inversion",
                quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            )
        )
        LedgerTransaction.objects.bulk_create(transactions)
        transactions = list(LedgerTransaction.objects.filter(user=self.user).order_by("id"))
        amount = Decimal("10.00")
        entries = []
        for transaction in transactions[:2400]:
            entries.append(
                LedgerEntry(
                    transaction=transaction,
                    account=self.cash_account,
                    side=LedgerEntry.Side.DEBIT,
                    amount=amount,
                    currency="EUR",
                )
            )
            entries.append(
                LedgerEntry(
                    transaction=transaction,
                    account=self.income_account,
                    side=LedgerEntry.Side.CREDIT,
                    amount=amount,
                    currency="EUR",
                )
            )
        investment_inflow = transactions[2400]
        investment_outflow = transactions[2401]
        entries.extend(
            [
                LedgerEntry(
                    transaction=investment_inflow,
                    account=investment_account,
                    side=LedgerEntry.Side.DEBIT,
                    amount=Decimal("500.00"),
                    currency="EUR",
                    asset=investment_asset,
                ),
                LedgerEntry(
                    transaction=investment_inflow,
                    account=self.cash_account,
                    side=LedgerEntry.Side.CREDIT,
                    amount=Decimal("500.00"),
                    currency="EUR",
                ),
                LedgerEntry(
                    transaction=investment_outflow,
                    account=self.cash_account,
                    side=LedgerEntry.Side.DEBIT,
                    amount=Decimal("200.00"),
                    currency="EUR",
                ),
                LedgerEntry(
                    transaction=investment_outflow,
                    account=investment_account,
                    side=LedgerEntry.Side.CREDIT,
                    amount=Decimal("200.00"),
                    currency="EUR",
                    asset=investment_asset,
                ),
            ]
        )
        LedgerEntry.objects.bulk_create(entries, batch_size=1000)

        with CaptureQueriesContext(connection) as captured_queries:
            summary = build_account_balances_summary(
                user_id=self.user.id,
                fiscal_year=2026,
                month=1,
                account_type=LedgerAccount.AccountType.ASSET,
            )

        self.assertLessEqual(len(captured_queries), 4)
        accounts_by_id = {row["account_id"]: row for row in summary["accounts"]}
        self.assertEqual(summary["totals_by_account_type"]["asset"], "24000.00")
        self.assertEqual(accounts_by_id[self.cash_account.id]["current_balance"], "23700.00000000")
        self.assertEqual(accounts_by_id[self.cash_account.id]["period_net_change"], "11700.00")
        self.assertEqual(accounts_by_id[investment_account.id]["current_balance"], "300.00000000")
        self.assertEqual(accounts_by_id[investment_account.id]["period_net_change"], "300.00")
        self.assertEqual(accounts_by_id[investment_account.id]["investment_inflow_total"], "500.00")
        self.assertEqual(
            accounts_by_id[investment_account.id]["investment_outflow_total"], "200.00"
        )
