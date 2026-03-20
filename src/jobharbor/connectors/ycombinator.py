from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from html import unescape
import json
from typing import Any
from urllib import request as urllib_request

from jobharbor.connectors.base import JobConnector, validate_jobs_payload

WORK_AT_A_STARTUP_BASE_URL = "https://www.workatastartup.com"


class YCombinatorConnector(JobConnector):
    """Fetch and normalize jobs from Y Combinator's Work at a Startup listings page."""

    def __init__(
        self,
        *,
        jobs_url: str = "https://www.ycombinator.com/jobs",
        fetch_text: Callable[[str], str] | None = None,
    ) -> None:
        self._jobs_url = jobs_url
        self._fetch_text = fetch_text or _default_fetch_text

    def fetch_jobs(self) -> Sequence[Mapping[str, Any]]:
        html = self._fetch_text(self._jobs_url)
        rows = validate_jobs_payload(self._extract_rows(html))
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

    def _extract_rows(self, html: str) -> list[dict[str, Any]]:
        text = unescape(html or "")
        rows: list[dict[str, Any]] = []
        cursor = 0
        marker = '"jobPostings":['

        while True:
            start = text.find(marker, cursor)
            if start == -1:
                break
            open_bracket = start + len('"jobPostings":')
            payload, end_idx = _extract_balanced_json_array(text, open_bracket)
            if not payload:
                cursor = start + 1
                continue

            try:
                entries = json.loads(payload)
            except json.JSONDecodeError:
                cursor = end_idx
                continue

            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, Mapping):
                        rows.append(dict(entry))
            cursor = end_idx

        return rows

    def _normalize_job(self, row: Mapping[str, Any]) -> dict[str, str]:
        raw_url = self._as_text(row.get("url"))
        absolute_url = raw_url
        if raw_url.startswith("/"):
            absolute_url = f"{WORK_AT_A_STARTUP_BASE_URL}{raw_url}"

        return {
            "external_id": self._as_text(row.get("id")),
            "title": self._as_text(row.get("title")),
            "company": self._as_text(row.get("companyName")),
            "location": self._as_text(row.get("location")),
            "url": absolute_url,
            "posted_at": self._as_text(row.get("createdAt")),
            "description": self._as_text(row.get("prettyRole") or row.get("roleSpecificType") or row.get("type")),
        }

    def _as_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()


def _default_fetch_text(url: str) -> str:
    request = urllib_request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; jobharbor/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib_request.urlopen(request, timeout=15.0) as response:
        return response.read().decode("utf-8", errors="replace")


def _extract_balanced_json_array(text: str, start_index: int) -> tuple[str, int]:
    if start_index < 0 or start_index >= len(text) or text[start_index] != "[":
        return ("", start_index)

    depth = 0
    in_string = False
    escaped = False

    for idx in range(start_index, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "[":
            depth += 1
            continue
        if char == "]":
            depth -= 1
            if depth == 0:
                return (text[start_index : idx + 1], idx + 1)

    return ("", start_index)

