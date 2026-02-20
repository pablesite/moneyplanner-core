from django.conf import settings
from django.db import models
from django.utils import timezone


class AnnualIncomeEntry(models.Model):
    class Category(models.TextChoices):
        SALARY = "salary", "Salarios y trabajo"
        BUSINESS = "business", "Actividad profesional/negocio"
        PASSIVE_INCOME = "passive_income", "Ingresos pasivos"
        CAPITAL_GAINS = "capital_gains", "Ganancias de capital"
        TRANSFERS_SUPPORT = "transfers_support", "Transferencias y apoyo recibido"
        PUBLIC_BENEFITS = "public_benefits", "Prestaciones y ayudas"
        OTHER_INCOME = "other_income", "Otros ingresos"

    class IncomeType(models.TextChoices):
        RECURRENT = "recurrent", "Recurrente"
        ONE_OFF = "one_off", "Puntual"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="annual_income_entries"
    )
    name = models.CharField(max_length=140)
    category = models.CharField(max_length=32, choices=Category.choices)
    subcategory = models.CharField(max_length=64)
    owner_name = models.CharField(max_length=120, blank=True, default="")
    income_type = models.CharField(
        max_length=16, choices=IncomeType.choices, default=IncomeType.RECURRENT
    )
    amount_annual = models.DecimalField(max_digits=14, decimal_places=2)
    fiscal_year = models.PositiveSmallIntegerField(default=timezone.now().year)
    currency = models.CharField(max_length=3, default="EUR")
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_annualincomeentry"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(
                fields=["user", "fiscal_year"],
                name="budget_ai_user_year_idx",
            ),
            models.Index(fields=["user", "category"]),
            models.Index(fields=["user", "subcategory"]),
        ]

    def __str__(self) -> str:
        return (
            f"AnnualIncomeEntry(user={self.user_id}, name={self.name}, amount={self.amount_annual})"
        )


class AnnualExpenseEntry(models.Model):
    class Category(models.TextChoices):
        SAVINGS_ALLOCATION = "savings_allocation", "Ahorro"
        FINANCIAL_INVESTMENTS = "financial_investments", "Inversion financiera"
        REAL_ESTATE_ASSETS = "real_estate_assets", "Activos inmobiliarios"
        TANGIBLE_ASSETS = "tangible_assets", "Activos mobiliarios"
        CONSUMPTION_EXPENSES = "consumption_expenses", "Gasto puro y duro"

    class ExpenseType(models.TextChoices):
        RECURRENT = "recurrent", "Recurrente"
        ONE_OFF = "one_off", "Puntual"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="annual_expense_entries"
    )
    name = models.CharField(max_length=140)
    category = models.CharField(max_length=32, choices=Category.choices)
    subcategory = models.CharField(max_length=64)
    owner_name = models.CharField(max_length=120, blank=True, default="")
    expense_type = models.CharField(
        max_length=16, choices=ExpenseType.choices, default=ExpenseType.RECURRENT
    )
    amount_annual = models.DecimalField(max_digits=14, decimal_places=2)
    fiscal_year = models.PositiveSmallIntegerField(default=timezone.now().year)
    currency = models.CharField(max_length=3, default="EUR")
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_annualexpenseentry"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(
                fields=["user", "fiscal_year"],
                name="budget_ae_user_year_idx",
            ),
            models.Index(fields=["user", "category"]),
            models.Index(fields=["user", "subcategory"]),
        ]

    def __str__(self) -> str:
        return f"AnnualExpenseEntry(user={self.user_id}, name={self.name}, amount={self.amount_annual})"
