from collections.abc import Mapping
from typing import Any

from jobharbor.connectors.smartrecruiters import SmartRecruitersConnector


class StubHttpClient:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = dict(payload)
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def get_json(self, url: str, params: Mapping[str, str] | None = None) -> Any:
        self.calls.append((url, dict(params) if params is not None else None))
        return self._payload


def test_smartrecruiters_fetch_jobs_normalizes_required_fields_and_ordering() -> None:
    client = StubHttpClient(
        {
            "content": [
                {
                    "id": "7440002",
                    "name": "Android Engineer",
                    "location": {"city": "San Francisco", "country": "United States"},
                    "ref": "https://jobs.smartrecruiters.com/acme/7440002-android-engineer",
                    "releasedDate": "2026-03-18T10:00:00Z",
                    "company": {"name": "Acme"},
                },
                {
                    "id": "7440001",
                    "name": "iOS Engineer",
                    "location": {"city": "Remote", "country": "United States"},
                    "ref": "https://jobs.smartrecruiters.com/acme/7440001-ios-engineer",
                    "releasedDate": "2026-03-17T10:00:00Z",
                    "company": {"name": "Acme"},
                },
            ]
        }
    )

    connector = SmartRecruitersConnector(http_client=client, company_slug="acme")
    jobs = connector.fetch_jobs()

    assert [job["external_id"] for job in jobs] == ["7440001", "7440002"]
    assert jobs[0] == {
        "external_id": "7440001",
        "title": "iOS Engineer",
        "company": "Acme",
        "location": "Remote, United States",
        "url": "https://jobs.smartrecruiters.com/acme/7440001-ios-engineer",
        "posted_at": "2026-03-17T10:00:00Z",
    }
    assert client.calls == [
        (
            "https://api.smartrecruiters.com/v1/companies/acme/postings",
            {"limit": "100"},
        )
    ]


def test_smartrecruiters_fetch_jobs_handles_invalid_payload_shapes() -> None:
    client = StubHttpClient({"content": "bad-shape"})
    connector = SmartRecruitersConnector(http_client=client, company_slug="acme")

    jobs = connector.fetch_jobs()
    assert jobs == []

