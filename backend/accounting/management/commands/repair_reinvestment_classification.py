"""Remove stale budget classifications from a recorded investment reinvestment.

An investment-to-investment reinvestment has no operating cash flow. Older rows could retain
the capital-gain classification from an earlier sale shape, making the monthly close count an
internal transfer as income. This command deliberately requires an explicit transaction id and
only writes after ``--apply``.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction

from accounting.models import LedgerTransaction


class Command(BaseCommand):
    help = "Quita clasificaciones funcionales antiguas de una reinversion entre inversiones."

    def add_arguments(self, parser):
        parser.add_argument("--transaction-id", type=int, required=True)
        parser.add_argument("--apply", action="store_true", help="Escribe. Sin esto solo revisa.")

    def handle(self, *args, **options):
        try:
            transaction = LedgerTransaction.objects.prefetch_related("entries").get(
                id=options["transaction_id"]
            )
        except LedgerTransaction.DoesNotExist as error:
            raise CommandError("Asiento inexistente.") from error

        if (
            transaction.quick_entry_kind != LedgerTransaction.QuickEntryKind.INVESTMENT
            or transaction.investment_direction
            != LedgerTransaction.InvestmentDirection.REINVESTMENT
        ):
            raise CommandError("El asiento indicado no es una reinversion.")

        classified_entries = [
            entry
            for entry in transaction.entries.all()
            if entry.flow_family or entry.category_key or entry.subcategory_key
        ]
        self.stdout.write(
            f"tx{transaction.id} {transaction.booking_date} {transaction.description}: "
            f"{len(classified_entries)} apuntes clasificados."
        )
        if not classified_entries:
            self.stdout.write(self.style.SUCCESS("Ya estaba corregido."))
            return
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("En seco. Nada escrito. Usa --apply."))
            return

        with db_transaction.atomic():
            for entry in classified_entries:
                entry.flow_family = ""
                entry.category_key = ""
                entry.subcategory_key = ""
                entry.save(update_fields=["flow_family", "category_key", "subcategory_key"])
        self.stdout.write(self.style.SUCCESS(f"Corregidos {len(classified_entries)} apuntes."))
