from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0028_asset_investment_contribution_currency"),
    ]

    operations = [
        migrations.AddField(
            model_name="liability",
            name="cancellation_date",
            field=models.DateField(
                blank=True,
                help_text="Fecha prevista de cancelacion anticipada (si aplica).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="cancellation_fee_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                help_text=(
                    "Comision de cancelacion anticipada (importe fijo). Si no se informa, "
                    "puede estimarse usando early_repayment_fee_percent."
                ),
                max_digits=20,
                null=True,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="cancellation_forecast_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Si true, modela una cancelacion anticipada prevista del pasivo y ajusta "
                    "la generacion de compromisos en presupuesto."
                ),
            ),
        ),
    ]
