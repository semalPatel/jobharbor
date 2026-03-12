from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class JobConnector(Protocol):
    """Contract for source connectors that fetch raw job records."""

    def fetch_jobs(self) -> Sequence[Mapping[str, Any]]:
        ...


def validate_jobs_payload(rows: Sequence[Mapping[str, Any]] | Sequence[Any]) -> list[dict[str, Any]]:
    """Normalize and validate connector payload shape for downstream processing."""

    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("connector payload entries must be mappings")
        normalized.append(dict(row))
    return normalized
