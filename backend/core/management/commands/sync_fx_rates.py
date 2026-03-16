from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.market_data import sync_market_data, sync_market_history
from net_worth.models import Asset, Liability


class Command(BaseCommand):
    help = "Sync historical FX and crypto rates used by Core net worth timelines."

    def add_arguments(self, parser):
        parser.add_argument(
            "--currencies",
            nargs="+",
            default=None,
            help="List of source currencies to sync, e.g. USD BTC ETH.",
        )
        parser.add_argument(
            "--quote-currency",
            default="EUR",
            help="Target currency to store in FxRate. Defaults to EUR.",
        )
        parser.add_argument(
            "--start-date",
            default=None,
            help="Start date in YYYY-MM-DD. Required unless --for-active-positions is used.",
        )
        parser.add_argument(
            "--end-date",
            default=None,
            help="End date in YYYY-MM-DD. Defaults to today.",
        )
        parser.add_argument(
            "--for-active-positions",
            action="store_true",
            help="Inspect active assets and liabilities to infer currencies and historical start date.",
        )

    def handle(self, *args, **options):
        quote_currency = str(options["quote_currency"] or "EUR").upper().strip()
        end_date = self._parse_optional_date(options.get("end_date")) or timezone.localdate()

        inferred_ranges: dict[str, date] = {}
        if options.get("for_active_positions"):
            if not options.get("currencies") and not options.get("start_date"):
                summary = sync_market_data(datasets=["fx"], mode="reconcile")
                total_rows = summary.get("fx", 0)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Delegated to sync_market_data --datasets fx --mode reconcile. Total rows upserted: {total_rows}."
                    )
                )
                return
            inferred_ranges = self._collect_position_ranges(quote_currency=quote_currency)

        explicit_currencies = [
            str(code).upper().strip() for code in options.get("currencies") or []
        ]
        explicit_start_date = self._parse_optional_date(options.get("start_date"))
        if explicit_currencies and explicit_start_date is None and not inferred_ranges:
            raise CommandError(
                "--start-date is required when using --currencies without --for-active-positions."
            )

        for currency in explicit_currencies:
            inferred_ranges.setdefault(currency, explicit_start_date)

        if not inferred_ranges:
            raise CommandError(
                "Nothing to sync. Provide --for-active-positions or --currencies with --start-date."
            )

        total_rows = 0
        for currency, start_date in sorted(inferred_ranges.items()):
            if not start_date or currency == quote_currency:
                continue
            inserted = sync_market_history(
                from_currency=currency,
                to_currency=quote_currency,
                start_date=start_date,
                end_date=end_date,
            )
            total_rows += inserted
            self.stdout.write(
                self.style.SUCCESS(
                    f"Synced {currency}->{quote_currency} from {start_date} to {end_date}: {inserted} rows."
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Done. Total rows upserted: {total_rows}."))

    def _parse_optional_date(self, raw_value: str | None) -> date | None:
        if not raw_value:
            return None
        try:
            return date.fromisoformat(str(raw_value))
        except ValueError as exc:
            raise CommandError(f"Invalid date '{raw_value}'. Use YYYY-MM-DD.") from exc

    def _collect_position_ranges(self, *, quote_currency: str) -> dict[str, date]:
        ranges: dict[str, date] = {}
        active_assets = Asset.objects.filter(is_active=True).exclude(currency=quote_currency)
        active_liabilities = Liability.objects.filter(is_active=True).exclude(
            currency=quote_currency
        )

        for position in list(active_assets) + list(active_liabilities):
            currency = str(position.currency or "").upper().strip()
            if not currency or currency == quote_currency:
                continue
            current_start = ranges.get(currency)
            if current_start is None or position.start_date < current_start:
                ranges[currency] = position.start_date
        return ranges
