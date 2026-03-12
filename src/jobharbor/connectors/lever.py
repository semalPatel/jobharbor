from collections.abc import Mapping, Sequence
from typing import Any

from jobharbor.connectors.base import JobConnector, validate_jobs_payload
from jobharbor.connectors.http_client import HttpClient


class LeverConnector(JobConnector):
    """Fetch and normalize jobs from Lever postings API."""

    def __init__(self, http_client: HttpClient, company_slug: str) -> None:
        self._http_client = http_client
        self._company_slug = company_slug
        self._base_url = f"https://api.lever.co/v0/postings/{company_slug}"

    def fetch_jobs(self) -> Sequence[Mapping[str, Any]]:
        payload = self._http_client.get_json(self._base_url, params={"mode": "json"})
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
        if isinstance(payload, Mapping):
            postings = payload.get("postings", [])
        else:
            postings = payload

        if isinstance(postings, (str, bytes, bytearray)) or not isinstance(
            postings,
            (list, tuple),
        ):
            return []
        if not all(isinstance(row, Mapping) for row in postings):
            return []
        return validate_jobs_payload(postings)

    def _normalize_job(self, row: Mapping[str, Any]) -> dict[str, str]:
        categories = row.get("categories")
        return {
            "external_id": self._as_text(row.get("id")),
            "title": self._as_text(row.get("text") or row.get("title")),
            "company": self._as_text(row.get("company") or self._company_slug),
            "location": self._as_text(self._nested_value(categories, "location")),
            "url": self._as_text(row.get("hostedUrl") or row.get("applyUrl")),
            "posted_at": self._as_text(row.get("createdAt")),
        }

    def _nested_value(self, value: Any, key: str) -> Any:
        if isinstance(value, Mapping):
            return value.get(key)
        return None

    def _as_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
