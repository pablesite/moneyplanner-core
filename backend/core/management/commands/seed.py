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
            self.stdout.write(
                self.style.WARNING(f"Admin user '{username}' already exists (ensured flags).")
            )

        # Seed FX + IPC — fallback para primer arranque sin sync.
        # Solo inserta si el par/region no tiene ningún dato todavía.
        # El servicio market_data_sync sobreescribe esto con datos reales del INE/Frankfurter.
        rate_date = timezone.localdate() - timedelta(days=1)

        fx_fallbacks = [
            ("USD", "EUR", _d("0.85")),
            ("BTC", "EUR", _d("80000")),
            ("ETH", "EUR", _d("2000")),
        ]
        for f, t, r in fx_fallbacks:
            if not FxRate.objects.filter(from_currency=f, to_currency=t).exists():
                FxRate.objects.create(from_currency=f, to_currency=t, rate_date=rate_date, rate=r)
                self.stdout.write(f"  FX fallback creado: {f}->{t} {rate_date}")

        if not InflationIndex.objects.filter(region=InflationIndex.Region.ES).exists():
            InflationIndex.objects.create(
                region=InflationIndex.Region.ES,
                period=timezone.datetime(2012, 6, 1).date(),
                index=_d("100"),
            )
            InflationIndex.objects.create(
                region=InflationIndex.Region.ES,
                period=timezone.datetime(2025, 12, 1).date(),
                index=_d("126"),
            )
            self.stdout.write("  IPC fallback creado para ES.")

        self.stdout.write(self.style.SUCCESS(f"Seed FX + IPC done for rate_date={rate_date}."))
