from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("auth.audit")


def log_auth_event(
    *, event: str, outcome: str, user_id: int | None = None, **metadata: Any
) -> None:
    payload = {
        "event": event,
        "outcome": outcome,
        "user_id": user_id,
        "metadata": metadata,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))
