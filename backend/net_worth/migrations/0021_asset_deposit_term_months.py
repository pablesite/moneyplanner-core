from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0020_asset_estimated_average_balance_for_interest"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="deposit_term_months",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text=(
                    "Duracion del deposito a corto plazo en meses (1-12). "
                    "Solo aplica a subcategoria short_term_deposit."
                ),
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(12),
                ],
            ),
        ),
    ]
