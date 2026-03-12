from collections.abc import Mapping, Sequence
from typing import Any

from jobharbor.connectors.base import JobConnector, validate_jobs_payload
from jobharbor.connectors.http_client import HttpClient


class GreenhouseConnector(JobConnector):
    """Fetch and normalize jobs from the Greenhouse board API."""

    def __init__(self, http_client: HttpClient, board_token: str, page_size: int = 100) -> None:
        self._http_client = http_client
        self._board_token = board_token
        self._page_size = page_size
        self._base_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

    def fetch_jobs(self) -> Sequence[Mapping[str, Any]]:
        page = 1
        normalized: list[dict[str, str]] = []

        while True:
            payload = self._http_client.get_json(
                self._base_url,
                params={
                    "content": "true",
                    "page": str(page),
                    "per_page": str(self._page_size),
                },
            )
            rows = self._extract_jobs(payload)
            if not rows:
                break

            normalized.extend(self._normalize_job(row) for row in rows)
            page += 1

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
        if isinstance(payload, Mapping):
            jobs = payload.get("jobs", [])
            if not isinstance(jobs, Sequence):
                return []
            return validate_jobs_payload(jobs)

        if isinstance(payload, Sequence):
            return validate_jobs_payload(payload)

        return []

    def _normalize_job(self, row: Mapping[str, Any]) -> dict[str, str]:
        location = row.get("location")
        company = row.get("company")

        return {
            "external_id": self._as_text(row.get("id")),
            "title": self._as_text(row.get("title")),
            "company": self._as_text(row.get("company_name") or self._nested_value(company, "name")),
            "location": self._normalize_location(location),
            "url": self._as_text(row.get("absolute_url") or row.get("hosted_url")),
            "posted_at": self._as_text(
                row.get("updated_at") or row.get("first_published") or row.get("created_at")
            ),
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
