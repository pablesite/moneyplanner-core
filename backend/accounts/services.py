from __future__ import annotations

from .models import UserSettings


def get_or_create_user_settings(*, user) -> UserSettings:
    return UserSettings.objects.get_or_create(user=user)[0]


def update_user_settings(*, user, validated_data: dict) -> UserSettings:
    settings_obj = get_or_create_user_settings(user=user)
    for field, value in validated_data.items():
        setattr(settings_obj, field, value)
    settings_obj.save()
    return settings_obj
