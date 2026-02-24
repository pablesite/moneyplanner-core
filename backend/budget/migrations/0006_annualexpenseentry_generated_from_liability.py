from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0017_liability_principal_amount"),
        ("budget", "0005_annualentry_cashflow_dimensions"),
    ]

    operations = [
        migrations.AddField(
            model_name="annualexpenseentry",
            name="is_system_generated",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="annualexpenseentry",
            name="source_liability",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="generated_annual_expense_entries",
                to="net_worth.liability",
            ),
        ),
        migrations.AddIndex(
            model_name="annualexpenseentry",
            index=models.Index(
                fields=["user", "is_system_generated"], name="budget_ae_user_sysgen_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="annualexpenseentry",
            index=models.Index(fields=["source_liability"], name="budget_ae_src_liab_idx"),
        ),
    ]
