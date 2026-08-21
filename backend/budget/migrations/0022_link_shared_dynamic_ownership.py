import re

from django.db import migrations

SHARED_SPLIT_RE = re.compile(r"(\d+(?:\.\d+)?)%")


def _find_shared_dynamic_ownership(Ownership, user_id, cache):
    if user_id in cache:
        return cache[user_id]

    ownership = (
        Ownership.objects.filter(
            user_id=user_id, kind="shared", allocation_basis="recurring_income_12m"
        )
        .order_by("id")
        .first()
    )
    cache[user_id] = ownership
    return ownership


def _is_non_5050_shared_label(owner_name: str) -> bool:
    percents = SHARED_SPLIT_RE.findall(owner_name)
    return len(percents) == 2 and {round(float(p)) for p in percents} != {50}


def link_shared_dynamic_ownership(apps, schema_editor):
    """Replace the legacy fixed "Compartido X% / Y%" free-text split (a manual
    approximation of the real income-proportional share, predating the
    recurring-income-12m dynamic ownership feature) with a link to that
    user's dynamic shared Ownership, wherever one already exists.

    User-confirmed decision (2026-08-21): these lines should follow the real
    computed split instead of a stale fixed percentage.
    """
    Ownership = apps.get_model("memberships", "Ownership")

    ownership_cache: dict[int, object] = {}

    for app_label, model_name in (
        ("budget", "AnnualExpenseEntry"),
        ("budget", "AnnualIncomeEntry"),
    ):
        Entry = apps.get_model(app_label, model_name)
        candidates = Entry.objects.filter(
            ownership__isnull=True, owner_name__istartswith="Compartido"
        )
        for entry in candidates:
            if not _is_non_5050_shared_label(entry.owner_name):
                continue
            ownership = _find_shared_dynamic_ownership(Ownership, entry.user_id, ownership_cache)
            if ownership is None:
                continue
            entry.ownership_id = ownership.id
            entry.save(update_fields=["ownership"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("budget", "0021_link_shared_5050_ownership"),
    ]

    operations = [
        migrations.RunPython(link_shared_dynamic_ownership, noop_reverse),
    ]
