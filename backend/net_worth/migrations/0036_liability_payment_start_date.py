from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0035_alter_liquiditymonthlycheckin_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="liability",
            name="payment_start_date",
            field=models.DateField(
                blank=True,
                help_text=(
                    "Fecha de la primera cuota. Si se deja vacia, se usa el comportamiento "
                    "legacy (primera cuota un periodo despues de start_date)."
                ),
                null=True,
            ),
        ),
    ]
