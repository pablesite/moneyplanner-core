from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.market_data import MarketDataSyncError, sync_market_data


class Command(BaseCommand):
    help = "Sync persisted market datasets used by Core."

    def add_arguments(self, parser):
        parser.add_argument(
            "--datasets",
            nargs="+",
            default=["fx", "inflation", "instrument_prices"],
            help="Datasets to sync. Supported: fx inflation instrument_prices.",
        )
        parser.add_argument(
            "--mode",
            default="reconcile",
            choices=["reconcile", "refresh"],
            help="Sync mode. reconcile backfills gaps, refresh only fetches incremental data.",
        )

    def handle(self, *args, **options):
        try:
            summary = sync_market_data(
                datasets=options.get("datasets"),
                mode=options.get("mode") or "reconcile",
            )
        except MarketDataSyncError as exc:
            raise CommandError(str(exc)) from exc

        for dataset, inserted in summary.items():
            self.stdout.write(self.style.SUCCESS(f"{dataset}: {inserted} rows upserted."))
