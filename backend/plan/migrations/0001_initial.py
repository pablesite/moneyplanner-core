import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_assumption_sets(apps, schema_editor):
    assumption_set = apps.get_model("plan", "AssumptionSet")
    rows = [
        {
            "name": "prudent",
            "inflation_rate": "0.0300",
            "productive_return_rate": "0.0350",
            "non_productive_appreciation_rate": "0.0050",
            "income_growth_rate": "0.0100",
            "contribution_growth_rate": "0.0100",
            "withdrawal_rate": "0.0300",
            "default_liability_rate": "0.0600",
            "is_default": False,
        },
        {
            "name": "expected",
            "inflation_rate": "0.0250",
            "productive_return_rate": "0.0500",
            "non_productive_appreciation_rate": "0.0150",
            "income_growth_rate": "0.0200",
            "contribution_growth_rate": "0.0200",
            "withdrawal_rate": "0.0350",
            "default_liability_rate": "0.0450",
            "is_default": True,
        },
        {
            "name": "favorable",
            "inflation_rate": "0.0200",
            "productive_return_rate": "0.0650",
            "non_productive_appreciation_rate": "0.0200",
            "income_growth_rate": "0.0300",
            "contribution_growth_rate": "0.0300",
            "withdrawal_rate": "0.0400",
            "default_liability_rate": "0.0350",
            "is_default": False,
        },
    ]
    for row in rows:
        assumption_set.objects.update_or_create(name=row["name"], defaults=row)


def unseed_assumption_sets(apps, schema_editor):
    assumption_set = apps.get_model("plan", "AssumptionSet")
    assumption_set.objects.filter(name__in=["prudent", "expected", "favorable"]).delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("memberships", "0006_familymember_plan_fields"),
        ("net_worth", "0042_remove_legacy_contribution_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssumptionSet",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=32, unique=True)),
                (
                    "inflation_rate",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=6,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                (
                    "productive_return_rate",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=6,
                        validators=[
                            django.core.validators.MinValueValidator(-1),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                (
                    "non_productive_appreciation_rate",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=6,
                        validators=[
                            django.core.validators.MinValueValidator(-1),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                (
                    "income_growth_rate",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=6,
                        validators=[
                            django.core.validators.MinValueValidator(-1),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                (
                    "contribution_growth_rate",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=6,
                        validators=[
                            django.core.validators.MinValueValidator(-1),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                (
                    "withdrawal_rate",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=6,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                (
                    "default_liability_rate",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=6,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="FinancialPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "household_type",
                    models.CharField(
                        choices=[("single", "Individual"), ("family", "Familiar")],
                        default="single",
                        max_length=16,
                    ),
                ),
                ("target_date", models.DateField()),
                (
                    "target_monthly_income_today_eur",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=14,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("projection_end_date", models.DateField()),
                (
                    "preservation_target_eur",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=14,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("preserved_asset_ids", models.JSONField(blank=True, null=True)),
                (
                    "profile",
                    models.CharField(
                        choices=[
                            ("security", "Seguridad"),
                            ("balanced", "Equilibrado"),
                            ("growth", "Crecimiento"),
                        ],
                        default="balanced",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Activo"), ("archived", "Archivado")],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "members",
                    models.ManyToManyField(
                        blank=True, related_name="financial_plans", to="memberships.familymember"
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="financial_plan",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="PlanAssetFunction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "function",
                    models.CharField(
                        choices=[
                            ("productive", "Productivo"),
                            ("security", "Seguridad"),
                            ("short_term_goal", "Objetivo corto plazo"),
                            ("family_use", "Uso familiar"),
                            ("unknown", "Desconocido"),
                        ],
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plan_function_overrides",
                        to="net_worth.asset",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plan_asset_functions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ProjectionSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("scenario", models.IntegerField(blank=True, null=True)),
                ("assumption_values", models.JSONField()),
                ("calculated_at", models.DateTimeField(auto_now_add=True)),
                ("input_hash", models.CharField(max_length=64)),
                ("result_json", models.JSONField()),
                ("quality_level", models.CharField(max_length=32)),
                ("is_official", models.BooleanField(default=True)),
                (
                    "assumption_set",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="projection_snapshots",
                        to="plan.assumptionset",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="projection_snapshots",
                        to="plan.financialplan",
                    ),
                ),
            ],
            options={"ordering": ["-calculated_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="assumptionset",
            index=models.Index(fields=["is_default"], name="plan_assump_is_defa_5e853d_idx"),
        ),
        migrations.AddIndex(
            model_name="financialplan",
            index=models.Index(fields=["user", "status"], name="plan_financ_user_id_dcc5b0_idx"),
        ),
        migrations.AddConstraint(
            model_name="planassetfunction",
            constraint=models.UniqueConstraint(
                fields=("user", "asset"), name="uniq_plan_asset_function_user"
            ),
        ),
        migrations.AddIndex(
            model_name="planassetfunction",
            index=models.Index(fields=["user", "function"], name="plan_planas_user_id_c00250_idx"),
        ),
        migrations.AddIndex(
            model_name="projectionsnapshot",
            index=models.Index(
                fields=["plan", "-calculated_at"], name="plan_projec_plan_id_e1c830_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="projectionsnapshot",
            index=models.Index(
                fields=["plan", "is_official"], name="plan_projec_plan_id_587a21_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="projectionsnapshot",
            index=models.Index(fields=["input_hash"], name="plan_projec_input_h_27643c_idx"),
        ),
        migrations.RunPython(seed_assumption_sets, reverse_code=unseed_assumption_sets),
    ]
