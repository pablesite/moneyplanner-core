from django.db import migrations, models


def backfill_budget_cashflow_dimensions(apps, schema_editor):
    AnnualIncomeEntry = apps.get_model("budget", "AnnualIncomeEntry")
    AnnualExpenseEntry = apps.get_model("budget", "AnnualExpenseEntry")

    for entry in AnnualIncomeEntry.objects.all().iterator():
        if entry.income_type == "one_off":
            entry.time_profile = "one_off"
        else:
            entry.time_profile = "structural_recurrent"

        if entry.category == "capital_gains":
            entry.cashflow_role = "asset_sale"
        elif entry.category in {"transfers_support", "public_benefits"}:
            entry.cashflow_role = "transfer"
        elif entry.category == "other_income":
            entry.cashflow_role = "other"
        else:
            entry.cashflow_role = "operating"
        entry.save(update_fields=["time_profile", "cashflow_role"])

    for entry in AnnualExpenseEntry.objects.all().iterator():
        if entry.expense_type == "one_off":
            entry.time_profile = "one_off"
        else:
            entry.time_profile = "structural_recurrent"

        if entry.category == "savings_allocation":
            entry.cashflow_role = "savings"
        elif entry.category == "financial_investments":
            entry.cashflow_role = "investment"
        elif entry.category in {"real_estate_assets", "tangible_assets"}:
            if entry.subcategory == "real_estate_fees_taxes":
                entry.cashflow_role = "tax_fee"
            else:
                entry.cashflow_role = "asset_purchase"
        else:
            entry.cashflow_role = "operating"
        entry.save(update_fields=["time_profile", "cashflow_role"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("budget", "0004_alter_annualexpenseentry_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="annualincomeentry",
            name="cashflow_role",
            field=models.CharField(
                choices=[
                    ("operating", "Operativo"),
                    ("transfer", "Transferencia"),
                    ("asset_sale", "Venta de activo"),
                    ("tax_adjustment", "Ajuste fiscal"),
                    ("other", "Otro"),
                ],
                default="operating",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="annualincomeentry",
            name="event_group",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="annualincomeentry",
            name="term_end_year",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="annualincomeentry",
            name="time_profile",
            field=models.CharField(
                choices=[
                    ("structural_recurrent", "Recurrente estructural"),
                    ("term_recurrent", "Recurrente temporal"),
                    ("one_off", "Puntual"),
                ],
                default="structural_recurrent",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="annualexpenseentry",
            name="cashflow_role",
            field=models.CharField(
                choices=[
                    ("operating", "Operativo"),
                    ("temporary_commitment", "Compromiso temporal"),
                    ("savings", "Ahorro"),
                    ("investment", "Inversion"),
                    ("asset_purchase", "Compra de activo"),
                    ("tax_fee", "Impuestos y gastos"),
                    ("transfer", "Transferencia"),
                    ("other", "Otro"),
                ],
                default="operating",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="annualexpenseentry",
            name="event_group",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="annualexpenseentry",
            name="term_end_year",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="annualexpenseentry",
            name="time_profile",
            field=models.CharField(
                choices=[
                    ("structural_recurrent", "Recurrente estructural"),
                    ("term_recurrent", "Recurrente temporal"),
                    ("one_off", "Puntual"),
                ],
                default="structural_recurrent",
                max_length=24,
            ),
        ),
        migrations.RunPython(backfill_budget_cashflow_dimensions, noop_reverse),
    ]
