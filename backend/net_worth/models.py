from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Asset(models.Model):
    class Category(models.TextChoices):
        CASH = "cash", "Liquidez"
        INVESTMENTS = "investments", "Inversiones"
        REAL_ESTATE = "real_estate", "Inmuebles"
        VEHICLE = "vehicle", "Vehiculo"
        FURNISHINGS = "furnishings", "Mobiliario"
        OTHER = "other", "Otros"

    class Subcategory(models.TextChoices):
        BANK_ACCOUNT = "bank_account", "Cuenta bancaria"
        WALLET = "wallet", "Monedero"
        CRYPTO_SPOT_EARN = "crypto_spot_earn", "Spot/Earn Cripto"

        DEPOSITS = "deposits", "Depositos"
        FUNDS = "funds", "Fondos"
        ETFS = "etfs", "ETFs"
        ROBOADVISOR = "roboadvisor", "Roboadvisor"
        STOCKS = "stocks", "Stocks"
        PENSION_PLANS = "pension_plans", "Planes de pensiones"
        CRYPTOCURRENCIES = "cryptocurrencies", "Criptomonedas"
        REAL_ESTATE_CROWD = "real_estate_crowd", "Crowdfunding Inmobiliario"
        CROWDLENDING = "crowdlending", "Crowdlending"

        PRIMARY_HOME = "primary_home", "Vivienda habitual"
        SECOND_HOME = "second_home", "Segunda vivienda"
        RENTAL = "rental", "Rentas"

        VEHICLES = "vehicles", "Vehiculos"
        TECHNOLOGY = "technology", "Tecnologia"
        HOME_FURNISHINGS = "home_furnishings", "Muebles vivienda"
        SPORTS_EQUIPMENT = "sports_equipment", "Equipamiento deportivo"
        JEWELRY = "jewelry", "Joyeria"

        OTHER = "other", "Otros"

    class TrackingMode(models.TextChoices):
        MANUAL = "manual", "Manual"
        ACCOUNTING = "accounting", "Desde contabilidad"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assets"
    )

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.CASH)
    subcategory = models.CharField(
        max_length=48, choices=Subcategory.choices, default=Subcategory.OTHER
    )

    tracking_mode = models.CharField(
        max_length=16, choices=TrackingMode.choices, default=TrackingMode.MANUAL
    )
    accounting_account_id = models.IntegerField(null=True, blank=True)

    currency = models.CharField(max_length=3, default="EUR")
    start_date = models.DateField(
        default=timezone.localdate,
        help_text="Fecha de inicio o adquisicion del activo.",
    )
    annual_interest_tae = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "TAE anual en porcentaje. Se usa para liquidez remunerada "
            "(cuentas bancarias y spot/earn cripto)."
        ),
    )
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[],
        help_text="Valor actual (puede ser negativo). Si tracking_mode=accounting, este campo puede ignorarse en summary.",
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


ASSET_SUBCATEGORY_MAP = {
    Asset.Category.CASH: {
        Asset.Subcategory.BANK_ACCOUNT,
        Asset.Subcategory.WALLET,
        Asset.Subcategory.CRYPTO_SPOT_EARN,
        Asset.Subcategory.OTHER,
    },
    Asset.Category.INVESTMENTS: {
        Asset.Subcategory.DEPOSITS,
        Asset.Subcategory.FUNDS,
        Asset.Subcategory.ETFS,
        Asset.Subcategory.ROBOADVISOR,
        Asset.Subcategory.STOCKS,
        Asset.Subcategory.PENSION_PLANS,
        Asset.Subcategory.CRYPTOCURRENCIES,
        Asset.Subcategory.REAL_ESTATE_CROWD,
        Asset.Subcategory.CROWDLENDING,
        Asset.Subcategory.OTHER,
    },
    Asset.Category.REAL_ESTATE: {
        Asset.Subcategory.PRIMARY_HOME,
        Asset.Subcategory.SECOND_HOME,
        Asset.Subcategory.RENTAL,
        Asset.Subcategory.OTHER,
    },
    Asset.Category.FURNISHINGS: {
        Asset.Subcategory.VEHICLES,
        Asset.Subcategory.TECHNOLOGY,
        Asset.Subcategory.HOME_FURNISHINGS,
        Asset.Subcategory.SPORTS_EQUIPMENT,
        Asset.Subcategory.JEWELRY,
        Asset.Subcategory.OTHER,
    },
    Asset.Category.VEHICLE: {
        Asset.Subcategory.VEHICLES,
        Asset.Subcategory.OTHER,
    },
    Asset.Category.OTHER: {
        Asset.Subcategory.OTHER,
    },
}


class Liability(models.Model):
    class Category(models.TextChoices):
        MORTGAGE = "mortgage", "Hipoteca"
        PERSONAL_LOAN = "personal_loan", "Prestamo personal"
        CREDIT_CARD = "credit_card", "Tarjeta"
        OTHER = "other", "Otros"

    class TrackingMode(models.TextChoices):
        MANUAL = "manual", "Manual"
        ACCOUNTING = "accounting", "Desde contabilidad"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="liabilities"
    )

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=32, choices=Category.choices, default=Category.OTHER)

    tracking_mode = models.CharField(
        max_length=16, choices=TrackingMode.choices, default=TrackingMode.MANUAL
    )
    accounting_account_id = models.IntegerField(null=True, blank=True)

    currency = models.CharField(max_length=3, default="EUR")
    start_date = models.DateField(
        default=timezone.localdate,
        help_text="Fecha de inicio o adquisicion del pasivo.",
    )
    annual_interest_tae = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "TAE anual en porcentaje. En esta iteracion se modela como tipo fijo "
            "para hipoteca, prestamo personal y tarjeta."
        ),
    )
    monthly_payment_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "Cuota mensual manual en la moneda del pasivo. "
            "Temporal hasta modelar amortizacion y calendario."
        ),
    )
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text="Deuda pendiente (positiva). Si tracking_mode=accounting, este campo puede ignorarse en summary.",
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    is_asset_backed = models.BooleanField(
        default=False,
        help_text=(
            "True si esta deuda esta asociada a un activo (hipoteca, prestamo coche, etc.). "
            "False si es deuda de gasto/consumo (clinica, tarjeta, etc.)."
        ),
    )

    financed_asset = models.ForeignKey(
        "Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financing_liabilities",
        help_text="Activo que financia esta deuda (si aplica). Si es null, es deuda sin activo asociado.",
    )

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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="net_worth_snapshots"
    )
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
            models.UniqueConstraint(
                fields=["user", "snapshot_date"], name="unique_snapshot_per_user_and_date"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} - {self.snapshot_date} - {self.net_worth}"
