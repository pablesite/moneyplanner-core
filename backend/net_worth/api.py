from __future__ import annotations

from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError


def raise_api_validation_error(exc: ValidationError) -> None:
    message = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
    raise DRFValidationError({"detail": message}) from exc
