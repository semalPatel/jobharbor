from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from jobharbor.connectors.base import JobConnector, validate_jobs_payload
from jobharbor.connectors.http_client import HttpClient


class SmartRecruitersConnector(JobConnector):
    """Fetch and normalize jobs from SmartRecruiters public postings API."""

    def __init__(self, *, http_client: HttpClient, company_slug: str) -> None:
        self._http_client = http_client
        self._company_slug = company_slug
        self._base_url = f"https://api.smartrecruiters.com/v1/companies/{company_slug}/postings"

    def fetch_jobs(self) -> Sequence[Mapping[str, Any]]:
        payload = self._http_client.get_json(self._base_url, params={"limit": "100"})
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
        postings = payload.get("content", [])
        if isinstance(postings, (str, bytes, bytearray)) or not isinstance(postings, (list, tuple)):
            return []
        if not all(isinstance(row, Mapping) for row in postings):
            return []
        return validate_jobs_payload(postings)

    def _normalize_job(self, row: Mapping[str, Any]) -> dict[str, str]:
        description = self._join_parts(
            self._as_text(row.get("industry")),
            self._as_text(row.get("department")),
            self._as_text(row.get("function")),
            self._as_text(row.get("typeOfEmployment")),
            self._as_text(row.get("experienceLevel")),
            self._flatten_custom_fields(row.get("customField")),
        )
        return {
            "external_id": self._as_text(row.get("id") or row.get("uuid")),
            "title": self._as_text(row.get("name")),
            "company": self._as_text(self._nested_value(row.get("company"), "name") or self._company_slug),
            "location": self._normalize_location(row.get("location")),
            "url": self._as_text(row.get("ref")),
            "posted_at": self._as_text(row.get("releasedDate")),
            "description": description,
        }

    def _normalize_location(self, location: Any) -> str:
        if isinstance(location, Mapping):
            city = self._as_text(location.get("city"))
            country = self._as_text(location.get("country"))
            if city and country:
                return f"{city}, {country}"
            return city or country
        return self._as_text(location)

    def _nested_value(self, value: Any, key: str) -> Any:
        if isinstance(value, Mapping):
            return value.get(key)
        return None

    def _as_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _flatten_custom_fields(self, value: Any) -> str:
        if isinstance(value, Mapping):
            return self._join_parts(*(self._as_text(v) for v in value.values()))
        if isinstance(value, (list, tuple)):
            return self._join_parts(*(self._as_text(v) for v in value))
        return self._as_text(value)

    def _join_parts(self, *parts: str) -> str:
        filtered = [part for part in parts if part.strip()]
        return " ".join(filtered)
