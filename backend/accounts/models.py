from django.conf import settings
from django.db import models


class UserSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="settings",
    )

    # ISO 4217 (EUR, USD, GBP...). En v1 lista cerrada en frontend.
    base_currency = models.CharField(max_length=3, default="EUR")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"UserSettings(user_id={self.user_id}, base_currency={self.base_currency})"
