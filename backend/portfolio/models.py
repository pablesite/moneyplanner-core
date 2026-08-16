from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Portfolio(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolio",
    )
    base_currency = models.CharField(max_length=3, default="EUR")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Portfolio(user={self.user_id}, base_currency={self.base_currency})"


class InvestmentContainer(models.Model):
    class ContainerType(models.TextChoices):
        BROKER = "broker", "Broker"
        BANK = "bank", "Banco"
        EXCHANGE = "exchange", "Exchange"
        WALLET = "wallet", "Wallet"
        PENSION = "pension", "Plan de pensiones"
        PLATFORM = "platform", "Plataforma"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="containers",
    )
    name = models.CharField(max_length=120)
    container_type = models.CharField(max_length=16, choices=ContainerType.choices)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "name"],
                name="portfolio_container_name_unique",
            )
        ]

    def __str__(self) -> str:
        return f"InvestmentContainer(portfolio={self.portfolio_id}, name={self.name})"


class ContainerCashAccount(models.Model):
    container = models.ForeignKey(
        InvestmentContainer,
        on_delete=models.CASCADE,
        related_name="cash_accounts",
    )
    ledger_account = models.OneToOneField(
        "accounting.LedgerAccount",
        on_delete=models.PROTECT,
        related_name="portfolio_cash_link",
    )
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["currency", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["container", "currency"],
                name="portfolio_container_cash_currency_unique",
            )
        ]

    def clean(self) -> None:
        if not self.container_id or not self.ledger_account_id:
            return
        account = self.ledger_account
        if account.user_id != self.container.portfolio.user_id:
            raise ValidationError("La cuenta de efectivo pertenece a otro usuario.")
        if account.account_type != "asset":
            raise ValidationError("La cuenta de efectivo debe ser de tipo asset.")
        if account.currency != self.currency:
            raise ValidationError("La moneda debe coincidir con la cuenta contable.")


class Instrument(models.Model):
    class IdentityKind(models.TextChoices):
        CUSTOM = "custom", "Custom"
        CANONICAL = "canonical", "Canónico"

    class AssetClass(models.TextChoices):
        CASH = "cash", "Efectivo"
        FIXED_INCOME = "fixed_income", "Renta fija"
        EQUITY = "equity", "Renta variable"
        MIXED = "mixed", "Mixto"
        REAL_ASSETS = "real_assets", "Activos reales"
        CRYPTO = "crypto", "Cripto"
        OTHER = "other", "Otros"

    class InstrumentType(models.TextChoices):
        CASH = "cash", "Efectivo"
        DEPOSIT = "deposit", "Depósito"
        FUND = "fund", "Fondo"
        ETF = "etf", "ETF"
        STOCK = "stock", "Acción"
        PENSION_PLAN = "pension_plan", "Plan de pensiones"
        CRYPTO = "crypto", "Criptoactivo"
        CROWDFUNDING = "crowdfunding", "Crowdfunding"
        OTHER = "other", "Otros"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="portfolio_instruments",
        help_text="Null para instrumentos canónicos compartidos.",
    )
    identity_kind = models.CharField(max_length=16, choices=IdentityKind.choices)
    name = models.CharField(max_length=160)
    asset_class = models.CharField(max_length=24, choices=AssetClass.choices)
    instrument_type = models.CharField(max_length=24, choices=InstrumentType.choices)
    quote_currency = models.CharField(max_length=3)
    isin = models.CharField(max_length=12, blank=True, default="")
    ticker = models.CharField(max_length=32, blank=True, default="")
    market = models.CharField(max_length=32, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(identity_kind="canonical", user__isnull=True)
                    | Q(identity_kind="custom", user__isnull=False)
                ),
                name="portfolio_instrument_identity_owner_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(identity_kind="custom") | ~Q(isin="") | (~Q(ticker="") & ~Q(market=""))
                ),
                name="portfolio_canonical_identity_required",
            ),
            models.UniqueConstraint(
                fields=["user", "name", "quote_currency"],
                condition=Q(identity_kind="custom"),
                name="portfolio_custom_instrument_unique",
            ),
            models.UniqueConstraint(
                fields=["isin"],
                condition=Q(identity_kind="canonical") & ~Q(isin=""),
                name="portfolio_canonical_isin_unique",
            ),
            models.UniqueConstraint(
                fields=["ticker", "market"],
                condition=(Q(identity_kind="canonical") & ~Q(ticker="") & ~Q(market="")),
                name="portfolio_canonical_ticker_market_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"Instrument(name={self.name}, kind={self.identity_kind})"


class InstrumentProviderMapping(models.Model):
    class Provider(models.TextChoices):
        TWELVE_DATA = "twelve_data", "Twelve Data"
        COINGECKO = "coingecko", "CoinGecko"

    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name="provider_mappings",
    )
    provider = models.CharField(max_length=24, choices=Provider.choices)
    provider_symbol = models.CharField(max_length=96)
    provider_market = models.CharField(max_length=32, blank=True, default="")
    quote_currency = models.CharField(max_length=3)
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["instrument_id", "provider"]
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "provider", "quote_currency"],
                name="portfolio_instrument_provider_quote_unique",
            ),
            models.CheckConstraint(
                condition=Q(is_confirmed=False) | Q(confirmed_at__isnull=False),
                name="portfolio_confirmed_mapping_has_timestamp",
            ),
        ]

    def clean(self) -> None:
        if self.provider == self.Provider.TWELVE_DATA and not self.provider_market:
            raise ValidationError("Twelve Data requiere mercado confirmado.")
        if self.is_confirmed and not self.confirmed_at:
            raise ValidationError("Un mapeo confirmado requiere confirmed_at.")

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_symbol}@{self.provider_market or '-'}"


class InstrumentPrice(models.Model):
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name="prices",
    )
    provider_mapping = models.ForeignKey(
        InstrumentProviderMapping,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prices",
    )
    price_date = models.DateField()
    close = models.DecimalField(
        max_digits=28,
        decimal_places=12,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3)
    source = models.CharField(max_length=32)
    source_key = models.CharField(max_length=128)
    source_market = models.CharField(max_length=32, blank=True, default="")
    fetched_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-price_date", "-id"]
        indexes = [
            models.Index(fields=["instrument", "price_date"], name="portfolio_price_date_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "price_date", "source", "source_key"],
                name="portfolio_instrument_price_source_unique",
            )
        ]


class PositionValuation(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        LEGACY_ASSET = "legacy_asset", "Derivada de AssetValuation"
        LEGACY_LEDGER = "legacy_ledger", "Derivada de revalorización contable"

    position = models.ForeignKey(
        "PortfolioPosition",
        on_delete=models.CASCADE,
        related_name="manual_valuations",
    )
    valuation_date = models.DateField()
    value = models.DecimalField(
        max_digits=28,
        decimal_places=8,
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(max_length=3)
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.MANUAL)
    legacy_asset_valuation = models.OneToOneField(
        "net_worth.AssetValuation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portfolio_derived_valuation",
    )
    legacy_ledger_transaction = models.ForeignKey(
        "accounting.LedgerTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="portfolio_derived_valuations",
    )
    note = models.CharField(max_length=240, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-valuation_date", "-id"]
        indexes = [
            models.Index(
                fields=["position", "valuation_date"],
                name="portfolio_valuation_date_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["position", "valuation_date", "source"],
                name="portfolio_position_valuation_source_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        source="legacy_asset",
                        legacy_asset_valuation__isnull=False,
                        legacy_ledger_transaction__isnull=True,
                    )
                    | Q(
                        source="legacy_ledger",
                        legacy_asset_valuation__isnull=True,
                        legacy_ledger_transaction__isnull=False,
                    )
                    | Q(
                        source="manual",
                        legacy_asset_valuation__isnull=True,
                        legacy_ledger_transaction__isnull=True,
                    )
                ),
                name="portfolio_position_valuation_source_valid",
            ),
        ]


class PortfolioPosition(models.Model):
    class TrackingStyle(models.TextChoices):
        VALUE_BASED = "value_based", "Por valor"
        UNITS_BASED = "units_based", "Por unidades"

    class Status(models.TextChoices):
        ACTIVE = "active", "Activa"
        ARCHIVED = "archived", "Archivada"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="positions",
    )
    container = models.ForeignKey(
        InvestmentContainer,
        on_delete=models.PROTECT,
        related_name="positions",
    )
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.PROTECT,
        related_name="positions",
    )
    asset = models.OneToOneField(
        "net_worth.Asset",
        on_delete=models.PROTECT,
        related_name="portfolio_position",
    )
    ledger_account = models.ForeignKey(
        "accounting.LedgerAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="portfolio_positions",
    )
    tracking_style = models.CharField(max_length=16, choices=TrackingStyle.choices)
    status = models.CharField(max_length=16, choices=Status.choices)
    opened_on = models.DateField()
    closed_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["instrument__name", "id"]
        indexes = [
            models.Index(fields=["portfolio", "status"], name="portfolio_pos_status_idx"),
            models.Index(fields=["container", "status"], name="portfolio_pos_container_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(closed_on__isnull=True) | Q(closed_on__gte=models.F("opened_on")),
                name="portfolio_position_dates_valid",
            )
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}
        user_id = self.portfolio.user_id if self.portfolio_id else None
        if self.container_id and self.container.portfolio_id != self.portfolio_id:
            errors["container"] = "El contenedor debe pertenecer a la cartera."
        if self.asset_id:
            if self.asset.user_id != user_id:
                errors["asset"] = "El activo pertenece a otro usuario."
            if self.asset.category != "investments":
                errors["asset"] = "La posición debe enlazar un activo de inversión."
        if self.instrument_id and self.instrument.user_id not in {None, user_id}:
            errors["instrument"] = "El instrumento pertenece a otro usuario."
        if self.ledger_account_id:
            account = self.ledger_account
            if account.user_id != user_id:
                errors["ledger_account"] = "La cuenta contable pertenece a otro usuario."
            elif account.account_type != "asset" or account.asset_id != self.asset_id:
                errors["ledger_account"] = "La cuenta debe ser el enlace asset del activo."
            elif account.currency != self.asset.currency:
                errors["ledger_account"] = "La moneda de la cuenta debe coincidir con el activo."
        if errors:
            raise ValidationError(errors)


class PositionOwnershipPeriod(models.Model):
    position = models.ForeignKey(
        PortfolioPosition,
        on_delete=models.CASCADE,
        related_name="ownership_periods",
    )
    ownership = models.ForeignKey(
        "memberships.Ownership",
        on_delete=models.PROTECT,
        related_name="portfolio_ownership_periods",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["position", "start_date"],
                name="portfolio_ownership_period_start_unique",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=models.F("start_date")),
                name="portfolio_ownership_period_dates_valid",
            ),
        ]

    def clean(self) -> None:
        if self.position_id and self.ownership_id:
            if self.position.portfolio.user_id != self.ownership.user_id:
                raise ValidationError("La titularidad pertenece a otro usuario.")
        if self.pk:
            raise ValidationError("Los periodos de titularidad son inmutables.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Los periodos de titularidad son inmutables.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los periodos de titularidad son inmutables.")


class PositionOwnershipShare(models.Model):
    period = models.ForeignKey(
        PositionOwnershipPeriod,
        on_delete=models.CASCADE,
        related_name="shares",
    )
    member = models.ForeignKey(
        "memberships.FamilyMember",
        on_delete=models.PROTECT,
        related_name="portfolio_ownership_shares",
    )
    percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["member_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["period", "member"],
                name="portfolio_ownership_share_member_unique",
            )
        ]

    def clean(self) -> None:
        if self.period_id and self.member_id:
            if self.period.position.portfolio.user_id != self.member.user_id:
                raise ValidationError("El miembro pertenece a otro usuario.")
        if self.pk:
            raise ValidationError("Las participaciones históricas son inmutables.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Las participaciones históricas son inmutables.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Las participaciones históricas son inmutables.")


class PortfolioMigrationIssue(models.Model):
    class Code(models.TextChoices):
        LEDGER_ACCOUNT_MISSING = "ledger_account_missing", "Cuenta contable ausente"
        LEDGER_ACCOUNT_AMBIGUOUS = "ledger_account_ambiguous", "Cuenta contable ambigua"
        OWNERSHIP_MISSING = "ownership_missing", "Titularidad ausente"
        OWNERSHIP_DYNAMIC = "ownership_dynamic", "Titularidad dinámica"
        OWNERSHIP_SHARES_INVALID = "ownership_shares_invalid", "Reparto inválido"
        BOOTSTRAP_ERROR = "bootstrap_error", "Error de migración"

    class Status(models.TextChoices):
        OPEN = "open", "Pendiente"
        RESOLVED = "resolved", "Resuelta"

    portfolio = models.ForeignKey(
        Portfolio,
        on_delete=models.CASCADE,
        related_name="migration_issues",
    )
    asset = models.ForeignKey(
        "net_worth.Asset",
        on_delete=models.CASCADE,
        related_name="portfolio_migration_issues",
    )
    code = models.CharField(max_length=32, choices=Code.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    detail = models.CharField(max_length=240, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_id", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "asset", "code"],
                name="portfolio_migration_issue_unique",
            )
        ]
