import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction


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
