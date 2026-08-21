import re

from django.db import migrations

SHARED_50_50_RE = re.compile(r"(\d+(?:\.\d+)?)%")


def _find_shared_5050_ownership(Ownership, user_id, cache):
    if user_id in cache:
        return cache[user_id]

    ownership = None
    for candidate in Ownership.objects.filter(
        user_id=user_id, kind="shared", allocation_basis="explicit_split"
    ):
        percents = list(candidate.splits.values_list("percent", flat=True))
        if len(percents) == 2 and all(p == 50 for p in percents):
            ownership = candidate
            break

    cache[user_id] = ownership
    return ownership


def _is_5050_label(owner_name: str) -> bool:
    percents = SHARED_50_50_RE.findall(owner_name)
    return len(percents) == 2 and {round(float(p)) for p in percents} == {50}


def link_shared_5050_ownership(apps, schema_editor):
    """Backfill the structured ownership FK for lines whose owner_name already
    says "Compartido X 50% / Y 50%" but were only ever saved as free text.

    The ratio is already correct; this only completes the link to the
    existing 50/50 shared Ownership record for that user, matching lines
    created before the ownership FK existed on these models.
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
            if not _is_5050_label(entry.owner_name):
                continue
            ownership = _find_shared_5050_ownership(Ownership, entry.user_id, ownership_cache)
            if ownership is None:
                continue
            entry.ownership_id = ownership.id
            entry.save(update_fields=["ownership"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("budget", "0020_monthlyclose_expected_liquidity_total_snapshot_and_more"),
        ("memberships", "0007_ownershipallocationsnapshot_and_more"),
    ]

    operations = [
        migrations.RunPython(link_shared_5050_ownership, noop_reverse),
    ]
