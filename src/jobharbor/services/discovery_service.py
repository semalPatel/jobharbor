from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from jobharbor.connectors.base import JobConnector, validate_jobs_payload
from jobharbor.models import RunStatus


@dataclass(frozen=True)
class DiscoveryRunOutcome:
    status: RunStatus
    total_jobs: int
    connectors_total: int
    connectors_failed: int

    def to_run_log_payload(self) -> dict[str, str | RunStatus]:
        if self.connectors_failed == 0:
            message = f"discovered {self.total_jobs} jobs from {self.connectors_total} connectors"
        else:
            message = (
                f"discovered {self.total_jobs} jobs with {self.connectors_failed} connector failures"
            )

        return {
            "source": "discovery",
            "status": self.status,
            "message": message,
        }


class DiscoveryService:
    """Orchestrates discovery connector execution in deterministic configured order."""

    def __init__(self, connectors: Sequence[tuple[str, JobConnector]]) -> None:
        self._connectors = list(connectors)

    def discover(self) -> tuple[list[dict[str, Any]], DiscoveryRunOutcome]:
        normalized_jobs: list[dict[str, Any]] = []
        connector_failures = 0

        for source, connector in self._connectors:
            try:
                rows = validate_jobs_payload(connector.fetch_jobs())
            except Exception:
                connector_failures += 1
                continue

            connector_jobs = [self._normalize_job(source, row) for row in rows]
            connector_jobs.sort(key=self._job_sort_key)
            normalized_jobs.extend(connector_jobs)

        run_status = self._resolve_run_status(
            connectors_total=len(self._connectors),
            connectors_failed=connector_failures,
        )
        outcome = DiscoveryRunOutcome(
            status=run_status,
            total_jobs=len(normalized_jobs),
            connectors_total=len(self._connectors),
            connectors_failed=connector_failures,
        )
        return normalized_jobs, outcome

    def _resolve_run_status(self, *, connectors_total: int, connectors_failed: int) -> RunStatus:
        if connectors_failed == 0:
            return RunStatus.success
        if connectors_failed == connectors_total:
            return RunStatus.failed
        return RunStatus.partial_failure

    def _normalize_job(self, source: str, row: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        normalized["source"] = source
        return normalized

    def _job_sort_key(self, job: Mapping[str, Any]) -> tuple[str, str, str, str, str, str]:
        return (
            str(job.get("external_id", "")),
            str(job.get("posted_at", "")),
            str(job.get("title", "")),
            str(job.get("company", "")),
            str(job.get("location", "")),
            str(job.get("url", "")),
        )
