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
        """De qué depende que la posición suba o baje.

        Una sola dimensión: el riesgo que se asume. El rol en la cartera (refugio,
        crecimiento), la estrategia (trading) y el propósito (liquidez para
        oportunidades) son ejes distintos, y mezclarlos aquí sacaba a cada activo de su
        clase real: "activos refugio" juntaba el oro con las criptomonedas, que se
        comportan al revés. El envoltorio tampoco es la clase: un plan de pensiones es
        fiscalidad y un ETF es un vehículo.

        El orden es el que recorre la paleta del gráfico, así que clases contiguas llevan
        tonos separados: primero las dos troncales, luego las especializaciones y "Otros"
        al final como cajón de sastre.
        """

        EQUITY = "equity", "Renta variable"
        FIXED_INCOME = "fixed_income", "Renta fija"
        REAL_ESTATE = "real_estate", "Inmobiliario"
        PRIVATE_DEBT = "private_debt", "Deuda privada"
        COMMODITIES = "commodities", "Materias primas"
        PRIVATE_EQUITY = "private_equity", "Capital privado"
        CRYPTO = "crypto", "Criptoactivos"
        CASH = "cash", "Liquidez"
        # El satélite: la bolsa acotada donde se experimenta y donde el dinero puede
        # perderse. No es una clase de riesgo sino un mandato, y es la única excepción
        # deliberada al eje único: de una bolsa así lo que importa es cuánto pesa, no de
        # qué está hecha, porque su contenido es provisional por naturaleza. El precio es
        # que lo que hay dentro no muestra su riesgo real, y por eso conviene que sea
        # pequeña.
        TRADING = "trading", "Trading"
        OTHER = "other", "Otros"
        # "Otros" es una respuesta: has mirado el activo y no encaja en ninguna clase.
        # Esto es la ausencia de respuesta, y son cosas distintas. El vehiculo determina
        # la clase en cripto o crowdlending, pero un fondo, un ETF, un plan o un
        # roboadvisor pueden ser cualquier cosa, asi que ahi nadie ha contestado todavia
        # y meterlo en "Otros" lo hacia parecer decidido.
        UNCLASSIFIED = "unclassified", "Sin clasificar"

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
        # A derived valuation is a projection of the ledger, so it must not block the
        # deletion of the revaluation it came from; it disappears with its source.
        on_delete=models.CASCADE,
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

    class HistoryMode(models.TextChoices):
        RECONSTRUCTED = "reconstructed", "Histórico reconstruido"
        CUTOFF = "cutoff", "Inicio desde fecha de corte"

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
    # How *this* portfolio classifies the position. Canonical instruments are shared
    # across portfolios so their class cannot be edited from one of them; keeping the
    # choice here lets every position be classified while the instrument's own class
    # stays the default for anyone who has not chosen.
    asset_class_override = models.CharField(
        max_length=24,
        choices=Instrument.AssetClass.choices,
        blank=True,
        default="",
    )
    # Si la posicion admite traspaso sin peaje fiscal. En Espana los traspasos entre
    # fondos y planes de pensiones son neutros y el resto tributa, asi que construir
    # dentro de la bolsa traspasable deja el rebalanceo futuro gratis. No es un motor
    # fiscal: es el unico dato sin el cual una recomendacion puede salir cara.
    tax_transferable = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices)
    opened_on = models.DateField()
    closed_on = models.DateField(null=True, blank=True)
    history_mode = models.CharField(
        max_length=16, choices=HistoryMode.choices, default=HistoryMode.RECONSTRUCTED
    )
    history_start_date = models.DateField(null=True, blank=True)
    setup_confirmed_at = models.DateTimeField(null=True, blank=True)
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
            ),
            models.CheckConstraint(
                condition=(
                    Q(history_mode="reconstructed", history_start_date__isnull=True)
                    | Q(history_mode="cutoff", history_start_date__isnull=False)
                ),
                name="portfolio_position_history_mode_valid",
            ),
        ]

    @property
    def effective_asset_class(self) -> str:
        """The class this portfolio uses, falling back to the instrument's own."""
        return self.asset_class_override or self.instrument.asset_class

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


class PositionClassBreakdown(models.Model):
    """Reparto interno de una posición entre varias clases de activo.

    Una cartera de roboadvisor o un fondo mixto no son de una sola clase, y meterlos
    entera en la dominante desplaza el gráfico de composición tanto como pese la
    posición: una cartera 60/40 que cuenta como renta variable hace desaparecer toda su
    renta fija. Solo afecta a la composición; el resto de cálculos siguen leyendo la
    clase efectiva, que no cambia.
    """

    position = models.ForeignKey(
        PortfolioPosition,
        on_delete=models.CASCADE,
        related_name="class_breakdown",
    )
    asset_class = models.CharField(max_length=24, choices=Instrument.AssetClass.choices)
    percent = models.DecimalField(max_digits=6, decimal_places=3)

    class Meta:
        ordering = ["-percent", "asset_class"]
        constraints = [
            models.UniqueConstraint(
                fields=["position", "asset_class"],
                name="portfolio_class_breakdown_unique",
            ),
            models.CheckConstraint(
                condition=Q(percent__gt=0) & Q(percent__lte=100),
                name="portfolio_class_breakdown_percent_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.position_id}:{self.asset_class}={self.percent}"


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

    def _only_closure_changed(self) -> bool:
        """El único cambio admitido: abrir o cerrar el final del tramo.

        La titularidad pasada no se reescribe, porque de ella dependen las cifras ya
        calculadas. Pero poner fin a un tramo abierto no es reescribirlo: es terminar de
        registrarlo, y es lo que ocurre cuando algo deja de ser compartido. Lo inverso
        —reabrirlo— es lo que hace falta para deshacer el tramo siguiente.
        """
        stored = (
            type(self)
            .objects.filter(pk=self.pk)
            .values("position_id", "ownership_id", "start_date")
            .first()
        )
        return stored is not None and (
            stored["position_id"] == self.position_id
            and stored["ownership_id"] == self.ownership_id
            and stored["start_date"] == self.start_date
        )

    def clean(self) -> None:
        if self.position_id and self.ownership_id:
            if self.position.portfolio.user_id != self.ownership.user_id:
                raise ValidationError("La titularidad pertenece a otro usuario.")
        if self.pk and not self._only_closure_changed():
            raise ValidationError("Los periodos de titularidad son inmutables.")

    def save(self, *args, **kwargs):
        if self.pk and not self._only_closure_changed():
            raise ValidationError("Los periodos de titularidad son inmutables.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Solo el último tramo se puede deshacer: corregir una fecha mal puesta exige
        # borrar y volver a escribir, pero borrar uno intermedio dejaría un hueco sin
        # titularidad en medio de la historia.
        if (
            type(self)
            .objects.filter(position_id=self.position_id, start_date__gt=self.start_date)
            .exists()
        ):
            raise ValidationError("Solo se puede deshacer el último tramo de titularidad.")
        return super().delete(*args, **kwargs)


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


class PortfolioTrade(models.Model):
    class OperationType(models.TextChoices):
        BUY = "buy", "Compra"
        SELL = "sell", "Venta"
        DIVIDEND = "dividend", "Dividendo"
        INTEREST = "interest", "Interés"
        FEE = "fee", "Comisión"
        FUNDED_PURCHASE = "funded_purchase", "Compra histórica financiada"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        CSV = "csv", "CSV"
        LEGACY = "legacy", "Histórico"

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="trades")
    position = models.ForeignKey(PortfolioPosition, on_delete=models.PROTECT, related_name="trades")
    ledger_transaction = models.OneToOneField(
        "accounting.LedgerTransaction",
        on_delete=models.PROTECT,
        related_name="portfolio_trade",
    )
    fee_transaction = models.OneToOneField(
        "accounting.LedgerTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="portfolio_trade_fee",
    )
    operation_type = models.CharField(max_length=24, choices=OperationType.choices)
    units = models.DecimalField(max_digits=28, decimal_places=12, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=28, decimal_places=12, null=True, blank=True)
    trade_currency = models.CharField(max_length=3)
    gross_amount = models.DecimalField(max_digits=28, decimal_places=8)
    fee = models.DecimalField(max_digits=28, decimal_places=8, default=Decimal("0"))
    external_id = models.CharField(max_length=160, blank=True, default="")
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    fingerprint = models.CharField(max_length=64)
    note = models.CharField(max_length=240, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ledger_transaction__booking_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "source", "external_id"],
                condition=~Q(external_id=""),
                name="portfolio_trade_external_source_unique",
            ),
            models.UniqueConstraint(
                fields=["portfolio", "fingerprint"],
                name="portfolio_trade_fingerprint_unique",
            ),
        ]


class PortfolioCorporateAction(models.Model):
    class ActionType(models.TextChoices):
        SPLIT = "split", "Split / contrasplit"
        IDENTIFIER_CHANGE = "identifier_change", "Cambio de identificador"
        POSITION_TRANSFER = "position_transfer", "Traspaso entre posiciones"
        ADJUSTMENT = "adjustment", "Ajuste manual"

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="corporate_actions"
    )
    position = models.ForeignKey(
        PortfolioPosition, on_delete=models.PROTECT, related_name="corporate_actions"
    )
    ledger_transaction = models.OneToOneField(
        "accounting.LedgerTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="portfolio_corporate_action",
    )
    action_type = models.CharField(max_length=32, choices=ActionType.choices)
    effective_date = models.DateField()
    payload = models.JSONField(default=dict)
    note = models.CharField(max_length=240, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "-id"]


class PortfolioImportBatch(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Subido"
        PREVIEWED = "previewed", "Previsualizado"
        PARTIAL = "partial", "Confirmado parcialmente"
        CONFIRMED = "confirmed", "Confirmado"
        FAILED = "failed", "Fallido"

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="import_batches"
    )
    filename = models.CharField(max_length=240)
    file_fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADED)
    headers = models.JSONField(default=list)
    mapping = models.JSONField(default=dict)
    row_count = models.PositiveIntegerField(default=0)
    confirmed_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "file_fingerprint"],
                name="portfolio_import_file_unique",
            )
        ]


class PortfolioImportRow(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        VALID = "valid", "Válida"
        ERROR = "error", "Con errores"
        DUPLICATE = "duplicate", "Duplicada"
        CONFIRMED = "confirmed", "Confirmada"

    batch = models.ForeignKey(PortfolioImportBatch, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField()
    raw_data = models.JSONField(default=dict)
    normalized_data = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    errors = models.JSONField(default=dict)
    fingerprint = models.CharField(max_length=64, blank=True, default="")
    trade = models.OneToOneField(
        PortfolioTrade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="import_row",
    )

    class Meta:
        ordering = ["row_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "row_number"], name="portfolio_import_row_number_unique"
            )
        ]


class AllocationStrategy(models.Model):
    """La politica de inversion de un ambito de titularidad, versionada por fecha.

    El ambito es una `Ownership`, no un miembro: "lo de Pablo", "lo de Lucas" y "lo
    compartido al 50%" son mandatos distintos, con horizontes distintos, y mezclarlos en
    una sola politica no significa nada. Filtrar por miembro responde a otra pregunta
    —que parte economica te toca— y sigue viviendo en el filtro de titularidad.

    Se versiona en vez de editarse: juzgar una decision de marzo contra la politica de
    hoy no dice nada. La desviacion de marzo se mide contra lo que estaba escrito en
    marzo.
    """

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="allocation_strategies"
    )
    ownership = models.ForeignKey(
        "memberships.Ownership",
        on_delete=models.PROTECT,
        related_name="allocation_strategies",
    )
    effective_from = models.DateField()
    note = models.TextField(blank=True, default="")
    # Cuanta comision se tolera en una linea antes de que la operacion no merezca la
    # pena. Es una decision de politica y no una constante del programa: quien opera con
    # un broker sin comisiones querra cero tolerancia porque nunca aplica, y quien paga
    # por operacion querra fijar su propio umbral.
    max_cost_share = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=Decimal("0.005"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    # Importe minimo de una linea para las posiciones que no fijan el suyo. Sin esto el
    # reparto proponia compras de nueve centimos, que ningun broker ejecuta y nadie
    # querria hacer. Cero deja el comportamiento anterior.
    min_line_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "ownership", "effective_from"],
                name="portfolio_strategy_version_unique",
            )
        ]
        indexes = [models.Index(fields=["portfolio", "ownership", "effective_from"])]

    def clean(self) -> None:
        if self.portfolio_id and self.ownership_id:
            if self.portfolio.user_id != self.ownership.user_id:
                raise ValidationError("La titularidad pertenece a otro usuario.")

    def __str__(self) -> str:
        return f"{self.ownership_id}@{self.effective_from}"


class AllocationTarget(models.Model):
    """Un objetivo de la politica: una clase de activo o una posicion concreta.

    Dos niveles, como fija el modelo conceptual. La banda es lo que dispara una
    recomendacion; sin ella el sistema pediria rebalancear cada mes por ruido de mercado.
    La liquidez tactica no necesita modelo aparte: es el objetivo de la clase `cash`, y
    asi deja de ser el sobrante de la operacion para ser una linea declarada.
    """

    strategy = models.ForeignKey(
        AllocationStrategy, on_delete=models.CASCADE, related_name="targets"
    )
    asset_class = models.CharField(
        max_length=24, choices=Instrument.AssetClass.choices, blank=True, default=""
    )
    position = models.ForeignKey(
        PortfolioPosition,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="allocation_targets",
    )
    target_percent = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    min_percent = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    max_percent = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ["-target_percent", "asset_class", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(asset_class="", position__isnull=False)
                    | (~Q(asset_class="") & Q(position__isnull=True))
                ),
                name="portfolio_target_one_level_only",
            ),
            models.CheckConstraint(
                condition=Q(target_percent__gte=0) & Q(target_percent__lte=100),
                name="portfolio_target_percent_range",
            ),
            models.UniqueConstraint(
                fields=["strategy", "asset_class"],
                condition=~Q(asset_class=""),
                name="portfolio_target_class_unique",
            ),
            models.UniqueConstraint(
                fields=["strategy", "position"],
                condition=Q(position__isnull=False),
                name="portfolio_target_position_unique",
            ),
        ]

    def clean(self) -> None:
        floor = self.min_percent
        ceiling = self.max_percent
        if floor is not None and floor > self.target_percent:
            raise ValidationError({"min_percent": "El minimo no puede superar al objetivo."})
        if ceiling is not None and ceiling < self.target_percent:
            raise ValidationError({"max_percent": "El maximo no puede quedar bajo el objetivo."})

    @property
    def key(self) -> str:
        return self.asset_class or f"position:{self.position_id}"


class ContributionBasket(models.Model):
    """Una propuesta de aportacion guardada, todavia sin efecto contable.

    El reparto no toca nada: se guarda, se revisa y solo la confirmacion crea operaciones
    reales. Es la misma disciplina de la importacion CSV, y por el mismo motivo: una
    propuesta que se ejecuta sola no se puede revisar.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Pendiente"
        CONFIRMED = "confirmed", "Confirmada"
        DISCARDED = "discarded", "Descartada"

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="contribution_baskets"
    )
    ownership = models.ForeignKey(
        "memberships.Ownership", on_delete=models.PROTECT, related_name="contribution_baskets"
    )
    strategy = models.ForeignKey(
        AllocationStrategy, on_delete=models.PROTECT, related_name="baskets"
    )
    booking_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reserved_cash = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    leftover = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    # De donde sale el dinero nuevo. Una compra se financia desde el efectivo del
    # contenedor, asi que la aportacion entra primero ahi desde la cuenta del banco.
    source_account = models.ForeignKey(
        "accounting.LedgerAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="portfolio_baskets",
    )
    explanation = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-booking_date", "-id"]
        indexes = [models.Index(fields=["portfolio", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="portfolio_basket_amount_positive"
            )
        ]

    def __str__(self) -> str:
        return f"basket:{self.id}:{self.status}"


class ContributionBasketLine(models.Model):
    """Un destino de la cesta: una posicion, o el efectivo de un contenedor.

    El efectivo es un destino de pleno derecho y no un apano: una plataforma con minimo
    de entrada alto no puede recibir la parte que le toca cada mes, asi que esa parte se
    acumula en su cuenta de efectivo —que es dinero real, en un sitio real— hasta que
    alcanza el minimo. Repartirla entre las demas la condenaria a no financiarse nunca.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        CONFIRMED = "confirmed", "Confirmada"
        SKIPPED = "skipped", "Descartada"

    basket = models.ForeignKey(ContributionBasket, on_delete=models.CASCADE, related_name="lines")
    position = models.ForeignKey(
        PortfolioPosition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="basket_lines",
    )
    cash_account = models.ForeignKey(
        ContainerCashAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="basket_lines",
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reason = models.CharField(max_length=32, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    ledger_transaction = models.ForeignKey(
        "accounting.LedgerTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portfolio_basket_lines",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-amount", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(position__isnull=False, cash_account__isnull=True)
                    | Q(position__isnull=True, cash_account__isnull=False)
                ),
                name="portfolio_basket_line_one_target",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="portfolio_basket_line_amount_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"line:{self.id}:{self.amount}"


class ContributionCommitment(models.Model):
    """Dinero que hay que llevar a un sitio pase lo que pase con la desviacion.

    No todo lo que se optimiza es la asignacion. Un plan de pensiones con 1.500 EUR al
    ano de tope deducible vale, a tipo marginal alto, varios cientos de euros seguros; la
    ganancia de rebalancear es una fraccion de punto. Cuando compiten, gana la deduccion,
    asi que esto se atiende antes que la politica y no en competencia con ella.

    Cubre dos formas del mismo compromiso: un suelo que se repite cada mes —mantener una
    aportacion periodica para conservar una ventaja del broker— y un cupo anual que hay
    que llenar antes de que acabe el ano.
    """

    class Period(models.TextChoices):
        MONTH = "month", "Mensual"
        YEAR = "year", "Anual"

    position = models.ForeignKey(
        PortfolioPosition,
        on_delete=models.CASCADE,
        related_name="commitments",
        null=True,
        blank=True,
    )
    # Un minimo puede ser del contenedor y no de un producto: MyInvestor pide 300 EUR al
    # mes en la plataforma, y da igual si van al plan de pensiones o al roboadvisor. Sin
    # esto habia que repartirlo a mano entre las posiciones, y entonces cada una tiraba
    # de su propio cupo cuando le convenia y algun mes el minimo de la plataforma se
    # quedaba sin cubrir.
    container = models.ForeignKey(
        InvestmentContainer,
        on_delete=models.CASCADE,
        related_name="commitments",
        null=True,
        blank=True,
    )
    period = models.CharField(max_length=8, choices=Period.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    reason = models.CharField(max_length=200, blank=True, default="")
    # Lo que cuesta al ano no cumplirlo. Un compromiso no vale por su importe sino por lo
    # que se pierde al romperlo: dejar la aportacion periodica del roboadvisor puede
    # tirar la remuneracion de toda la cuenta del banco, que es mucho mas dinero que la
    # aportacion. Cuando la aportacion no llega para todos, decide esto y no el orden en
    # que estan guardados.
    breach_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position_id", "container_id", "period"]
        constraints = [
            models.UniqueConstraint(
                fields=["position", "period"], name="portfolio_commitment_unique"
            ),
            models.UniqueConstraint(
                fields=["container", "period"], name="portfolio_commitment_container_unique"
            ),
            models.CheckConstraint(
                condition=(
                    Q(position__isnull=False, container__isnull=True)
                    | Q(position__isnull=True, container__isnull=False)
                ),
                name="portfolio_commitment_one_target",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="portfolio_commitment_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(breach_cost__gte=0), name="portfolio_commitment_breach_cost_positive"
            ),
        ]

    def __str__(self) -> str:
        target = self.position_id or f"c{self.container_id}"
        return f"{target}:{self.period}:{self.amount}"


class PositionAllocationRule(models.Model):
    """Como puede recibir dinero una posicion.

    Sin esto el reparto propone importes que no se pueden ejecutar: un fondo con minimo
    de suscripcion, una posicion archivada que no deberia recibir nada nunca, o un
    producto que solo admite participaciones enteras.
    """

    position = models.OneToOneField(
        PortfolioPosition, on_delete=models.CASCADE, related_name="allocation_rule"
    )
    excluded = models.BooleanField(default=False)
    min_contribution = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    rounding_step = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    # Lo que cuesta una compra suelta. Un euro de comision sobre una linea de doce es un
    # 8%: mucho mas de lo que la propia linea puede aportar en un ano. El reparto tiene
    # que saberlo para no proponer operaciones que se comen a si mismas.
    operation_cost = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    # Una aportacion periodica del broker suele estar exenta de comision, asi que esa
    # linea no paga peaje aunque el resto si.
    fee_free_plan = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"rule:{self.position_id}"
