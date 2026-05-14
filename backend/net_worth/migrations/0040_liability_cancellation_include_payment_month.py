from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0039_migrate_legacy_contribution_intervals"),
    ]

    operations = [
        migrations.AddField(
            model_name="liability",
            name="cancellation_include_payment_month",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Si true, incluye la cuota periodica del mismo mes en el que se cancela "
                    "anticipadamente el pasivo."
                ),
            ),
        ),
    ]
