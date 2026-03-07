from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.validators import MaxValueValidator
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
        SHORT_TERM_DEPOSIT = "short_term_deposit", "Deposito a corto plazo"
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

    class AmortizationMethod(models.TextChoices):
        NONE = "none", "Sin amortizacion"
        STRAIGHT_LINE = "straight_line", "Lineal"
        MANUAL = "manual", "Manual"

    class ValuationModel(models.TextChoices):
        MANUAL = "manual", "Manual"
        REAL_ESTATE_AUTO = "real_estate_auto", "Vivienda automatica"

    class InvestmentContributionMode(models.TextChoices):
        ONE_TIME = "one_time", "Aportacion unica"
        PERIODIC_CONTRIBUTION = "periodic_contribution", "Aportacion periodica"

    class InvestmentContributionFrequency(models.TextChoices):
        MONTHLY = "monthly", "Mensual"
        WEEKLY = "weekly", "Semanal"

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
    expected_end_date = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Fecha fin prevista para aportaciones periodicas en inversiones. "
            "Solo aplica cuando investment_contribution_mode=periodic_contribution."
        ),
    )
    initial_purchase_value = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "Valor de compra inicial del activo en la moneda del activo. "
            "Opcional si no se desea modelar amortizacion."
        ),
    )
    amortization_method = models.CharField(
        max_length=24,
        choices=AmortizationMethod.choices,
        default=AmortizationMethod.NONE,
        help_text="Modelo de amortizacion/depreciacion del activo (si aplica).",
    )
    amortization_term_years = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Vida util/plazo de amortizacion estimado en anos (si aplica).",
    )
    investment_contribution_mode = models.CharField(
        max_length=32,
        choices=InvestmentContributionMode.choices,
        default=InvestmentContributionMode.ONE_TIME,
        help_text=(
            "Modo de aportacion para inversiones: unica o periodica. "
            "Solo aplica a category=investments."
        ),
    )
    investment_contribution_frequency = models.CharField(
        max_length=16,
        choices=InvestmentContributionFrequency.choices,
        default=InvestmentContributionFrequency.MONTHLY,
        help_text=(
            "Frecuencia de la aportacion periodica en inversiones: mensual o semanal. "
            "Solo aplica a investment_contribution_mode=periodic_contribution."
        ),
    )
    investment_contribution_currency = models.CharField(
        max_length=3,
        null=True,
        blank=True,
        help_text=(
            "Moneda de la cuota periodica en inversiones. "
            "Si no se indica, se asume la moneda del activo."
        ),
    )
    monthly_contribution_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "Cuota mensual prevista para inversiones periodicas. "
            "Solo aplica a investment_contribution_mode=periodic_contribution."
        ),
    )
    market_value_override = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "Valor de mercado manual del activo (marca a mercado). "
            "Si se informa en inversiones, prevalece sobre el valor calculado por aportaciones."
        ),
    )
    market_value_override_date = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha de la ultima valoracion manual del activo (as-of).",
    )
    valuation_model = models.CharField(
        max_length=24,
        choices=ValuationModel.choices,
        default=ValuationModel.MANUAL,
        help_text=(
            "Modelo de valoracion del activo. En inmuebles residenciales puede usarse "
            "valoracion automatica por suelo + construccion."
        ),
    )
    land_value_share_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=(
            "Porcentaje del valor inicial atribuible al suelo para valoracion automatica "
            "de vivienda."
        ),
    )
    land_annual_appreciation_percent = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(-100), MaxValueValidator(200)],
        help_text="Revalorizacion anual del suelo en porcentaje.",
    )
    building_annual_depreciation_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Depreciacion anual de la construccion en porcentaje.",
    )
    annual_interest_tae = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "TAE anual en porcentaje. Se usa para liquidez remunerada "
            "(cuentas bancarias, depositos a corto plazo y spot/earn cripto)."
        ),
    )
    estimated_average_balance_for_interest = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "Saldo/importe anual medio previsto para estimar intereses en activos "
            "de liquidez remunerados."
        ),
    )
    deposit_term_months = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text=(
            "Duracion del deposito a corto plazo en meses (1-12). "
            "Solo aplica a subcategoria short_term_deposit."
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


class AssetImprovement(models.Model):
    class AmortizationMethod(models.TextChoices):
        NONE = "none", "Sin amortizacion"
        STRAIGHT_LINE = "straight_line", "Lineal"
        MANUAL = "manual", "Manual"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="improvements",
    )
    name = models.CharField(max_length=120)
    reform_date = models.DateField(
        default=timezone.localdate,
        help_text="Fecha en la que la reforma/obra entra en servicio.",
    )
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text="Importe total de la reforma en la moneda del activo.",
    )
    amortization_method = models.CharField(
        max_length=24,
        choices=AmortizationMethod.choices,
        default=AmortizationMethod.NONE,
        help_text="Metodo de amortizacion de la reforma.",
    )
    amortization_term_years = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Plazo de amortizacion de la reforma en anos (si aplica).",
    )
    annual_interest_tae = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="TAE anual asociada a la financiacion de la reforma (opcional).",
    )
    capitalize_interest = models.BooleanField(
        default=False,
        help_text=(
            "Si true, la TAE se capitaliza sobre el valor de la reforma para calculo "
            "de valor efectivo."
        ),
    )
    manual_current_value = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "Valor actual manual de la reforma. Requerido cuando "
            "amortization_method=manual."
        ),
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["asset", "reform_date"]),
        ]
        ordering = ["-reform_date", "-id"]

    def __str__(self) -> str:
        return f"{self.asset_id} - {self.name} ({self.amount})"


ASSET_SUBCATEGORY_MAP = {
    Asset.Category.CASH: {
        Asset.Subcategory.BANK_ACCOUNT,
        Asset.Subcategory.SHORT_TERM_DEPOSIT,
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

    class RateType(models.TextChoices):
        FIXED = "fixed", "Fijo"
        VARIABLE = "variable", "Variable"
        MIXED = "mixed", "Mixto"

    class PaymentFrequency(models.TextChoices):
        MONTHLY = "monthly", "Mensual"
        QUARTERLY = "quarterly", "Trimestral"
        YEARLY = "yearly", "Anual"

    class AmortizationSystem(models.TextChoices):
        FRENCH = "french", "Frances (cuota constante)"
        GERMAN = "german", "Aleman (amortizacion constante)"
        AMERICAN = "american", "Americano"
        MANUAL = "manual", "Manual"

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
    expected_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Fecha prevista de finalizacion del pasivo (si se conoce).",
    )
    term_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Plazo previsto en meses (alternativa/complemento a expected_end_date).",
    )
    rate_type = models.CharField(
        max_length=16,
        choices=RateType.choices,
        default=RateType.FIXED,
        help_text="Comportamiento del tipo de interes del pasivo.",
    )
    payment_frequency = models.CharField(
        max_length=16,
        choices=PaymentFrequency.choices,
        default=PaymentFrequency.MONTHLY,
        help_text="Frecuencia de pago prevista.",
    )
    amortization_system = models.CharField(
        max_length=16,
        choices=AmortizationSystem.choices,
        null=True,
        blank=True,
        help_text="Sistema de amortizacion (si se modela).",
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
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        validators=[MinValueValidator(0)],
        help_text="Deuda pendiente (positiva). Si tracking_mode=accounting, este campo puede ignorarse en summary.",
    )
    principal_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "Capital inicial/original del pasivo. Si se informa junto con calendario/plazo, "
            "permite estimar saldo pendiente actual automaticamente."
        ),
    )
    opening_fees_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Comisiones de apertura (importe) si aplica, especialmente en hipoteca.",
    )
    early_repayment_fee_percent = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Comision por amortizacion anticipada (% sobre capital amortizado), si aplica.",
    )
    novation_subrogation_fee_amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Coste estimado de novacion/subrogacion (importe), si aplica.",
    )
    linked_products_monthly_cost = models.DecimalField(
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "Coste mensual de productos vinculados (seguros, etc.) si se desea registrar "
            "como metadata del pasivo."
        ),
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


class LiquidityMonthlyCheckin(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmado"
        ADJUSTED = "adjusted", "Ajustado"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="liquidity_monthly_checkins",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="liquidity_monthly_checkins",
    )
    fiscal_year = models.PositiveSmallIntegerField(default=timezone.now().year)
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    closing_balance_real = models.DecimalField(max_digits=20, decimal_places=8)
    note = models.CharField(max_length=240, blank=True, default="")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "fiscal_year", "month"], name="nw_liq_chk_user_ym_idx"),
            models.Index(fields=["asset"], name="nw_liq_chk_asset_idx"),
        ]
        ordering = ["-fiscal_year", "-month", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "asset", "fiscal_year", "month"],
                name="unique_liq_checkin_user_asset_year_month",
            )
        ]

    def __str__(self) -> str:
        return (
            f"LiquidityMonthlyCheckin(user={self.user_id}, asset={self.asset_id}, "
            f"{self.fiscal_year}-{self.month}, real={self.closing_balance_real})"
        )
