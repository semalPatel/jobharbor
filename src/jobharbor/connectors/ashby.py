from collections.abc import Mapping, Sequence
from typing import Any

from jobharbor.connectors.base import JobConnector, validate_jobs_payload
from jobharbor.connectors.http_client import HttpClient


class AshbyConnector(JobConnector):
    """Fetch and normalize jobs from the Ashby posting API."""

    def __init__(self, http_client: HttpClient, organization_slug: str) -> None:
        self._http_client = http_client
        self._organization_slug = organization_slug
        self._base_url = f"https://api.ashbyhq.com/posting-api/job-board/{organization_slug}"

    def fetch_jobs(self) -> Sequence[Mapping[str, Any]]:
        payload = self._http_client.get_json(
            self._base_url,
            params={"includeCompensation": "true"},
        )
        rows = self._extract_jobs(payload)
        normalized = [self._normalize_job(row) for row in rows]
        return sorted(
            normalized,
            key=lambda job: (
                job["external_id"],
                job["posted_at"],
                job["title"],
                job["company"],
                job["location"],
                job["url"],
            ),
        )

    def _extract_jobs(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, Mapping):
            return []
        jobs = payload.get("jobs", [])
        if isinstance(jobs, (str, bytes, bytearray)) or not isinstance(jobs, (list, tuple)):
            return []
        if not all(isinstance(row, Mapping) for row in jobs):
            return []
        return validate_jobs_payload(jobs)

    def _normalize_job(self, row: Mapping[str, Any]) -> dict[str, str]:
        return {
            "external_id": self._as_text(row.get("id")),
            "title": self._as_text(row.get("title")),
            "company": self._as_text(self._nested_value(row.get("team"), "name")),
            "location": self._normalize_location(row.get("location")),
            "url": self._as_text(row.get("jobUrl") or row.get("applyUrl")),
            "posted_at": self._as_text(row.get("publishedAt") or row.get("createdAt")),
        }

    def _normalize_location(self, location: Any) -> str:
        if isinstance(location, Mapping):
            return self._as_text(location.get("name"))
        return self._as_text(location)

    def _nested_value(self, value: Any, key: str) -> Any:
        if isinstance(value, Mapping):
            return value.get(key)
        return None

    def _as_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
