from __future__ import annotations

from dataclasses import dataclass

from django.apps import apps

PLAN_EVENT_PREFIX = "plan_event:"


@dataclass(frozen=True)
class PlanLineage:
    is_managed: bool
    event_id: int | None = None
    event_name: str | None = None


def parse_plan_event_id(event_group: str) -> int | None:
    if not event_group.startswith(PLAN_EVENT_PREFIX):
        return None
    try:
        value = int(event_group.removeprefix(PLAN_EVENT_PREFIX))
    except ValueError:
        return None
    return value if value > 0 else None


def plan_lineage_for_entry(entry) -> PlanLineage:
    cached = getattr(entry, "_plan_lineage_cache", None)
    if cached is not None:
        return cached
    event_id = parse_plan_event_id(entry.event_group or "")
    if event_id is None:
        result = PlanLineage(is_managed=False)
        entry._plan_lineage_cache = result
        return result
    plan_event_model = apps.get_model("plan", "PlanEvent")
    event = plan_event_model.objects.filter(id=event_id, plan__user_id=entry.user_id).first()
    if event is None:
        result = PlanLineage(is_managed=False)
        entry._plan_lineage_cache = result
        return result
    result = PlanLineage(is_managed=True, event_id=event.id, event_name=event.name)
    entry._plan_lineage_cache = result
    return result


def is_reserved_plan_event_group(value: str) -> bool:
    return value.strip().startswith(PLAN_EVENT_PREFIX)
