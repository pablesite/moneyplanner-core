from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.views import exception_handler


def _normalize_error_details(detail):
    if isinstance(detail, dict):
        return {key: _normalize_error_details(value) for key, value in detail.items()}
    if isinstance(detail, list):
        return [_normalize_error_details(value) for value in detail]
    if isinstance(detail, ErrorDetail):
        return str(detail)
    return detail


def _infer_error_code(status_code: int, exc) -> str:
    if isinstance(exc, ValidationError):
        return "validation_error"
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "unauthorized"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "forbidden"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "not_found"
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return "server_error"
    return "api_error"


def _infer_message(status_code: int, details) -> str:
    if isinstance(details, dict) and "detail" in details and isinstance(details["detail"], str):
        return details["detail"]
    if isinstance(details, str):
        return details
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return "Unexpected server error."
    return "Request failed."


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    normalized_details = _normalize_error_details(response.data)
    response.data = {
        "error": {
            "code": _infer_error_code(response.status_code, exc),
            "message": _infer_message(response.status_code, normalized_details),
            "details": normalized_details,
        }
    }
    return response
