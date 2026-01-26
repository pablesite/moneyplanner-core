from django.db import models
from django.utils import timezone

class FxRate(models.Model):
    """
    Tipo de cambio simple.
    Convención:
    1 unit de from_currency = rate units de to_currency
    Ej: USD -> EUR, rate=0.92  =>  1 USD = 0.92 EUR
    """

    rate_date = models.DateField(default=timezone.localdate)

    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=18, decimal_places=8)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("from_currency", "to_currency", "rate_date")
        indexes = [
            models.Index(fields=["from_currency", "to_currency", "rate_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.from_currency}->{self.to_currency} {self.rate} ({self.rate_date})"


class InflationIndex(models.Model):
    """
    Índice de precios (IPC) mensual.

    Guardamos un índice (no %). Ej:
    - index=100.0 en un mes base
    - index=118.0 en otro mes
    Esto permite convertir valores nominales a "euros constantes" de un mes base.
    """

    class Region(models.TextChoices):
        ES = "ES", "España"
        # más adelante: "ES-MU" para Murcia, etc.

    region = models.CharField(max_length=10, choices=Region.choices, default=Region.ES)

    # Representa el mes. Convención: usar el día 1 del mes (YYYY-MM-01)
    period = models.DateField(help_text="Mes del índice (usar YYYY-MM-01)")

    index = models.DecimalField(max_digits=12, decimal_places=4)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["region", "period"], name="unique_inflation_region_period"),
        ]
        indexes = [
            models.Index(fields=["region", "period"]),
        ]
        ordering = ["-period"]

    def __str__(self) -> str:
        return f"InflationIndex(region={self.region}, period={self.period}, index={self.index})"
