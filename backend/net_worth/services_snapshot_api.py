from __future__ import annotations

from rest_framework.exceptions import ValidationError as DRFValidationError

from .serializers import NetWorthSnapshotSerializer
from .services_snapshots import import_snapshots_bulk_for_user


def import_snapshots_bulk_from_request(*, user, request_data, request) -> dict[str, object]:
    if not isinstance(request_data, list):
        raise DRFValidationError({"detail": "Expected a JSON array of snapshots."})

    serializer = NetWorthSnapshotSerializer(
        data=request_data, many=True, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)

    result = import_snapshots_bulk_for_user(user=user, rows=serializer.validated_data)
    return {
        "ok": result["ok"],
        "created": result["created"],
        "updated": result["updated"],
        "snapshots": NetWorthSnapshotSerializer(result["snapshots"], many=True).data,
    }
