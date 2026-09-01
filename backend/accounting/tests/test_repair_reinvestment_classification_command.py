from io import StringIO
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction


class RepairReinvestmentClassificationCommandTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="repair", password="pass")
        self.water = LedgerAccount.objects.create(
            user=self.user,
            name="Water",
            account_type=LedgerAccount.AccountType.ASSET,
        )
        self.small_caps = LedgerAccount.objects.create(
            user=self.user,
            name="Small Caps",
            account_type=LedgerAccount.AccountType.ASSET,
        )
        self.transaction = LedgerTransaction.objects.create(
            user=self.user,
            description="Traspaso entre ETFs",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=LedgerTransaction.InvestmentDirection.REINVESTMENT,
        )
        LedgerEntry.objects.create(
            transaction=self.transaction,
            account=self.small_caps,
            side=LedgerEntry.Side.DEBIT,
            amount="699.46",
        )
        self.classified_entry = LedgerEntry.objects.create(
            transaction=self.transaction,
            account=self.water,
            side=LedgerEntry.Side.CREDIT,
            amount="699.46",
            flow_family=LedgerEntry.FlowFamily.INCOME,
            category_key="capital_gains",
            subcategory_key="sale_financial_assets",
        )

    def run_command(self, **options):
        out = StringIO()
        call_command(
            "repair_reinvestment_classification",
            transaction_id=self.transaction.id,
            stdout=out,
            **options,
        )
        return out.getvalue()

    def test_dry_run_keeps_the_original_classification(self):
        output = self.run_command()

        self.classified_entry.refresh_from_db()
        self.assertIn("En seco", output)
        self.assertEqual(self.classified_entry.flow_family, LedgerEntry.FlowFamily.INCOME)

    def test_apply_clears_only_functional_classification(self):
        self.run_command(apply=True)

        self.classified_entry.refresh_from_db()
        self.assertEqual(self.classified_entry.flow_family, "")
        self.assertEqual(self.classified_entry.category_key, "")
        self.assertEqual(self.classified_entry.subcategory_key, "")
        self.assertEqual(self.classified_entry.amount, Decimal("699.46"))
        self.assertEqual(self.classified_entry.account, self.water)

    def test_rejects_a_transaction_that_is_not_a_reinvestment(self):
        self.transaction.investment_direction = LedgerTransaction.InvestmentDirection.OUTFLOW
        self.transaction.save(update_fields=["investment_direction", "updated_at"])

        with self.assertRaisesMessage(CommandError, "no es una reinversion"):
            self.run_command(apply=True)
