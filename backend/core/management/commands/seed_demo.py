from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234demo"


def _d(v: str) -> Decimal:
    return Decimal(str(v).replace(",", "."))


class Command(BaseCommand):
    help = "Seed a demo user with realistic Spanish financial data (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        if User.objects.filter(username=DEMO_USERNAME).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Demo user '{DEMO_USERNAME}' already exists — skipping seed_demo."
                )
            )
            return

        # ── 1. Usuario ──────────────────────────────────────────────────────
        user = User.objects.create_user(
            username=DEMO_USERNAME,
            password=DEMO_PASSWORD,
            email="demo@example.es",
        )

        # UserSettings auto-created by signal; just update currency/region
        from accounts.models import UserSettings

        UserSettings.objects.filter(user=user).update(
            base_currency="EUR",
            inflation_region="ES",
        )

        # ── 2. Activos ───────────────────────────────────────────────────────
        from net_worth.models import Asset, AssetValuation, Liability, LiabilityValuation

        today = timezone.localdate()

        assets_data = [
            {
                "name": "Vivienda habitual",
                "category": Asset.Category.REAL_ESTATE,
                "subcategory": Asset.Subcategory.PRIMARY_HOME,
                "start_date": date(2018, 6, 1),
                "amount": _d("320000"),
            },
            {
                "name": "Cuenta corriente",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.BANK_ACCOUNT,
                "start_date": date(2015, 1, 1),
                "amount": _d("18500"),
            },
            {
                "name": "Cuenta ahorro",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.BANK_ACCOUNT,
                "start_date": date(2020, 3, 1),
                "amount": _d("8000"),
            },
            {
                "name": "Depósito 6 meses",
                "category": Asset.Category.CASH,
                "subcategory": Asset.Subcategory.SHORT_TERM_DEPOSIT,
                "start_date": date(2024, 9, 1),
                "amount": _d("12000"),
            },
            {
                "name": "Cartera ETFs globales",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.ETFS,
                "start_date": date(2021, 1, 1),
                "amount": _d("45000"),
            },
            {
                "name": "Plan de pensiones",
                "category": Asset.Category.INVESTMENTS,
                "subcategory": Asset.Subcategory.PENSION_PLANS,
                "start_date": date(2017, 1, 1),
                "amount": _d("28000"),
            },
            {
                "name": "Coche familiar",
                "category": Asset.Category.VEHICLE,
                "subcategory": Asset.Subcategory.VEHICLES,
                "start_date": date(2022, 4, 1),
                "amount": _d("22000"),
            },
        ]

        asset_objects: dict[str, Asset] = {}
        for data in assets_data:
            valuation_value = data["amount"]
            asset = Asset.objects.create(
                user=user,
                tracking_mode=Asset.TrackingMode.MANUAL,
                currency="EUR",
                **data,
            )
            AssetValuation.objects.create(
                user=user,
                asset=asset,
                valuation_date=today,
                value=valuation_value,
                source=AssetValuation.Source.MANUAL_CHECKPOINT,
            )
            asset_objects[asset.name] = asset

        # ── 3. Pasivos ───────────────────────────────────────────────────────
        vivienda = asset_objects["Vivienda habitual"]

        liabilities_data = [
            {
                "name": "Hipoteca vivienda",
                "category": Liability.Category.MORTGAGE,
                "start_date": date(2018, 6, 1),
                "amount": _d("210000"),
                "principal_amount": _d("280000"),
                "annual_interest_tae": _d("2.85"),
                "term_months": 300,
                "amortization_system": Liability.AmortizationSystem.FRENCH,
                "financed_asset": vivienda,
            },
            {
                "name": "Préstamo coche",
                "category": Liability.Category.PERSONAL_LOAN,
                "start_date": date(2022, 4, 1),
                "amount": _d("8500"),
                "principal_amount": _d("14000"),
                "annual_interest_tae": _d("4.20"),
                "term_months": 36,
                "amortization_system": Liability.AmortizationSystem.FRENCH,
                "financed_asset": asset_objects["Coche familiar"],
            },
        ]

        for data in liabilities_data:
            valuation_value = data["amount"]
            liability = Liability.objects.create(
                user=user,
                tracking_mode=Liability.TrackingMode.MANUAL,
                currency="EUR",
                rate_type=Liability.RateType.FIXED,
                payment_frequency=Liability.PaymentFrequency.MONTHLY,
                **data,
            )
            LiabilityValuation.objects.create(
                user=user,
                liability=liability,
                valuation_date=today,
                value=valuation_value,
                source=LiabilityValuation.Source.MANUAL_CHECKPOINT,
            )

        # ── 4. Presupuesto ───────────────────────────────────────────────────
        from budget.models import AnnualExpenseEntry, AnnualIncomeEntry

        fiscal_year = 2025

        incomes = [
            {
                "name": "Salario neto titular",
                "category": AnnualIncomeEntry.Category.SALARY,
                "subcategory": "salario",
                "amount_annual": _d("32400"),
                "amount_input_period": AnnualIncomeEntry.AmountInputPeriod.ANNUAL,
                "time_profile": AnnualIncomeEntry.TimeProfile.STRUCTURAL_RECURRENT,
                "cashflow_role": AnnualIncomeEntry.CashflowRole.OPERATING,
            },
            {
                "name": "Salario neto pareja",
                "category": AnnualIncomeEntry.Category.SALARY,
                "subcategory": "salario",
                "amount_annual": _d("28800"),
                "amount_input_period": AnnualIncomeEntry.AmountInputPeriod.ANNUAL,
                "time_profile": AnnualIncomeEntry.TimeProfile.STRUCTURAL_RECURRENT,
                "cashflow_role": AnnualIncomeEntry.CashflowRole.OPERATING,
            },
            {
                "name": "Dividendos ETFs",
                "category": AnnualIncomeEntry.Category.PASSIVE_INCOME,
                "subcategory": "dividendos",
                "amount_annual": _d("900"),
                "amount_input_period": AnnualIncomeEntry.AmountInputPeriod.ANNUAL,
                "time_profile": AnnualIncomeEntry.TimeProfile.STRUCTURAL_RECURRENT,
                "cashflow_role": AnnualIncomeEntry.CashflowRole.OPERATING,
            },
        ]

        for data in incomes:
            AnnualIncomeEntry.objects.create(
                user=user, fiscal_year=fiscal_year, currency="EUR", **data
            )

        expenses = [
            {
                "name": "Alimentación y hogar",
                "category": AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
                "subcategory": "alimentación",
                "amount_annual": _d("9600"),
            },
            {
                "name": "Suministros",
                "category": AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
                "subcategory": "suministros",
                "amount_annual": _d("2400"),
            },
            {
                "name": "Transporte",
                "category": AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
                "subcategory": "transporte",
                "amount_annual": _d("3600"),
            },
            {
                "name": "Salud",
                "category": AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
                "subcategory": "salud",
                "amount_annual": _d("1800"),
            },
            {
                "name": "Ocio y vacaciones",
                "category": AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
                "subcategory": "ocio",
                "amount_annual": _d("4800"),
            },
            {
                "name": "Formación",
                "category": AnnualExpenseEntry.Category.CONSUMPTION_EXPENSES,
                "subcategory": "formación",
                "amount_annual": _d("1200"),
            },
            {
                "name": "Aportación mensual ETFs",
                "category": AnnualExpenseEntry.Category.FINANCIAL_INVESTMENTS,
                "subcategory": "fondos",
                "amount_annual": _d("3600"),
            },
        ]

        for data in expenses:
            AnnualExpenseEntry.objects.create(
                user=user,
                fiscal_year=fiscal_year,
                currency="EUR",
                amount_input_period=AnnualExpenseEntry.AmountInputPeriod.ANNUAL,
                time_profile=AnnualExpenseEntry.TimeProfile.STRUCTURAL_RECURRENT,
                cashflow_role=AnnualExpenseEntry.CashflowRole.OPERATING,
                **data,
            )

        self.stdout.write(self.style.SUCCESS("Demo data created successfully."))
        self.stdout.write("")
        self.stdout.write("  Username : demo")
        self.stdout.write("  Password : demo1234demo")
        self.stdout.write("")
        self.stdout.write("  Open http://localhost:5173 and log in to explore the app.")
