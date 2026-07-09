from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class FinancialPlan(models.Model):
    class HouseholdType(models.TextChoices):
        SINGLE = "single", "Individual"
        FAMILY = "family", "Familiar"

    class Profile(models.TextChoices):
        SECURITY = "security", "Seguridad"
        BALANCED = "balanced", "Equilibrado"
        GROWTH = "growth", "Crecimiento"

    class Status(models.TextChoices):
        ACTIVE = "active", "Activo"
        ARCHIVED = "archived", "Archivado"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="financial_plan",
    )
    household_type = models.CharField(
        max_length=16,
        choices=HouseholdType.choices,
        default=HouseholdType.SINGLE,
    )
    target_date = models.DateField()
    target_monthly_income_today_eur = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    projection_end_date = models.DateField()
    preservation_target_eur = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    preserved_asset_ids = models.JSONField(null=True, blank=True)
    profile = models.CharField(
        max_length=16,
        choices=Profile.choices,
        default=Profile.BALANCED,
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    members = models.ManyToManyField(
        "memberships.FamilyMember",
        blank=True,
        related_name="financial_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
        ]
        ordering = ["-updated_at"]

    def clean(self) -> None:
        if self.projection_end_date and self.target_date:
            if self.projection_end_date < self.target_date:
                raise ValidationError("projection_end_date must be >= target_date.")

    def __str__(self) -> str:
        return f"{self.user_id} - financial plan"


class PlanAssetFunction(models.Model):
    class Function(models.TextChoices):
        PRODUCTIVE = "productive", "Productivo"
        SECURITY = "security", "Seguridad"
        SHORT_TERM_GOAL = "short_term_goal", "Objetivo corto plazo"
        FAMILY_USE = "family_use", "Uso familiar"
        UNKNOWN = "unknown", "Desconocido"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="plan_asset_functions",
    )
    asset = models.ForeignKey(
        "net_worth.Asset",
        on_delete=models.CASCADE,
        related_name="plan_function_overrides",
    )
    function = models.CharField(max_length=32, choices=Function.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "asset"], name="uniq_plan_asset_function_user")
        ]
        indexes = [models.Index(fields=["user", "function"])]

    def clean(self) -> None:
        if self.asset_id and self.user_id and self.asset.user_id != self.user_id:
            raise ValidationError("Asset does not belong to this user.")

    def __str__(self) -> str:
        return f"{self.user_id} - asset:{self.asset_id} -> {self.function}"


class AssumptionSet(models.Model):
    name = models.CharField(max_length=32, unique=True)
    inflation_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    productive_return_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
    )
    non_productive_appreciation_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
    )
    income_growth_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
    )
    contribution_growth_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
    )
    withdrawal_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    default_liability_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["is_default"])]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProjectionSnapshot(models.Model):
    plan = models.ForeignKey(
        FinancialPlan,
        on_delete=models.CASCADE,
        related_name="projection_snapshots",
    )
    scenario = models.IntegerField(null=True, blank=True)
    assumption_set = models.ForeignKey(
        AssumptionSet,
        on_delete=models.PROTECT,
        related_name="projection_snapshots",
    )
    assumption_values = models.JSONField()
    calculated_at = models.DateTimeField(auto_now_add=True)
    input_hash = models.CharField(max_length=64)
    result_json = models.JSONField()
    quality_level = models.CharField(max_length=32)
    is_official = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["plan", "-calculated_at"]),
            models.Index(fields=["plan", "is_official"]),
            models.Index(fields=["input_hash"]),
        ]
        ordering = ["-calculated_at", "-id"]

    def __str__(self) -> str:
        return f"{self.plan_id} - {self.assumption_set.name} - {self.calculated_at}"
