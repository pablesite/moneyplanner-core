from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0029_liability_cancellation_forecast"),
    ]

    operations = [
        migrations.AddField(
            model_name="liability",
            name="expense_subcategory_override",
            field=models.CharField(
                blank=True,
                choices=[
                    ("housing_home", "Vivienda y hogar"),
                    ("living_expenses", "Alimentacion"),
                    ("family_childcare", "Familia y bebe"),
                    ("transport_mobility", "Transporte y movilidad"),
                    ("health_wellbeing", "Salud y bienestar"),
                    ("education_growth", "Formacion y desarrollo"),
                    ("leisure_lifestyle", "Ocio y estilo de vida"),
                    ("gifts_donations", "Regalos y donaciones"),
                    ("financial_commitments", "Compromisos financieros"),
                    ("other_consumption_expenses", "Otros gastos de consumo"),
                ],
                help_text="Subcategoria tematica opcional para la salida presupuestaria generada desde este pasivo cuando no financia un activo concreto.",
                max_length=64,
                null=True,
            ),
        ),
    ]
