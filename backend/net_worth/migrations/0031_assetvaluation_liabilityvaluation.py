from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("net_worth", "0030_liability_expense_subcategory_override"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssetValuation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "valuation_date",
                    models.DateField(
                        default=django.utils.timezone.localdate,
                        help_text="Fecha de valoracion manual del activo (as-of).",
                    ),
                ),
                (
                    "value",
                    models.DecimalField(
                        decimal_places=8,
                        help_text="Valor observado/manual del activo en su moneda.",
                        max_digits=20,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manual_checkpoint", "Checkpoint manual"),
                            ("imported", "Importado"),
                            ("system", "Sistema"),
                        ],
                        default="manual_checkpoint",
                        max_length=32,
                    ),
                ),
                ("note", models.CharField(blank=True, default="", max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="valuations",
                        to="net_worth.asset",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asset_valuations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-valuation_date", "-updated_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="LiabilityValuation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "valuation_date",
                    models.DateField(
                        default=django.utils.timezone.localdate,
                        help_text="Fecha de valoracion manual del pasivo (as-of).",
                    ),
                ),
                (
                    "value",
                    models.DecimalField(
                        decimal_places=8,
                        help_text="Saldo/valor observado del pasivo en su moneda.",
                        max_digits=20,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manual_checkpoint", "Checkpoint manual"),
                            ("imported", "Importado"),
                            ("system", "Sistema"),
                        ],
                        default="manual_checkpoint",
                        max_length=32,
                    ),
                ),
                ("note", models.CharField(blank=True, default="", max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "liability",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="valuations",
                        to="net_worth.liability",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="liability_valuations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-valuation_date", "-updated_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="assetvaluation",
            index=models.Index(
                fields=["user", "valuation_date"], name="nw_asset_val_user_date_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="assetvaluation",
            index=models.Index(
                fields=["asset", "valuation_date"], name="nw_asset_val_asset_date_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="assetvaluation",
            constraint=models.UniqueConstraint(
                fields=("user", "asset", "valuation_date"),
                name="unique_asset_valuation_user_asset_date",
            ),
        ),
        migrations.AddIndex(
            model_name="liabilityvaluation",
            index=models.Index(
                fields=["user", "valuation_date"], name="nw_liability_val_user_date_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="liabilityvaluation",
            index=models.Index(
                fields=["liability", "valuation_date"], name="nw_liability_val_liab_date_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="liabilityvaluation",
            constraint=models.UniqueConstraint(
                fields=("user", "liability", "valuation_date"),
                name="unique_liability_valuation_user_liability_date",
            ),
        ),
    ]
