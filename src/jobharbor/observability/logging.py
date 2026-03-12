import json
import logging
from datetime import UTC, datetime
from typing import Any


LOGGER_NAME = "jobharbor"


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def emit_structured_log(
    *,
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    logger.log(level, json.dumps(payload, sort_keys=True))
