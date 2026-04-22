from __future__ import annotations

import os

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured


def get_fernet() -> Fernet:
    raw_key = os.environ.get("BROKER_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        raise ImproperlyConfigured("BROKER_ENCRYPTION_KEY no está configurada.")
    try:
        return Fernet(raw_key.encode())
    except Exception as exc:  # pragma: no cover - library handles exact error variants
        raise ImproperlyConfigured("BROKER_ENCRYPTION_KEY inválida para Fernet.") from exc


def encrypt(value: str) -> bytes:
    return get_fernet().encrypt(value.encode())


def decrypt(encrypted: bytes) -> str:
    return get_fernet().decrypt(encrypted).decode()
