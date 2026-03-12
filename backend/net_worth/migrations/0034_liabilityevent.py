from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("net_worth", "0033_liquidityassetevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="LiabilityEvent",
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
                        help_text="Fecha efectiva del movimiento del pasivo.",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("charge", "Cargo"),
                            ("payment", "Pago"),
                            ("fee", "Comision"),
                            ("interest", "Interes"),
                            ("adjustment", "Ajuste"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=8,
                        help_text="Importe positivo del movimiento en la moneda del pasivo.",
                        max_digits=20,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("note", models.CharField(blank=True, default="", max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "liability",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="net_worth.liability",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="liability_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-event_date", "-updated_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="liabilityevent",
            index=models.Index(fields=["user", "event_date"], name="nw_liab_evt_user_date_idx"),
        ),
        migrations.AddIndex(
            model_name="liabilityevent",
            index=models.Index(
                fields=["liability", "event_date"], name="nw_liab_evt_liab_date_idx"
            ),
        ),
    ]
