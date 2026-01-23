# Create your models here.
from django.conf import settings
from django.db import models
from django.utils import timezone


class Asset(models.Model):
    class Category(models.TextChoices):
        CASH = "cash", "Liquidez"
        INVESTMENTS = "investments", "Inversiones"
        REAL_ESTATE = "real_estate", "Inmuebles"
        VEHICLE = "vehicle", "Vehículo"
        OTHER = "other", "Otros"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assets")
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.CASH)
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # euros
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "category"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.name} ({self.amount})"


class Liability(models.Model):
    class Category(models.TextChoices):
        MORTGAGE = "mortgage", "Hipoteca"
        PERSONAL_LOAN = "personal_loan", "Préstamo personal"
        CREDIT_CARD = "credit_card", "Tarjeta"
        OTHER = "other", "Otros"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="liabilities")
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.OTHER)
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # deuda pendiente (positivo)
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "category"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.name} ({self.amount})"


class NetWorthSnapshot(models.Model):
    """
    Foto mensual (o puntual) del patrimonio neto. Guardamos:
    - total_assets
    - total_liabilities
    - net_worth
    - snapshot_date (por defecto hoy)
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="net_worth_snapshots")
    snapshot_date = models.DateField(default=timezone.now)

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
