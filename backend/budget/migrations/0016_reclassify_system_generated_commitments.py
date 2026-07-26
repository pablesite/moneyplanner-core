from __future__ import annotations

from django.db import migrations


def reclassify_forward(apps, schema_editor):
    """Restaura el invariante temporary_commitment <-> term_recurrent en las
    partidas generadas por el sistema que lo rompian.

    1. Aportaciones periodicas generadas desde activos de inversion: eran
       `temporary_commitment` pese a ser `structural_recurrent`; son destino de
       ahorro/inversion, no un compromiso que consuma renta -> `investment`.
    2. Cancelaciones anticipadas de principal: eran `temporary_commitment` pese a
       ser `one_off`; son un movimiento de balance puntual -> `transfer`.
    """
    AnnualExpenseEntry = apps.get_model("budget", "AnnualExpenseEntry")

    AnnualExpenseEntry.objects.filter(
        is_system_generated=True,
        source_asset__isnull=False,
        cashflow_role="temporary_commitment",
    ).update(cashflow_role="investment")

    AnnualExpenseEntry.objects.filter(
        is_system_generated=True,
        time_profile="one_off",
        event_group__endswith="_cancellation_principal",
        cashflow_role="temporary_commitment",
    ).update(cashflow_role="transfer")


def reclassify_backward(apps, schema_editor):
    AnnualExpenseEntry = apps.get_model("budget", "AnnualExpenseEntry")

    AnnualExpenseEntry.objects.filter(
        is_system_generated=True,
        source_asset__isnull=False,
        cashflow_role="investment",
    ).update(cashflow_role="temporary_commitment")

    AnnualExpenseEntry.objects.filter(
        is_system_generated=True,
        time_profile="one_off",
        event_group__endswith="_cancellation_principal",
        cashflow_role="transfer",
    ).update(cashflow_role="temporary_commitment")


class Migration(migrations.Migration):
    dependencies = [
        ("budget", "0015_annualexpenseentry_term_start_month_and_more"),
    ]

    operations = [
        migrations.RunPython(reclassify_forward, reclassify_backward),
    ]
