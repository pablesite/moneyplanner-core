from rest_framework.exceptions import ValidationError as DRFValidationError


def parse_optional_int_query_param(query_params, name):
    value = (query_params.get(name) or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_required_int_query_param(query_params, name):
    value = (query_params.get(name) or "").strip()
    if not value:
        raise DRFValidationError({name: f"Query param '{name}' es obligatorio."})
    try:
        return int(value)
    except ValueError as exc:
        raise DRFValidationError({name: f"Query param '{name}' invalido."}) from exc
