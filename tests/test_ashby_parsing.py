from collections.abc import Mapping
from typing import Any

from jobharbor.connectors.ashby import AshbyConnector


class StubHttpClient:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = dict(payload)
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def get_json(self, url: str, params: Mapping[str, str] | None = None) -> Any:
        self.calls.append((url, dict(params) if params is not None else None))
        return self._payload


def test_ashby_fetch_jobs_normalizes_required_fields_and_ordering() -> None:
    client = StubHttpClient(
        {
            "jobs": [
                {
                    "id": "ashby-2",
                    "title": "Backend Engineer",
                    "team": {"name": "Acme"},
                    "location": {"name": "Remote - US"},
                    "jobUrl": "https://jobs.ashbyhq.com/acme/ashby-2",
                    "publishedAt": "2026-03-11T09:00:00Z",
                },
                {
                    "id": "ashby-1",
                    "title": "ML Engineer",
                    "team": {"name": "Acme"},
                    "location": "San Francisco, CA",
                    "applyUrl": "https://jobs.ashbyhq.com/acme/ashby-1",
                    "createdAt": "2026-03-10T09:00:00Z",
                },
            ]
        }
    )

    connector = AshbyConnector(http_client=client, organization_slug="acme")

    jobs = connector.fetch_jobs()

    assert [job["external_id"] for job in jobs] == ["ashby-1", "ashby-2"]
    assert jobs[0] == {
        "external_id": "ashby-1",
        "title": "ML Engineer",
        "company": "Acme",
        "location": "San Francisco, CA",
        "url": "https://jobs.ashbyhq.com/acme/ashby-1",
        "posted_at": "2026-03-10T09:00:00Z",
    }
    assert client.calls == [
        (
            "https://api.ashbyhq.com/posting-api/job-board/acme",
            {"includeCompensation": "true"},
        )
    ]


def test_ashby_fetch_jobs_handles_invalid_payload_shapes() -> None:
    client = StubHttpClient({"jobs": "bad-shape"})
    connector = AshbyConnector(http_client=client, organization_slug="acme")

    jobs = connector.fetch_jobs()

    assert jobs == []
