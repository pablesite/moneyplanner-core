from django.conf import settings
from django.core.validators import MinValueValidator,  MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone



class Asset(models.Model):
    class Category(models.TextChoices):
        CASH = "cash", "Liquidez"
        INVESTMENTS = "investments", "Inversiones"
        REAL_ESTATE = "real_estate", "Inmuebles"
        VEHICLE = "vehicle", "Vehículo"
        OTHER = "other", "Otros"

    class TrackingMode(models.TextChoices):
        MANUAL = "manual", "Manual"
        ACCOUNTING = "accounting", "Desde contabilidad"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assets")

    ownership = models.ForeignKey(
        "Ownership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assets",
        help_text="Titularidad (individual o compartido)",
    )

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.CASH)

    tracking_mode = models.CharField(max_length=16, choices=TrackingMode.choices, default=TrackingMode.MANUAL)
    # placeholder para enlazar con el módulo contabilidad (cuando exista)
    accounting_account_id = models.IntegerField(null=True, blank=True)

    currency = models.CharField(max_length=3, default="EUR")
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Valor actual (positivo). Si tracking_mode=accounting, este campo puede ignorarse en summary.",
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "category"]),
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["user", "tracking_mode"]),
        ]
        ordering = ["category", "name"]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.name} ({self.amount} {self.currency})"


class Liability(models.Model):
    class Category(models.TextChoices):
        MORTGAGE = "mortgage", "Hipoteca"
        PERSONAL_LOAN = "personal_loan", "Préstamo personal"
        CREDIT_CARD = "credit_card", "Tarjeta"
        OTHER = "other", "Otros"

    class TrackingMode(models.TextChoices):
        MANUAL = "manual", "Manual"
        ACCOUNTING = "accounting", "Desde contabilidad"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="liabilities")

    ownership = models.ForeignKey(
        "Ownership",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="liabilities",
        help_text="Titularidad (individual o compartido)",
    )

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.OTHER)

    tracking_mode = models.CharField(max_length=16, choices=TrackingMode.choices, default=TrackingMode.MANUAL)
    accounting_account_id = models.IntegerField(null=True, blank=True)

    currency = models.CharField(max_length=3, default="EUR")
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Deuda pendiente (positiva). Si tracking_mode=accounting, este campo puede ignorarse en summary.",
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "category"]),
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["user", "tracking_mode"]),
        ]
        ordering = ["category", "name"]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.name} ({self.amount} {self.currency})"


class NetWorthSnapshot(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="net_worth_snapshots")
    snapshot_date = models.DateField(default=timezone.now)

    base_currency = models.CharField(max_length=3, default="EUR")

    total_assets = models.DecimalField(max_digits=14, decimal_places=2)
    total_liabilities = models.DecimalField(max_digits=14, decimal_places=2)
    net_worth = models.DecimalField(max_digits=14, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "snapshot_date"])]
        ordering = ["-snapshot_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "snapshot_date"], name="unique_snapshot_per_user_and_date")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.snapshot_date} - {self.net_worth}"



class FamilyMember(models.Model):
    class Role(models.TextChoices):
        ADULT = "adult", "Adulto"
        CHILD = "child", "Niño"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="family_members")

    name = models.CharField(max_length=80)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.ADULT)

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["user", "role"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="uniq_member_name_per_user"),
        ]
        ordering = ["role", "name"]

    def __str__(self):
        return f"{self.user_id} - {self.name} ({self.role})"


class Ownership(models.Model):
    class Kind(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        SHARED = "shared", "Compartido"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ownerships")

    kind = models.CharField(max_length=16, choices=Kind.choices)

    member = models.ForeignKey(
        "FamilyMember",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="individual_ownerships",
    )

    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "kind"])]
        constraints = [
            models.CheckConstraint(
                name="ownership_individual_requires_member",
                condition=(
                    Q(kind="individual", member__isnull=False)
                    | Q(kind="shared", member__isnull=True)
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.kind}"


class OwnershipSplit(models.Model):
    ownership = models.ForeignKey("Ownership", on_delete=models.CASCADE, related_name="splits")
    member = models.ForeignKey("FamilyMember", on_delete=models.PROTECT, related_name="ownership_splits")

    percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["ownership", "member"], name="uniq_split_member_per_ownership"),
        ]

    def __str__(self) -> str:
        return f"{self.ownership_id} - {self.member_id} - {self.percent}%"