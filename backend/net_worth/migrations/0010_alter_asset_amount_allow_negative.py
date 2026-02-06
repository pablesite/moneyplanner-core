from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0009_remove_ownership_notes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="asset",
            name="amount",
            field=models.DecimalField(
                decimal_places=8,
                help_text="Valor actual (puede ser negativo). Si tracking_mode=accounting, este campo puede ignorarse en summary.",
                max_digits=20,
                validators=[],
            ),
        ),
    ]
