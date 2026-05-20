from __future__ import annotations

from typing import cast

from django.core.exceptions import ObjectDoesNotExist

from .models import UserSettings


def get_or_create_user_settings(*, user) -> UserSettings:
    return UserSettings.objects.get_or_create(user=user)[0]


def _ensure_user_settings(user) -> None:
    try:
        user.settings  # noqa: B018 – triggers Django cached descriptor
    except ObjectDoesNotExist:
        UserSettings.objects.get_or_create(user=user)


def get_base_currency_for_user(*, user) -> str:
    _ensure_user_settings(user)
    return cast(str, user.settings.base_currency)


def update_user_settings(*, user, validated_data: dict) -> UserSettings:
    settings_obj = get_or_create_user_settings(user=user)
    for field, value in validated_data.items():
        setattr(settings_obj, field, value)
    settings_obj.save()
    return settings_obj
