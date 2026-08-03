from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class FamilyMember(models.Model):
    class Role(models.TextChoices):
        ADULT = "adult", "Adulto"
        CHILD = "child", "Nino"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="family_members"
    )

    name = models.CharField(max_length=80)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.ADULT)
    birth_date = models.DateField(null=True, blank=True)
    employment_income_end_date = models.DateField(null=True, blank=True)
    pension_start_date = models.DateField(null=True, blank=True)
    estimated_monthly_pension_today_eur = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    other_future_income_today_eur = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["user", "role"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="uniq_member_name_per_user_memberships",
            ),
        ]
        ordering = ["role", "name"]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.name} ({self.role})"


class Ownership(models.Model):
    class Kind(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        SHARED = "shared", "Compartido"

    class AllocationBasis(models.TextChoices):
        EXPLICIT_SPLIT = "explicit_split", "Reparto explicito"
        RECURRING_INCOME_12M = "recurring_income_12m", "Ingresos recurrentes (12 meses)"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ownerships"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    allocation_basis = models.CharField(
        max_length=32,
        choices=AllocationBasis.choices,
        default=AllocationBasis.EXPLICIT_SPLIT,
    )

    member = models.ForeignKey(
        FamilyMember,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="individual_ownerships",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "kind"])]
        constraints = [
            models.CheckConstraint(
                name="ownership_individual_requires_member_memberships",
                condition=(
                    Q(kind="individual", member__isnull=False)
                    | Q(kind="shared", member__isnull=True)
                ),
            ),
            models.CheckConstraint(
                name="ownership_dynamic_requires_shared_memberships",
                condition=(
                    Q(kind="shared") | Q(kind="individual", allocation_basis="explicit_split")
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.kind}"


class OwnershipSplit(models.Model):
    ownership = models.ForeignKey(Ownership, on_delete=models.CASCADE, related_name="splits")
    member = models.ForeignKey(
        FamilyMember, on_delete=models.PROTECT, related_name="ownership_splits"
    )

    percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["ownership", "member"],
                name="uniq_split_member_per_ownership_memberships",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ownership_id} - {self.member_id} - {self.percent}%"


class OwnershipIncomeRule(models.Model):
    ownership = models.ForeignKey(
        Ownership,
        on_delete=models.CASCADE,
        related_name="income_rules",
    )
    category_key = models.CharField(max_length=64)
    subcategory_key = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["category_key", "subcategory_key", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["ownership", "category_key", "subcategory_key"],
                name="uniq_income_rule_per_ownership_memberships",
            ),
        ]

    def __str__(self) -> str:
        taxonomy = self.category_key
        if self.subcategory_key:
            taxonomy = f"{taxonomy}/{self.subcategory_key}"
        return f"{self.ownership_id} - {taxonomy}"


class OwnershipAllocationSnapshot(models.Model):
    class Status(models.TextChoices):
        READY = "ready", "Listo"
        PROVISIONAL = "provisional", "Provisional"
        BLOCKED = "blocked", "Bloqueado"

    ownership = models.ForeignKey(
        Ownership,
        on_delete=models.CASCADE,
        related_name="allocation_snapshots",
    )
    fiscal_year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    window_start = models.DateField()
    window_end = models.DateField()
    base_currency = models.CharField(max_length=3)
    source_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices)
    quality_reasons = models.JSONField(default=list, blank=True)
    observed_months = models.PositiveSmallIntegerField(default=0)
    eligible_transaction_count = models.PositiveIntegerField(default=0)
    excluded_transaction_count = models.PositiveIntegerField(default=0)
    total_qualifying_income = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    is_frozen = models.BooleanField(default=False)
    frozen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fiscal_year", "-month", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["ownership", "fiscal_year", "month"],
                name="uniq_allocation_snapshot_month_memberships",
            ),
        ]
        indexes = [
            models.Index(
                fields=["ownership", "fiscal_year", "month"],
                name="member_alloc_period_idx",
            ),
        ]

    def freeze(self) -> None:
        if not self.is_frozen:
            self.is_frozen = True
            self.frozen_at = timezone.now()
            self.save(update_fields=["is_frozen", "frozen_at", "updated_at"])


class OwnershipAllocationSnapshotShare(models.Model):
    snapshot = models.ForeignKey(
        OwnershipAllocationSnapshot,
        on_delete=models.CASCADE,
        related_name="shares",
    )
    member = models.ForeignKey(
        FamilyMember,
        on_delete=models.PROTECT,
        related_name="allocation_snapshot_shares",
    )
    qualifying_income = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        ordering = ["member_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "member"],
                name="uniq_allocation_share_member_memberships",
            ),
        ]


class OwnershipLink(models.Model):
    class TargetType(models.TextChoices):
        ASSET = "asset", "Activo"
        LIABILITY = "liability", "Pasivo"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ownership_links"
    )
    ownership = models.ForeignKey(Ownership, on_delete=models.CASCADE, related_name="links")
    target_type = models.CharField(max_length=16, choices=TargetType.choices)
    target_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "target_type", "target_id"]),
            models.Index(fields=["ownership"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "target_type", "target_id"],
                name="uniq_target_per_user",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.user_id} - {self.target_type}:{self.target_id} -> ownership:{self.ownership_id}"
        )
