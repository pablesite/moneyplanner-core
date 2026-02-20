from django.db import migrations, models
from django.utils import timezone


def backfill_fiscal_year(apps, schema_editor):
    AnnualIncomeEntry = apps.get_model("budget", "AnnualIncomeEntry")
    for entry in AnnualIncomeEntry.objects.all().iterator():
        if entry.created_at:
            entry.fiscal_year = entry.created_at.year
            entry.save(update_fields=["fiscal_year"])


class Migration(migrations.Migration):
    dependencies = [
        ("budget", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="annualincomeentry",
            name="fiscal_year",
            field=models.PositiveSmallIntegerField(default=timezone.now().year),
        ),
        migrations.RunPython(backfill_fiscal_year, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name="annualincomeentry",
            index=models.Index(fields=["user", "fiscal_year"], name="budget_ai_user_year_idx"),
        ),
    ]
