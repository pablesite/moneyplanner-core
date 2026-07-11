from django.core.management.base import BaseCommand

from budget.models import AnnualExpenseEntry, AnnualIncomeEntry
from budget.plan_lineage import PLAN_EVENT_PREFIX, parse_plan_event_id
from plan.models import PlanEvent


class Command(BaseCommand):
    help = "Reporta partidas con linaje plan_event inválido o huérfano sin modificarlas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--repair-legacy-scenario-ids",
            action="store_true",
            help="Migra un ID de Scenario legado al ID de su PlanEvent cuando la relación es única.",
        )

    def handle(self, *args, **options):
        del args
        orphan_count = 0
        repaired_count = 0
        for model in (AnnualIncomeEntry, AnnualExpenseEntry):
            for entry in model.objects.filter(event_group__startswith=PLAN_EVENT_PREFIX).iterator():
                event_id = parse_plan_event_id(entry.event_group)
                valid = (
                    event_id is not None
                    and PlanEvent.objects.filter(id=event_id, plan__user_id=entry.user_id).exists()
                )
                if valid:
                    continue
                legacy_event = (
                    PlanEvent.objects.filter(
                        source_scenario_id=event_id, plan__user_id=entry.user_id
                    ).first()
                    if event_id is not None
                    else None
                )
                if legacy_event is not None and options["repair_legacy_scenario_ids"]:
                    entry.event_group = f"{PLAN_EVENT_PREFIX}{legacy_event.id}"
                    entry.save(update_fields=["event_group"])
                    repaired_count += 1
                    self.stdout.write(
                        f"REPARADA model={model.__name__} id={entry.id} "
                        f"event_group={entry.event_group}"
                    )
                    continue
                orphan_count += 1
                self.stdout.write(
                    f"HUERFANA model={model.__name__} id={entry.id} "
                    f"user_id={entry.user_id} event_group={entry.event_group}"
                )
        self.stdout.write(
            self.style.SUCCESS(
                f"Partidas huérfanas: {orphan_count}; partidas reparadas: {repaired_count}"
            )
        )
