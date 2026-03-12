from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("net_worth", "0031_assetvaluation_liabilityvaluation"),
    ]

    operations = [
        migrations.CreateModel(
            name="InvestmentAssetEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "event_date",
                    models.DateField(
                        default=django.utils.timezone.localdate,
                        help_text="Fecha efectiva del evento de inversion.",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("contribution", "Aportacion"),
                            ("withdrawal", "Retirada"),
                            ("fee", "Comision"),
                            ("passive_income", "Rendimiento"),
                        ],
                        max_length=24,
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=8,
                        help_text="Importe positivo del evento en la moneda del activo.",
                        max_digits=20,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "is_reinvested",
                    models.BooleanField(
                        default=True,
                        help_text="Solo aplica a passive_income. Si false, no incrementa el valor del activo.",
                    ),
                ),
                ("note", models.CharField(blank=True, default="", max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="investment_events",
                        to="net_worth.asset",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="investment_asset_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-event_date", "-updated_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="investmentassetevent",
            index=models.Index(fields=["user", "event_date"], name="nw_inv_evt_user_date_idx"),
        ),
        migrations.AddIndex(
            model_name="investmentassetevent",
            index=models.Index(fields=["asset", "event_date"], name="nw_inv_evt_asset_date_idx"),
        ),
    ]
