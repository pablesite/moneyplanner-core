from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from accounting.models import LedgerAccount, LedgerEntry, LedgerTransaction
from memberships.models import FamilyMember, Ownership, OwnershipSplit


class SplitCommingledOwnershipTests(TestCase):
    """Corregir el libro de un bote mezclado sin inventar ni perder unidades."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="pot", password="pass")
        her = FamilyMember.objects.create(user=self.user, name="Ella", role=FamilyMember.Role.ADULT)
        him = FamilyMember.objects.create(user=self.user, name="El", role=FamilyMember.Role.ADULT)
        self.shared = Ownership.objects.create(user=self.user, kind=Ownership.Kind.SHARED)
        OwnershipSplit.objects.create(ownership=self.shared, member=her, percent=Decimal("50"))
        OwnershipSplit.objects.create(ownership=self.shared, member=him, percent=Decimal("50"))
        self.own = Ownership.objects.create(
            user=self.user, kind=Ownership.Kind.INDIVIDUAL, member=him
        )
        self.pot = LedgerAccount.objects.create(
            user=self.user,
            name="Bote",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="BTC",
        )
        self.cash = LedgerAccount.objects.create(
            user=self.user,
            name="Efectivo",
            account_type=LedgerAccount.AccountType.ASSET,
            currency="EUR",
        )
        # Compra compartida, compra propia, la venta que lo liquida todo, una venta que solo
        # el puede cubrir, y las recompras que reconstruyen lo compartido.
        self.shared_buy = self.move(date(2021, 1, 1), Decimal("6"), Decimal("600"), self.shared)
        self.own_buy = self.move(date(2023, 1, 1), Decimal("4"), Decimal("800"), self.own)
        self.sale = self.move(date(2023, 6, 1), Decimal("-9"), Decimal("1800"), self.own)
        self.own_buy_two = self.move(date(2023, 7, 1), Decimal("3"), Decimal("600"), self.own)
        self.mid_sale = self.move(date(2023, 8, 1), Decimal("-2"), Decimal("400"), self.own)
        self.rebuild = self.move(date(2023, 9, 1), Decimal("5"), Decimal("1000"), self.own)

    def move(self, day, units, cash_amount, ownership):
        inflow = units > 0
        transaction = LedgerTransaction.objects.create(
            user=self.user,
            booking_date=day,
            value_date=day,
            description="Movimiento",
            quick_entry_kind=LedgerTransaction.QuickEntryKind.INVESTMENT,
            investment_direction=(
                LedgerTransaction.InvestmentDirection.INFLOW
                if inflow
                else LedgerTransaction.InvestmentDirection.OUTFLOW
            ),
            ownership=ownership,
            import_fingerprint=f"fp-{day}-{units}",
            import_source="test",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=self.pot,
            side=LedgerEntry.Side.DEBIT if inflow else LedgerEntry.Side.CREDIT,
            amount=abs(units),
            currency="BTC",
        )
        LedgerEntry.objects.create(
            transaction=transaction,
            account=self.cash,
            side=LedgerEntry.Side.CREDIT if inflow else LedgerEntry.Side.DEBIT,
            amount=cash_amount,
            currency="EUR",
        )
        return transaction

    def run_command(self, **overrides):
        out = StringIO()
        options = {
            "account_id": self.pot.id,
            "shared_ownership_id": self.shared.id,
            "own_ownership_id": self.own.id,
            "liquidation_date": "2023-06-01",
            "target_units": "4",
            "stdout": out,
        }
        options.update(overrides)
        call_command("split_commingled_ownership", **options)
        return out.getvalue()

    def pot_units(self, transaction):
        return transaction.entries.get(account=self.pot).amount

    def test_a_dry_run_writes_nothing(self):
        output = self.run_command()

        self.sale.refresh_from_db()
        self.assertIn("Nada escrito", output)
        self.assertEqual(self.sale.ownership_id, self.own.id)
        self.assertEqual(LedgerTransaction.objects.count(), 6)

    def test_the_liquidation_sells_the_shared_side_whole(self):
        self.run_command(apply=True, rebuild_from="2023-09-01")

        self.sale.refresh_from_db()
        copy = LedgerTransaction.objects.get(booking_date=date(2023, 6, 1), ownership=self.shared)
        # De las 9 vendidas, 6 eran compartidas y 3 suyas.
        self.assertEqual(self.pot_units(copy), Decimal("6.00000000"))
        self.assertEqual(self.pot_units(self.sale), Decimal("3.00000000"))
        self.assertEqual(self.sale.ownership_id, self.own.id)

    def test_a_split_keeps_both_legs_adding_up_to_the_original(self):
        self.run_command(apply=True, rebuild_from="2023-09-01")

        self.sale.refresh_from_db()
        copy = LedgerTransaction.objects.get(booking_date=date(2023, 6, 1), ownership=self.shared)
        cash = (
            copy.entries.get(account=self.cash).amount
            + self.sale.entries.get(account=self.cash).amount
        )
        units = self.pot_units(copy) + self.pot_units(self.sale)
        self.assertEqual(units, Decimal("9.00000000"))
        self.assertEqual(cash, Decimal("1800.00000000"))

    def test_the_copy_does_not_inherit_the_import_fingerprint(self):
        # Es unica por usuario y origen, y pertenece al asiento que si vino de la importacion.
        self.run_command(apply=True, rebuild_from="2023-09-01")

        copy = LedgerTransaction.objects.get(booking_date=date(2023, 6, 1), ownership=self.shared)
        self.assertEqual(copy.import_fingerprint, "")

    def test_rebuilding_later_leaves_the_middle_sale_to_the_individual_pocket(self):
        self.run_command(apply=True, rebuild_from="2023-09-01")

        self.own_buy_two.refresh_from_db()
        self.mid_sale.refresh_from_db()
        self.rebuild.refresh_from_db()
        # La compra de julio se queda suya para poder cubrir la venta de agosto, y lo
        # compartido se reconstruye de una vez en septiembre.
        self.assertEqual(self.own_buy_two.ownership_id, self.own.id)
        self.assertEqual(self.mid_sale.ownership_id, self.own.id)
        rebuilt = LedgerTransaction.objects.get(
            booking_date=date(2023, 9, 1), ownership=self.shared
        )
        self.assertEqual(self.pot_units(rebuilt), Decimal("4.00000000"))
        self.assertEqual(self.pot_units(self.rebuild), Decimal("1.00000000"))

    def test_rebuilding_right_away_eats_the_purchase_that_covered_the_sale(self):
        # Sin retrasar la reconstruccion, julio pasa a compartido y la venta de agosto se
        # come lo que se acaba de reconstruir: es justo lo que `--rebuild-from` evita.
        self.run_command(apply=True)

        self.own_buy_two.refresh_from_db()
        self.assertEqual(self.own_buy_two.ownership_id, self.shared.id)

    def test_an_unreachable_target_is_refused_instead_of_half_applied(self):
        with self.assertRaises(CommandError):
            self.run_command(apply=True, target_units="999")

        self.sale.refresh_from_db()
        self.assertEqual(self.sale.ownership_id, self.own.id)
        self.assertEqual(LedgerTransaction.objects.count(), 6)

    def test_tagging_an_outflow_shared_is_reported_and_applied(self):
        self.run_command(apply=True, rebuild_from="2023-09-01", tag_shared=[self.mid_sale.id])

        self.mid_sale.refresh_from_db()
        self.assertEqual(self.mid_sale.ownership_id, self.shared.id)
