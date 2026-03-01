from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("net_worth", "0019_liquiditymonthlycheckin"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="estimated_average_balance_for_interest",
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                help_text=(
                    "Saldo/importe anual medio previsto para estimar intereses en activos "
                    "de liquidez remunerados."
                ),
                max_digits=20,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
    ]
