from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class LedgerAccount(models.Model):
    class AccountType(models.TextChoices):
        ASSET = "asset", "Activo"
        LIABILITY = "liability", "Pasivo"
        EQUITY = "equity", "Patrimonio neto"
        INCOME = "income", "Ingreso"
        EXPENSE = "expense", "Gasto"

    class Origin(models.TextChoices):
        USER = "user", "Usuario"
        SYSTEM = "system", "Sistema"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ledger_accounts"
    )
    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=16, choices=AccountType.choices)
    currency = models.CharField(max_length=3, default="EUR")
    origin = models.CharField(max_length=16, choices=Origin.choices, default=Origin.USER)
    asset = models.ForeignKey(
        "net_worth.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_accounts",
    )
    liability = models.ForeignKey(
        "net_worth.Liability",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_accounts",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["account_type", "name", "id"]
        indexes = [
            models.Index(fields=["user", "account_type"], name="acct_acc_user_type_idx"),
            models.Index(fields=["user", "is_active"], name="acct_acc_user_active_idx"),
        ]

    def __str__(self) -> str:
        return f"LedgerAccount(user={self.user_id}, name={self.name}, type={self.account_type})"


class LedgerTransaction(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        POSTED = "posted", "Contabilizada"

    class Origin(models.TextChoices):
        MANUAL = "manual", "Manual"
        IMPORT = "import", "Importacion"
        SYSTEM = "system", "Sistema"

    class QuickEntryKind(models.TextChoices):
        INCOME = "income", "Ingreso"
        EXPENSE = "expense", "Gasto"
        TRANSFER = "transfer", "Transferencia"
        INVESTMENT = "investment", "Inversion"
        DEBT_PAYMENT = "debt_payment", "Pago deuda"
        REVALUATION = "revaluation", "Revalorizacion"

    class InvestmentDirection(models.TextChoices):
        INFLOW = "inflow", "Aporte"
        OUTFLOW = "outflow", "Desinversion"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ledger_transactions"
    )
    booking_date = models.DateField(default=timezone.localdate)
    value_date = models.DateField(default=timezone.localdate)
    description = models.CharField(max_length=240)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.POSTED)
    origin = models.CharField(max_length=16, choices=Origin.choices, default=Origin.MANUAL)
    notes = models.TextField(blank=True, default="")
    import_source = models.CharField(max_length=32, blank=True, default="")
    import_fingerprint = models.CharField(max_length=64, blank=True, default="")
    member_tag = models.CharField(max_length=32, blank=True, default="")
    quick_entry_kind = models.CharField(max_length=24, blank=True, default="")
    investment_direction = models.CharField(max_length=16, blank=True, default="")
    realized_cost_basis = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
    )
    realized_gain_loss = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-booking_date", "-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "import_source", "import_fingerprint"],
                condition=~Q(import_fingerprint=""),
                name="acct_tx_user_import_fp_unique",
            )
        ]
        indexes = [
            models.Index(fields=["user", "booking_date"], name="acct_tx_user_book_idx"),
            models.Index(
                fields=["user", "-booking_date", "-id"],
                name="acct_tx_user_book_id_desc",
            ),
            models.Index(fields=["user", "value_date"], name="acct_tx_user_value_idx"),
            models.Index(fields=["user", "status"], name="acct_tx_user_status_idx"),
            models.Index(
                fields=["user", "import_source", "import_fingerprint"],
                name="acct_tx_user_import_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"LedgerTransaction(user={self.user_id}, date={self.booking_date}, desc={self.description})"


class LedgerEntry(models.Model):
    class Side(models.TextChoices):
        DEBIT = "debit", "Debe"
        CREDIT = "credit", "Haber"

    class FlowFamily(models.TextChoices):
        INCOME = "income", "Ingreso"
        EXPENSE = "expense", "Gasto"

    transaction = models.ForeignKey(
        LedgerTransaction,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    account = models.ForeignKey(
        LedgerAccount,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    side = models.CharField(max_length=8, choices=Side.choices)
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=3, default="EUR")
    flow_family = models.CharField(
        max_length=16,
        choices=FlowFamily.choices,
        blank=True,
        default="",
    )
    category_key = models.CharField(max_length=64, blank=True, default="")
    subcategory_key = models.CharField(max_length=64, blank=True, default="")
    annual_income_entry = models.ForeignKey(
        "budget.AnnualIncomeEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    annual_expense_entry = models.ForeignKey(
        "budget.AnnualExpenseEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    asset = models.ForeignKey(
        "net_worth.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    liability = models.ForeignKey(
        "net_worth.Liability",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    notes = models.CharField(max_length=240, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["transaction"], name="acct_entry_tx_idx"),
            models.Index(fields=["account"], name="acct_entry_acc_idx"),
            models.Index(fields=["currency"], name="acct_entry_currency_idx"),
            models.Index(fields=["flow_family"], name="acct_entry_flow_idx"),
            models.Index(
                fields=["flow_family", "category_key", "subcategory_key"],
                name="acct_entry_class_idx",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"LedgerEntry(tx={self.transaction_id}, account={self.account_id}, side={self.side}, "
            f"amount={self.amount} {self.currency})"
        )
