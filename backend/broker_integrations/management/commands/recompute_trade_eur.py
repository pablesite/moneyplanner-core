from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from broker_integrations.models import BrokerCredential, BrokerTrade
from broker_integrations.services.intraday_fx import IntradayFxError, get_rate_at


class Command(BaseCommand):
    help = "Recompute EUR price/fee fields for broker trades."

    def add_arguments(self, parser):
        parser.add_argument("--credential", type=int, required=True)
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--interval", type=str, default="1m")

    def handle(self, *args, **options):
        credential_id = options["credential"]
        year = options["year"]
        if options.get("interval") not in {"1m", "1h", "1d"}:
            raise CommandError("Interval must be one of: 1m, 1h, 1d.")
        credential = BrokerCredential.objects.filter(id=credential_id).first()
        if credential is None:
            raise CommandError(f"Credential {credential_id} not found.")

        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        queryset = BrokerTrade.objects.filter(
            credential=credential,
            timestamp__gte=start,
            timestamp__lt=end,
        ).order_by("timestamp", "id")

        updated = 0
        skipped = 0
        for trade in queryset.iterator(chunk_size=500):
            try:
                quote_rate, source = get_rate_at(timestamp=trade.timestamp, asset=trade.quote_asset)
                trade.price_eur = trade.price * quote_rate
                trade.fee_eur = Decimal("0")
                if trade.fee and trade.fee_asset:
                    fee_rate, _ = get_rate_at(timestamp=trade.timestamp, asset=trade.fee_asset)
                    trade.fee_eur = trade.fee * fee_rate
                trade.eur_rate_source = source
                trade.save(update_fields=["price_eur", "fee_eur", "eur_rate_source"])
                updated += 1
            except (IntradayFxError, ValueError):
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Recomputed EUR fields for credential={credential_id}, year={year}. "
                f"updated={updated}, skipped={skipped}"
            )
        )
