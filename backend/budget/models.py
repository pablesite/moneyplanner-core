from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
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
    ownership = models.ForeignKey(
        "memberships.Ownership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="annual_income_entries",
    )
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
    term_start_month = models.PositiveSmallIntegerField(null=True, blank=True)
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
    ownership = models.ForeignKey(
        "memberships.Ownership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="annual_expense_entries",
    )
    settlement_account = models.ForeignKey(
        "SettlementAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="annual_expense_entries",
    )
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
    term_start_month = models.PositiveSmallIntegerField(null=True, blank=True)
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
    opening_liquidity_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    expected_liquidity_total_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    residual_snapshot = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
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


class SettlementProfile(models.Model):
    class ReadinessStatus(models.TextChoices):
        NOT_CHECKED = "not_checked", "No comprobado"
        READY = "ready", "Listo"
        BLOCKED = "blocked", "Bloqueado"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="settlement_profile",
    )
    is_enabled = models.BooleanField(default=False)
    activation_date = models.DateField(null=True, blank=True)
    base_currency = models.CharField(max_length=3, default="EUR")
    operating_reserve_adjustment = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Ajuste manual, positivo o negativo, sobre la reserva operativa calculada.",
    )
    readiness_status = models.CharField(
        max_length=16,
        choices=ReadinessStatus.choices,
        default=ReadinessStatus.NOT_CHECKED,
    )
    readiness_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "budget_settlement_profile"


class SettlementAccount(models.Model):
    class Role(models.TextChoices):
        OPERATING = "operating", "Operativa"
        PERSONAL_DESTINATION = "personal_destination", "Destino personal"
        ALLOCATION_DESTINATION = "allocation_destination", "Destino de asignacion"
        PHYSICAL_CASH = "physical_cash", "Efectivo fisico"

    profile = models.ForeignKey(
        SettlementProfile,
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    asset = models.ForeignKey(
        "net_worth.Asset",
        on_delete=models.PROTECT,
        related_name="settlement_accounts",
    )
    role = models.CharField(max_length=32, choices=Role.choices)
    member = models.ForeignKey(
        "memberships.FamilyMember",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="settlement_accounts",
    )
    currency = models.CharField(max_length=3)
    is_primary = models.BooleanField(default=False)
    accepted_physical_balance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    modeled_balance_at_activation = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "budget_settlement_account"
        ordering = ["role", "asset_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "asset"],
                name="budget_settle_account_asset_unique",
            ),
            models.UniqueConstraint(
                fields=["profile", "member", "currency"],
                condition=models.Q(role="personal_destination", is_primary=True),
                name="budget_settle_primary_member_currency_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(role="personal_destination", member__isnull=False)
                    | ~models.Q(role="personal_destination") & models.Q(member__isnull=True)
                ),
                name="budget_settle_personal_requires_member",
            ),
        ]


class SettlementOpeningBalance(models.Model):
    profile = models.ForeignKey(
        SettlementProfile,
        on_delete=models.CASCADE,
        related_name="opening_balances",
    )
    account = models.ForeignKey(
        SettlementAccount,
        on_delete=models.CASCADE,
        related_name="opening_balances",
    )
    member = models.ForeignKey(
        "memberships.FamilyMember",
        on_delete=models.PROTECT,
        related_name="settlement_opening_balances",
    )
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "budget_settlement_opening_balance"
        ordering = ["account_id", "member_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "account", "member"],
                name="budget_settle_opening_account_member_unique",
            ),
        ]


class SettlementOpeningAdjustment(models.Model):
    class Kind(models.TextChoices):
        MANUAL = "manual", "Manual"
        WALLET_NORMALIZATION = "wallet_normalization", "Normalizacion de monedero"

    profile = models.ForeignKey(
        SettlementProfile,
        on_delete=models.CASCADE,
        related_name="opening_adjustments",
    )
    account = models.ForeignKey(
        SettlementAccount,
        on_delete=models.CASCADE,
        related_name="opening_adjustments",
    )
    member = models.ForeignKey(
        "memberships.FamilyMember",
        on_delete=models.PROTECT,
        related_name="settlement_opening_adjustments",
    )
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.MANUAL)
    note = models.CharField(max_length=240, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "budget_settlement_opening_adjustment"
        ordering = ["account_id", "member_id", "id"]


class SettlementWalletNormalization(models.Model):
    profile = models.ForeignKey(
        SettlementProfile,
        on_delete=models.CASCADE,
        related_name="wallet_normalizations",
    )
    transaction = models.OneToOneField(
        "accounting.LedgerTransaction",
        on_delete=models.PROTECT,
        related_name="settlement_wallet_normalization",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "budget_settlement_wallet_normalization"
        ordering = ["transaction__booking_date", "transaction_id"]


class SettlementSnapshot(models.Model):
    class Status(models.TextChoices):
        READY = "ready", "Listo"
        NOT_READY = "not_ready", "No listo"

    monthly_close = models.OneToOneField(
        MonthlyClose,
        on_delete=models.CASCADE,
        related_name="settlement_snapshot",
    )
    profile = models.ForeignKey(
        SettlementProfile,
        on_delete=models.PROTECT,
        related_name="snapshots",
    )
    allocation_snapshots = models.ManyToManyField(
        "memberships.OwnershipAllocationSnapshot",
        blank=True,
        related_name="settlement_snapshots",
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    base_currency = models.CharField(max_length=3)
    period_start = models.DateField()
    period_end = models.DateField()
    target_year = models.PositiveSmallIntegerField()
    target_month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    opening_source = models.CharField(max_length=24)
    source_hash = models.CharField(max_length=64)
    allocations = models.JSONField(default=list)
    economic_balances = models.JSONField(default=list)
    account_balances = models.JSONField(default=list)
    reserves = models.JSONField(default=list)
    compensations = models.JSONField(default=list)
    blockers = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    reconciliation = models.JSONField(default=dict)
    is_frozen = models.BooleanField(default=True)
    computed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "budget_settlement_snapshot"
        ordering = ["-monthly_close__fiscal_year", "-monthly_close__month"]


class SettlementTransferRecommendation(models.Model):
    class Status(models.TextChoices):
        RECOMMENDED = "recommended", "Recomendada"
        ACCEPTED = "accepted", "Aceptada"
        APPLIED = "applied", "Aplicada"
        PARTIALLY_APPLIED = "partially_applied", "Aplicada parcialmente"
        CANCELLED = "cancelled", "Cancelada"

    snapshot = models.ForeignKey(
        SettlementSnapshot,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    from_account = models.ForeignKey(
        SettlementAccount,
        on_delete=models.PROTECT,
        related_name="outgoing_recommendations",
    )
    to_account = models.ForeignKey(
        SettlementAccount,
        on_delete=models.PROTECT,
        related_name="incoming_recommendations",
    )
    member = models.ForeignKey(
        "memberships.FamilyMember",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="settlement_recommendations",
    )
    ownership = models.ForeignKey(
        "memberships.Ownership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="settlement_recommendations",
    )
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    currency = models.CharField(max_length=3)
    reason = models.CharField(max_length=32, default="settlement")
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.RECOMMENDED,
    )
    applied_amount = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    accepted_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "budget_settlement_transfer_recommendation"
        ordering = ["sort_order", "id"]
