from collections.abc import Mapping
from typing import Any

from jobharbor.connectors.lever import LeverConnector


class StubHttpClient:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = dict(payload)
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def get_json(self, url: str, params: Mapping[str, str] | None = None) -> Any:
        self.calls.append((url, dict(params) if params is not None else None))
        return self._payload


def test_lever_fetch_jobs_normalizes_required_fields_and_ordering() -> None:
    client = StubHttpClient(
        {
            "postings": [
                {
                    "id": "lever-2",
                    "text": "Backend Engineer",
                    "categories": {"location": "Remote", "team": "Platform"},
                    "hostedUrl": "https://jobs.lever.co/acme/lever-2",
                    "createdAt": 1710172800000,
                    "company": "Acme",
                },
                {
                    "id": "lever-1",
                    "text": "ML Engineer",
                    "categories": {"location": "San Francisco, CA"},
                    "hostedUrl": "https://jobs.lever.co/acme/lever-1",
                    "createdAt": 1710086400000,
                    "company": "Acme",
                    "descriptionPlain": "Build mobile features",
                },
            ]
        }
    )

    connector = LeverConnector(http_client=client, company_slug="acme")

    jobs = connector.fetch_jobs()

    assert [job["external_id"] for job in jobs] == ["lever-1", "lever-2"]
    assert jobs[0] == {
        "external_id": "lever-1",
        "title": "ML Engineer",
        "company": "Acme",
        "location": "San Francisco, CA",
        "url": "https://jobs.lever.co/acme/lever-1",
        "posted_at": "1710086400000",
        "description": "Build mobile features",
    }
    assert client.calls == [
        (
            "https://api.lever.co/v0/postings/acme",
            {"mode": "json"},
        )
    ]


def test_lever_fetch_jobs_handles_invalid_payload_shapes() -> None:
    client = StubHttpClient({"postings": "bad-shape"})
    connector = LeverConnector(http_client=client, company_slug="acme")

    jobs = connector.fetch_jobs()

    assert jobs == []
