from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class FamilyMember(models.Model):
    class Role(models.TextChoices):
        ADULT = "adult", "Adulto"
        CHILD = "child", "Nino"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="family_members"
    )

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

    def __str__(self) -> str:
        return f"{self.user_id} - {self.name} ({self.role})"


class Ownership(models.Model):
    class Kind(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        SHARED = "shared", "Compartido"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ownerships"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)

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
                fields=["ownership", "member"], name="uniq_split_member_per_ownership"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ownership_id} - {self.member_id} - {self.percent}%"


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
