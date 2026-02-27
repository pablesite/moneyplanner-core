from django.utils import timezone


def resolve_confirmed_at(current_confirmed_at, status_value, skipped_status):
    if status_value == skipped_status:
        return None
    return current_confirmed_at or timezone.now()
