from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0016_asset_amortization_and_liability_schedule_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="liability",
            name="principal_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                help_text=(
                    "Capital inicial/original del pasivo. Si se informa junto con calendario/plazo, "
                    "permite estimar saldo pendiente actual automaticamente."
                ),
                max_digits=20,
                null=True,
                validators=[MinValueValidator(0)],
            ),
        ),
    ]
