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
    inflation_region = models.CharField(max_length=10, default="ES")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return (
            "UserSettings("
            f"user_id={self.user_id}, "
            f"base_currency={self.base_currency}, "
            f"inflation_region={self.inflation_region}"
            ")"
        )


class ExternalIdentity(models.Model):
    class Provider(models.TextChoices):
        EXTERNAL = "external", "External"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="external_identities",
    )
    provider = models.CharField(max_length=16, choices=Provider.choices)
    external_user_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_user_id"],
                name="accounts_ext_identity_provider_userid_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["provider", "external_user_id"]),
            models.Index(fields=["user", "provider"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.external_user_id} -> user:{self.user_id}"
