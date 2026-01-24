from django.db import models


class FxRate(models.Model):
    """
    Tipo de cambio simple.
    Convención:
    1 unit de from_currency = rate units de to_currency
    Ej: USD -> EUR, rate=0.92  =>  1 USD = 0.92 EUR
    """

    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=18, decimal_places=8)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("from_currency", "to_currency")
        indexes = [
            models.Index(fields=["from_currency", "to_currency"]),
        ]

    def __str__(self) -> str:
        return f"{self.from_currency} -> {self.to_currency} ({self.rate})"
