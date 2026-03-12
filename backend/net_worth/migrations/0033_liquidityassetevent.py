from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("net_worth", "0032_investmentassetevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="LiquidityAssetEvent",
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
                        help_text="Fecha efectiva del movimiento de liquidez.",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("inflow", "Entrada"),
                            ("outflow", "Salida"),
                            ("fee", "Comision"),
                            ("interest", "Interes"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=8,
                        help_text="Importe positivo del movimiento en la moneda del activo.",
                        max_digits=20,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("note", models.CharField(blank=True, default="", max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="liquidity_events",
                        to="net_worth.asset",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="liquidity_asset_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-event_date", "-updated_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="liquidityassetevent",
            index=models.Index(fields=["user", "event_date"], name="nw_liq_evt_user_date_idx"),
        ),
        migrations.AddIndex(
            model_name="liquidityassetevent",
            index=models.Index(fields=["asset", "event_date"], name="nw_liq_evt_asset_date_idx"),
        ),
    ]
