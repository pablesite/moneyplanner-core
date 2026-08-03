from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from memberships.models import Ownership
from memberships.services_allocations import resolve_ownership_allocation


class Command(BaseCommand):
    help = "Audita repartos dinamicos sin crear ni actualizar snapshots."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int)
        parser.add_argument("--ownership-id", type=int)
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--month", type=int, required=True)

    def handle(self, *args, **options):
        user_id = options["user_id"]
        ownership_id = options["ownership_id"]
        fiscal_year = options["year"]
        month = options["month"]
        if not user_id and not ownership_id:
            raise CommandError("Indica --user-id o --ownership-id.")
        if month < 1 or month > 12 or fiscal_year < 1:
            raise CommandError("El periodo no es valido.")

        queryset = Ownership.objects.filter(
            kind=Ownership.Kind.SHARED,
            allocation_basis=Ownership.AllocationBasis.RECURRING_INCOME_12M,
        ).select_related("user", "member")
        if ownership_id:
            queryset = queryset.filter(id=ownership_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        results = [
            resolve_ownership_allocation(
                ownership=ownership,
                fiscal_year=fiscal_year,
                month=month,
                persist=False,
            )
            for ownership in queryset.order_by("id")
        ]
        self.stdout.write(json.dumps(results, ensure_ascii=True, sort_keys=True))
