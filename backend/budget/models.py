from django.conf import settings
from django.db import models
from django.utils import timezone


class AnnualIncomeEntry(models.Model):
    class AmountInputPeriod(models.TextChoices):
        ANNUAL = "annual", "Anual"
        MONTHLY = "monthly", "Mensual"

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

    class TimeProfile(models.TextChoices):
        STRUCTURAL_RECURRENT = "structural_recurrent", "Recurrente estructural"
        TERM_RECURRENT = "term_recurrent", "Recurrente temporal"
        ONE_OFF = "one_off", "Puntual"

    class CashflowRole(models.TextChoices):
        OPERATING = "operating", "Operativo"
        TRANSFER = "transfer", "Transferencia"
        ASSET_SALE = "asset_sale", "Venta de activo"
        TAX_ADJUSTMENT = "tax_adjustment", "Ajuste fiscal"
        OTHER = "other", "Otro"

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
    time_profile = models.CharField(
        max_length=24, choices=TimeProfile.choices, default=TimeProfile.STRUCTURAL_RECURRENT
    )
    cashflow_role = models.CharField(
        max_length=24, choices=CashflowRole.choices, default=CashflowRole.OPERATING
    )
    event_group = models.CharField(max_length=64, blank=True, default="")
    target_month = models.PositiveSmallIntegerField(null=True, blank=True)
    term_end_month = models.PositiveSmallIntegerField(null=True, blank=True)
    term_end_year = models.PositiveSmallIntegerField(null=True, blank=True)
    amount_input_period = models.CharField(
        max_length=8, choices=AmountInputPeriod.choices, default=AmountInputPeriod.ANNUAL
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
    class AmountInputPeriod(models.TextChoices):
        ANNUAL = "annual", "Anual"
        MONTHLY = "monthly", "Mensual"

    class Category(models.TextChoices):
        SAVINGS_ALLOCATION = "savings_allocation", "Ahorro"
        FINANCIAL_INVESTMENTS = "financial_investments", "Inversión financiera"
        REAL_ESTATE_ASSETS = "real_estate_assets", "Activos inmobiliarios"
        TANGIBLE_ASSETS = "tangible_assets", "Activos mobiliarios"
        CONSUMPTION_EXPENSES = "consumption_expenses", "Gastos"

    class ExpenseType(models.TextChoices):
        RECURRENT = "recurrent", "Recurrente"
        ONE_OFF = "one_off", "Puntual"

    class TimeProfile(models.TextChoices):
        STRUCTURAL_RECURRENT = "structural_recurrent", "Recurrente estructural"
        TERM_RECURRENT = "term_recurrent", "Recurrente temporal"
        ONE_OFF = "one_off", "Puntual"

    class CashflowRole(models.TextChoices):
        OPERATING = "operating", "Operativo"
        TEMPORARY_COMMITMENT = "temporary_commitment", "Compromiso temporal"
        SAVINGS = "savings", "Ahorro"
        INVESTMENT = "investment", "Inversión"
        ASSET_PURCHASE = "asset_purchase", "Compra de activo"
        TAX_FEE = "tax_fee", "Impuestos y gastos"
        TRANSFER = "transfer", "Transferencia"
        OTHER = "other", "Otro"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="annual_expense_entries"
    )
    source_liability = models.ForeignKey(
        "net_worth.Liability",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="generated_annual_expense_entries",
    )
    source_asset = models.ForeignKey(
        "net_worth.Asset",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="generated_annual_expense_entries",
    )
    is_system_generated = models.BooleanField(default=False)
    name = models.CharField(max_length=140)
    category = models.CharField(max_length=32, choices=Category.choices)
    subcategory = models.CharField(max_length=64)
    owner_name = models.CharField(max_length=120, blank=True, default="")
    expense_type = models.CharField(
        max_length=16, choices=ExpenseType.choices, default=ExpenseType.RECURRENT
    )
    time_profile = models.CharField(
        max_length=24, choices=TimeProfile.choices, default=TimeProfile.STRUCTURAL_RECURRENT
    )
    cashflow_role = models.CharField(
        max_length=24, choices=CashflowRole.choices, default=CashflowRole.OPERATING
    )
    event_group = models.CharField(max_length=64, blank=True, default="")
    target_month = models.PositiveSmallIntegerField(null=True, blank=True)
    term_end_month = models.PositiveSmallIntegerField(null=True, blank=True)
    term_end_year = models.PositiveSmallIntegerField(null=True, blank=True)
    amount_input_period = models.CharField(
        max_length=8, choices=AmountInputPeriod.choices, default=AmountInputPeriod.ANNUAL
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
            models.Index(fields=["user", "is_system_generated"], name="budget_ae_user_sysgen_idx"),
            models.Index(
                fields=["user", "fiscal_year"],
                name="budget_ae_user_year_idx",
            ),
            models.Index(fields=["user", "category"]),
            models.Index(fields=["user", "subcategory"]),
            models.Index(fields=["source_liability"], name="budget_ae_src_liab_idx"),
            models.Index(fields=["source_asset"], name="budget_ae_src_asset_idx"),
        ]

    def __str__(self) -> str:
        return f"AnnualExpenseEntry(user={self.user_id}, name={self.name}, amount={self.amount_annual})"


class AnnualExpenseMonthlyCheckin(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmado"
        ADJUSTED = "adjusted", "Ajustado"
        SKIPPED = "skipped", "No ocurrido"
        ESTIMATED = "estimated", "Estimado"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="annual_expense_monthly_checkins",
    )
    annual_expense_entry = models.ForeignKey(
        AnnualExpenseEntry,
        on_delete=models.CASCADE,
        related_name="monthly_checkins",
    )
    fiscal_year = models.PositiveSmallIntegerField(default=timezone.now().year)
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    executed_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=240, blank=True, default="")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_annualexpensemonthlycheckin"
        ordering = ["-fiscal_year", "-month", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "annual_expense_entry", "fiscal_year", "month"],
                name="budget_aemc_unique_user_entry_year_month",
            )
        ]
        indexes = [
            models.Index(fields=["user", "fiscal_year", "month"], name="budget_aemc_user_ym_idx"),
            models.Index(fields=["annual_expense_entry"], name="budget_aemc_entry_idx"),
        ]

    def __str__(self) -> str:
        return (
            "AnnualExpenseMonthlyCheckin("
            f"user={self.user_id}, entry={self.annual_expense_entry_id}, "
            f"year={self.fiscal_year}, month={self.month}, status={self.status})"
        )


class AnnualIncomeMonthlyCheckin(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmado"
        ADJUSTED = "adjusted", "Ajustado"
        SKIPPED = "skipped", "No ocurrido"
        ESTIMATED = "estimated", "Estimado"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="annual_income_monthly_checkins",
    )
    annual_income_entry = models.ForeignKey(
        AnnualIncomeEntry,
        on_delete=models.CASCADE,
        related_name="monthly_checkins",
    )
    fiscal_year = models.PositiveSmallIntegerField(default=timezone.now().year)
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    executed_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=240, blank=True, default="")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_annualincomemonthlycheckin"
        ordering = ["-fiscal_year", "-month", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "annual_income_entry", "fiscal_year", "month"],
                name="budget_aimc_unique_user_entry_year_month",
            )
        ]
        indexes = [
            models.Index(fields=["user", "fiscal_year", "month"], name="budget_aimc_user_ym_idx"),
            models.Index(fields=["annual_income_entry"], name="budget_aimc_entry_idx"),
        ]

    def __str__(self) -> str:
        return (
            "AnnualIncomeMonthlyCheckin("
            f"user={self.user_id}, entry={self.annual_income_entry_id}, "
            f"year={self.fiscal_year}, month={self.month}, status={self.status})"
        )


class MonthlyClose(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        FINALIZED = "finalized", "Finalizado"
        LOCKED = "locked", "Bloqueado"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="monthly_closes",
    )
    fiscal_year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    finalized_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    income_total_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    expense_total_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    liquidity_total_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_monthlyclose"
        ordering = ["-fiscal_year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "fiscal_year", "month"],
                name="budget_mc_unique_user_year_month",
            )
        ]
        indexes = [
            models.Index(fields=["user", "fiscal_year", "month"], name="budget_mc_user_ym_idx"),
            models.Index(fields=["user", "status"], name="budget_mc_user_status_idx"),
        ]

    def __str__(self) -> str:
        return (
            f"MonthlyClose(user={self.user_id}, "
            f"{self.fiscal_year}-{self.month:02d}, status={self.status})"
        )
