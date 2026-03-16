from django.core.management.base import BaseCommand, CommandError

from accounting.services import backfill_ledger_entry_classification


class Command(BaseCommand):
    help = (
        "Backfill legacy ledger entries linked to annual budget rows into the "
        "new flow_family/category_key/subcategory_key classification fields."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="Limit the backfill to a single user id.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process at most N candidate ledger entries.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the backfill summary without persisting changes.",
        )

    def handle(self, *args, **options):
        user_id = options["user_id"]
        limit = options["limit"]
        dry_run = options["dry_run"]

        if limit is not None and limit < 1:
            raise CommandError("--limit must be greater than zero.")

        result = backfill_ledger_entry_classification(
            user_id=user_id,
            limit=limit,
            dry_run=dry_run,
        )

        mode_label = "DRY RUN" if result.dry_run else "APPLIED"
        self.stdout.write(
            f"[{mode_label}] scanned={result.scanned} updated={result.updated} "
            f"already_classified={result.already_classified} ambiguous={result.ambiguous}"
        )
        if result.ambiguous_reasons:
            for reason, count in result.ambiguous_reasons.items():
                self.stdout.write(f" - {reason}: {count}")
        elif result.ambiguous == 0:
            self.stdout.write(" - ambiguous_reasons: none")
