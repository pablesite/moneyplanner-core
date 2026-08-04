from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


FINANCING_NOTE = "Generado automaticamente desde Mi Plan: financiacion prevista."
MONEY = Decimal("0.01")


def _annual_payment(*, principal, annual_rate, term_years):
    months = max(1, term_years * 12)
    monthly_rate = annual_rate / Decimal("12")
    if monthly_rate <= 0:
        return (principal / Decimal(max(1, term_years))).quantize(MONEY, rounding=ROUND_HALF_UP)
    factor = (Decimal("1") + monthly_rate) ** months
    monthly = principal * monthly_rate * factor / (factor - Decimal("1"))
    return (monthly * Decimal("12")).quantize(MONEY, rounding=ROUND_HALF_UP)


def backfill_planned_decision_financing(apps, schema_editor):
    plan_event_model = apps.get_model("plan", "PlanEvent")
    expense_model = apps.get_model("budget", "AnnualExpenseEntry")

    events = plan_event_model.objects.filter(status="planned", source_scenario__isnull=True)
    for event in events.iterator():
        event_group = f"plan_event:{event.id}"
        if expense_model.objects.filter(
            user_id=event.plan.user_id,
            event_group=event_group,
            is_system_generated=True,
            notes=FINANCING_NOTE,
        ).exists():
            continue

        for payload in event.planned_impact_json.get("events", []):
            principal = Decimal(str(payload.get("new_debt_principal") or "0"))
            term_years = int(str(payload.get("new_debt_term_years") or "0"))
            if principal <= 0 or term_years <= 0:
                continue

            start = date(
                int(payload["start_year"]),
                int(payload.get("start_month") or 1),
                1,
            )
            term_months = term_years * 12
            final_month_index = start.month - 1 + term_months - 1
            end = date(
                start.year + final_month_index // 12,
                final_month_index % 12 + 1,
                1,
            )
            annual_payment = _annual_payment(
                principal=principal,
                annual_rate=Decimal(str(payload.get("new_debt_interest_rate") or "0")),
                term_years=term_years,
            )
            monthly_payment = annual_payment / Decimal("12")
            is_housing = event.event_type == "housing"

            for year in range(start.year, end.year + 1):
                start_month = start.month if year == start.year else 1
                end_month = end.month if year == end.year else 12
                months = end_month - start_month + 1
                expense_model.objects.create(
                    user_id=event.plan.user_id,
                    is_system_generated=True,
                    name=f"{event.name} - financiacion",
                    category="real_estate_assets" if is_housing else "consumption_expenses",
                    subcategory="mortgage_principal" if is_housing else "personal_loan_repayment",
                    expense_type="recurrent",
                    time_profile="term_recurrent",
                    cashflow_role="temporary_commitment",
                    event_group=event_group,
                    term_start_month=start_month,
                    term_end_year=year,
                    term_end_month=end_month,
                    amount_annual=(monthly_payment * Decimal(months)).quantize(
                        MONEY, rounding=ROUND_HALF_UP
                    ),
                    fiscal_year=year,
                    currency="EUR",
                    notes=FINANCING_NOTE,
                )


def remove_backfilled_planned_decision_financing(apps, schema_editor):
    expense_model = apps.get_model("budget", "AnnualExpenseEntry")
    expense_model.objects.filter(
        is_system_generated=True,
        notes=FINANCING_NOTE,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("plan", "0009_assumptionset_furnishings_depreciation_rate"),
    ]

    operations = [
        migrations.RunPython(
            backfill_planned_decision_financing,
            remove_backfilled_planned_decision_financing,
        ),
    ]
