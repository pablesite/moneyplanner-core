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
        VEHICLE = "vehicle", "Veh�culo"
        FURNISHINGS = "furnishings", "Mobiliario"
        OTHER = "other", "Otros"

    
    class Subcategory(models.TextChoices):
        BANK_ACCOUNT = "bank_account", "Cuenta bancaria"
        WALLET = "wallet", "Monedero"
        CRYPTO_SPOT_EARN = "crypto_spot_earn", "Spot/Earn Cripto"

        DEPOSITS = "deposits", "Depósitos"
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

        VEHICLES = "vehicles", "Vehículos"
        TECHNOLOGY = "technology", "Tecnología"
        HOME_FURNISHINGS = "home_furnishings", "Muebles vivienda"
        SPORTS_EQUIPMENT = "sports_equipment", "Equipamiento deportivo"
        JEWELRY = "jewelry", "Joyería"

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
    subcategory = models.CharField(max_length=48, choices=Subcategory.choices, default=Subcategory.OTHER)

    tracking_mode = models.CharField(max_length=16, choices=TrackingMode.choices, default=TrackingMode.MANUAL)
    # placeholder para enlazar con el módulo contabilidad (cuando exista)
    accounting_account_id = models.IntegerField(null=True, blank=True)

    currency = models.CharField(max_length=3, default="EUR")
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
        PERSONAL_LOAN = "personal_loan", "Préstamo personal"
        CREDIT_CARD = "credit_card", "Tarjeta"
        OTHER = "other", "Otros"

    
    class Subcategory(models.TextChoices):
        BANK_ACCOUNT = "bank_account", "Cuenta bancaria"
        WALLET = "wallet", "Monedero"
        CRYPTO_SPOT_EARN = "crypto_spot_earn", "Spot/Earn Cripto"

        DEPOSITS = "deposits", "Dep�sitos"
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

        VEHICLES = "vehicles", "Veh�culos"
        TECHNOLOGY = "technology", "Tecnolog�a"
        HOME_FURNISHINGS = "home_furnishings", "Muebles vivienda"
        SPORTS_EQUIPMENT = "sports_equipment", "Equipamiento deportivo"
        JEWELRY = "jewelry", "Joyer�a"

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
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text="Deuda pendiente (positiva). Si tracking_mode=accounting, este campo puede ignorarse en summary.",
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")

    is_asset_backed = models.BooleanField(
        default=False,
        help_text="True si esta deuda está asociada a un activo (hipoteca, préstamo coche, etc.). False si es deuda de gasto/consumo (clínica, tarjeta, etc.).",
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
    




