import json
import logging
from datetime import UTC, datetime
from typing import Any


LOGGER_NAME = "jobharbor"


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def build_log_record(
    *,
    event: str,
    level: str,
    timestamp: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    event_name = event.strip()
    if not event_name:
        raise ValueError("event must be non-empty")

    level_name = level.strip()
    if not level_name:
        raise ValueError("level must be non-empty")

    ts = timestamp or datetime.now(UTC)
    return {
        "timestamp": ts.isoformat(),
        "level": level_name,
        "event": event_name,
        **fields,
    }


def emit_structured_log(
    *,
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    payload = build_log_record(event=event, level=logging.getLevelName(level), **fields)
    logger.log(level, json.dumps(payload, sort_keys=True))
