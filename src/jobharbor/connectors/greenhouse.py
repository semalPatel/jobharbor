from collections.abc import Mapping, Sequence
import json
from typing import Any

from jobharbor.connectors.base import JobConnector, validate_jobs_payload
from jobharbor.connectors.http_client import HttpClient


class GreenhouseConnector(JobConnector):
    """Fetch and normalize jobs from the Greenhouse board API."""

    MAX_PAGES_DEFAULT = 100

    def __init__(
        self,
        http_client: HttpClient,
        board_token: str,
        page_size: int = 100,
        max_pages: int = MAX_PAGES_DEFAULT,
    ) -> None:
        self._http_client = http_client
        self._board_token = board_token
        self._page_size = page_size
        self._max_pages = max_pages
        self._base_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

    def fetch_jobs(self) -> Sequence[Mapping[str, Any]]:
        normalized: list[dict[str, str]] = []
        seen_payload_fingerprints: set[str] = set()

        for page in range(1, self._max_pages + 1):
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

            payload_fingerprint = self._payload_fingerprint(rows)
            if payload_fingerprint in seen_payload_fingerprints:
                break
            seen_payload_fingerprints.add(payload_fingerprint)

            normalized.extend(self._normalize_job(row) for row in rows)

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
            return self._normalize_jobs_rows(jobs)

        return self._normalize_jobs_rows(payload)

    def _normalize_jobs_rows(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, (str, bytes, bytearray)):
            return []
        if not isinstance(value, (list, tuple)):
            return []
        if not all(isinstance(row, Mapping) for row in value):
            return []
        return validate_jobs_payload(value)

    def _payload_fingerprint(self, payload: Any) -> str:
        try:
            return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        except TypeError:
            return repr(payload)

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
