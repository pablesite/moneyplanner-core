from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("net_worth", "0015_liability_monthly_payment_amount"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="amortization_method",
            field=models.CharField(
                choices=[
                    ("none", "Sin amortizacion"),
                    ("straight_line", "Lineal"),
                    ("manual", "Manual"),
                ],
                default="none",
                help_text="Modelo de amortizacion/depreciacion del activo (si aplica).",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="amortization_term_years",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Vida util/plazo de amortizacion estimado en anos (si aplica).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="initial_purchase_value",
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                help_text=(
                    "Valor de compra inicial del activo en la moneda del activo. "
                    "Opcional si no se desea modelar amortizacion."
                ),
                max_digits=20,
                null=True,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="amortization_system",
            field=models.CharField(
                blank=True,
                choices=[
                    ("french", "Frances (cuota constante)"),
                    ("german", "Aleman (amortizacion constante)"),
                    ("american", "Americano"),
                    ("manual", "Manual"),
                ],
                help_text="Sistema de amortizacion (si se modela).",
                max_length=16,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="early_repayment_fee_percent",
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                help_text="Comision por amortizacion anticipada (% sobre capital amortizado), si aplica.",
                max_digits=6,
                null=True,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="expected_end_date",
            field=models.DateField(
                blank=True,
                help_text="Fecha prevista de finalizacion del pasivo (si se conoce).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="linked_products_monthly_cost",
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                help_text=(
                    "Coste mensual de productos vinculados (seguros, etc.) si se desea registrar "
                    "como metadata del pasivo."
                ),
                max_digits=20,
                null=True,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="novation_subrogation_fee_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                help_text="Coste estimado de novacion/subrogacion (importe), si aplica.",
                max_digits=20,
                null=True,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="opening_fees_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                help_text="Comisiones de apertura (importe) si aplica, especialmente en hipoteca.",
                max_digits=20,
                null=True,
                validators=[MinValueValidator(0)],
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="payment_frequency",
            field=models.CharField(
                choices=[
                    ("monthly", "Mensual"),
                    ("quarterly", "Trimestral"),
                    ("yearly", "Anual"),
                ],
                default="monthly",
                help_text="Frecuencia de pago prevista.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="rate_type",
            field=models.CharField(
                choices=[
                    ("fixed", "Fijo"),
                    ("variable", "Variable"),
                    ("mixed", "Mixto"),
                ],
                default="fixed",
                help_text="Comportamiento del tipo de interes del pasivo.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="liability",
            name="term_months",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Plazo previsto en meses (alternativa/complemento a expected_end_date).",
                null=True,
            ),
        ),
    ]
