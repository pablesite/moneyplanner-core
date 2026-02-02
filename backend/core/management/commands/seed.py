import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from core.models import FxRate, InflationIndex

def _d(v: str) -> Decimal:
    return Decimal(str(v).strip().replace(",", "."))


class Command(BaseCommand):
    help = "Seed minimal initial data for local/dev (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        create_admin = os.getenv("SEED_CREATE_ADMIN", "1") == "1"
        username = os.getenv("SEED_ADMIN_USERNAME", "admin")
        email = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
        password = os.getenv("SEED_ADMIN_PASSWORD", "admin")
        force_password = os.getenv("SEED_FORCE_ADMIN_PASSWORD", "0") == "1"

        if not create_admin:
            self.stdout.write("SEED_CREATE_ADMIN=0 -> skipping admin user creation.")
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        # Asegurar flags (por si ya existía)
        changed = False
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if email and user.email != email:
            user.email = email
            changed = True

        if created or force_password:
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created admin user '{username}'."))
        else:
            self.stdout.write(self.style.WARNING(f"Admin user '{username}' already exists (ensured flags)."))

        


        # Seed FX + IPC (mínimo viable)
        rate_date = timezone.localdate() - timedelta(days=1)

        # FX (triangulación vía USD)
        fx_rows = [
            ("USD", "EUR", _d("0,85")),
            ("BTC", "USD", _d("78281")),
            ("ETH", "USD", _d("2332,96")),
        ]

        for f, t, r in fx_rows:
            FxRate.objects.update_or_create(
                from_currency=f,
                to_currency=t,
                rate_date=rate_date,
                defaults={"rate": r},
            )

        # IPC mensual (period siempre YYYY-MM-01)
        base_period = timezone.datetime(2012, 6, 1).date()
        current_period = timezone.datetime(2025, 12, 1).date()

        InflationIndex.objects.update_or_create(
            region=InflationIndex.Region.ES,
            period=base_period,
            defaults={"index": _d("100")},
        )
        InflationIndex.objects.update_or_create(
            region=InflationIndex.Region.ES,
            period=current_period,
            defaults={"index": _d("126")},
        )

        self.stdout.write(self.style.SUCCESS(f"Seed FX + IPC done for rate_date={rate_date}."))

