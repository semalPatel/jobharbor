from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class JobConnector(Protocol):
    """Contract for source connectors that fetch raw job records."""

    def fetch_jobs(self) -> Sequence[dict[str, Any]]:
        ...
