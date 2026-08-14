from django.db import migrations


def backfill_deterministic_budget_ownership(apps, schema_editor):
    Ownership = apps.get_model("memberships", "Ownership")
    Income = apps.get_model("budget", "AnnualIncomeEntry")
    Expense = apps.get_model("budget", "AnnualExpenseEntry")

    for ownership in Ownership.objects.select_related("member").prefetch_related("splits__member"):
        if ownership.kind == "individual":
            label = ownership.member.name if ownership.member_id else ""
        else:
            splits = sorted(ownership.splits.all(), key=lambda split: split.member_id)
            members = " / ".join(
                f"{split.member.name} {split.percent.normalize()}%" for split in splits
            )
            label = f"Compartido ({members})" if members else ""
        if not label:
            continue
        for model in (Income, Expense):
            model.objects.filter(
                user_id=ownership.user_id,
                ownership__isnull=True,
                owner_name=label,
            ).update(ownership_id=ownership.id)


class Migration(migrations.Migration):
    dependencies = [
        ("budget", "0017_annualexpenseentry_ownership_and_more"),
        ("plan", "0011_planevent_ownership"),
    ]

    operations = [
        migrations.RunPython(backfill_deterministic_budget_ownership, migrations.RunPython.noop),
    ]
