from django.db import models
from django.utils import timezone


class FxRate(models.Model):
    """
    Simple FX rate.
    Convention:
    1 unit of from_currency = rate units of to_currency.
    """

    rate_date = models.DateField(default=timezone.localdate)
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    source = models.CharField(max_length=32, default="manual")
    source_key = models.CharField(max_length=128, blank=True, default="")
    managed_by_system = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("from_currency", "to_currency", "rate_date")
        indexes = [
            models.Index(fields=["from_currency", "to_currency", "rate_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.from_currency}->{self.to_currency} {self.rate} ({self.rate_date})"


INFLATION_REGION_CHOICES = [
    ("ES", "Espana"),
    ("ES-AN", "Andalucia"),
    ("ES-AR", "Aragon"),
    ("ES-AS", "Asturias"),
    ("ES-IB", "Illes Balears"),
    ("ES-CN", "Canarias"),
    ("ES-CB", "Cantabria"),
    ("ES-CL", "Castilla y Leon"),
    ("ES-CM", "Castilla-La Mancha"),
    ("ES-CT", "Cataluna"),
    ("ES-VC", "Comunitat Valenciana"),
    ("ES-EX", "Extremadura"),
    ("ES-GA", "Galicia"),
    ("ES-MD", "Comunidad de Madrid"),
    ("ES-MC", "Region de Murcia"),
    ("ES-NC", "Comunidad Foral de Navarra"),
    ("ES-PV", "Pais Vasco"),
    ("ES-RI", "La Rioja"),
    ("ES-CE", "Ceuta"),
    ("ES-ML", "Melilla"),
]


class InflationIndex(models.Model):
    """
    Monthly inflation index.

    Stores an index value, not a percentage, so values can be converted to constant euros.
    """

    class Region(models.TextChoices):
        ES = "ES", "Espana"
        ES_AN = "ES-AN", "Andalucia"
        ES_AR = "ES-AR", "Aragon"
        ES_AS = "ES-AS", "Asturias"
        ES_IB = "ES-IB", "Illes Balears"
        ES_CN = "ES-CN", "Canarias"
        ES_CB = "ES-CB", "Cantabria"
        ES_CL = "ES-CL", "Castilla y Leon"
        ES_CM = "ES-CM", "Castilla-La Mancha"
        ES_CT = "ES-CT", "Cataluna"
        ES_VC = "ES-VC", "Comunitat Valenciana"
        ES_EX = "ES-EX", "Extremadura"
        ES_GA = "ES-GA", "Galicia"
        ES_MD = "ES-MD", "Comunidad de Madrid"
        ES_MC = "ES-MC", "Region de Murcia"
        ES_NC = "ES-NC", "Comunidad Foral de Navarra"
        ES_PV = "ES-PV", "Pais Vasco"
        ES_RI = "ES-RI", "La Rioja"
        ES_CE = "ES-CE", "Ceuta"
        ES_ML = "ES-ML", "Melilla"

    region = models.CharField(max_length=10, choices=INFLATION_REGION_CHOICES, default=Region.ES)
    period = models.DateField(help_text="Month of the index. Use YYYY-MM-01.")
    index = models.DecimalField(max_digits=12, decimal_places=4)
    source = models.CharField(max_length=32, default="manual")
    source_key = models.CharField(max_length=128, blank=True, default="")
    managed_by_system = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["region", "period"], name="unique_inflation_region_period"
            ),
        ]
        indexes = [
            models.Index(fields=["region", "period"]),
        ]
        ordering = ["-period"]

    def __str__(self) -> str:
        return f"InflationIndex(region={self.region}, period={self.period}, index={self.index})"

    @classmethod
    def supported_regions(cls) -> list[dict[str, str]]:
        return [{"code": code, "label": label} for code, label in INFLATION_REGION_CHOICES]


class MarketDataSyncState(models.Model):
    class Dataset(models.TextChoices):
        FX = "fx", "FX"
        INFLATION = "inflation", "Inflation"
        INSTRUMENT_PRICES = "instrument_prices", "Instrument prices"

    dataset = models.CharField(max_length=32, choices=Dataset.choices)
    scope = models.CharField(max_length=64)
    required_start_date = models.DateField(null=True, blank=True)
    covered_until = models.DateField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    source = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "scope"], name="unique_market_data_dataset_scope"
            ),
        ]
        indexes = [
            models.Index(fields=["dataset", "scope"]),
        ]
        ordering = ["dataset", "scope"]

    def __str__(self) -> str:
        return f"MarketDataSyncState(dataset={self.dataset}, scope={self.scope})"
