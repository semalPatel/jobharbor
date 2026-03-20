from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from jobharbor.connectors.base import JobConnector, validate_jobs_payload
from jobharbor.models import RunStatus

ROLLOUT_SOURCE_ORDER: tuple[str, ...] = ("greenhouse", "ashby", "lever", "smartrecruiters", "ycombinator")


def order_connectors_for_rollout(
    connectors: Sequence[tuple[str, JobConnector]],
) -> list[tuple[str, JobConnector]]:
    order_lookup = {source: index for index, source in enumerate(ROLLOUT_SOURCE_ORDER)}
    return sorted(
        list(connectors),
        key=lambda item: (
            order_lookup.get(item[0], len(ROLLOUT_SOURCE_ORDER)),
            item[0],
        ),
    )


@dataclass(frozen=True)
class DiscoveryRunOutcome:
    status: RunStatus
    total_jobs: int
    connectors_total: int
    connectors_failed: int
    failure_details: list[dict[str, str]]

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
        self._connectors = order_connectors_for_rollout(connectors)

    def discover(self) -> tuple[list[dict[str, Any]], DiscoveryRunOutcome]:
        normalized_jobs: list[dict[str, Any]] = []
        failure_details: list[dict[str, str]] = []

        for source, connector in self._connectors:
            try:
                rows = validate_jobs_payload(connector.fetch_jobs())
            except Exception as exc:
                failure_details.append(
                    {
                        "source": source,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                continue

            connector_jobs = [self._normalize_job(source, row) for row in rows]
            connector_jobs.sort(key=self._job_sort_key)
            normalized_jobs.extend(connector_jobs)

        connector_failures = len(failure_details)
        run_status = self._resolve_run_status(
            connectors_total=len(self._connectors),
            connectors_failed=connector_failures,
        )
        outcome = DiscoveryRunOutcome(
            status=run_status,
            total_jobs=len(normalized_jobs),
            connectors_total=len(self._connectors),
            connectors_failed=connector_failures,
            failure_details=failure_details,
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
            self._as_sortable_text(job.get("external_id")),
            self._as_sortable_text(job.get("posted_at")),
            self._as_sortable_text(job.get("title")),
            self._as_sortable_text(job.get("company")),
            self._as_sortable_text(job.get("location")),
            self._as_sortable_text(job.get("url")),
        )

    def _as_sortable_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return ""
