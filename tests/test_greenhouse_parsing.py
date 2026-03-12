from collections.abc import Mapping
from typing import Any

from jobharbor.connectors.greenhouse import GreenhouseConnector


class StubHttpClient:
    def __init__(self, pages: Mapping[str, Any]) -> None:
        self._pages = dict(pages)
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    def get_json(self, url: str, params: Mapping[str, str] | None = None) -> Any:
        key = (params or {}).get("page", "1")
        self.calls.append((url, dict(params) if params is not None else None))
        return self._pages[key]


def test_greenhouse_fetch_jobs_normalizes_required_fields_and_ordering() -> None:
    client = StubHttpClient(
        {
            "1": {
                "jobs": [
                    {
                        "id": 22,
                        "title": "ML Engineer",
                        "company_name": "Acme",
                        "location": {"name": "Remote"},
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/22",
                        "updated_at": "2026-03-10T10:00:00Z",
                    },
                    {
                        "id": 1,
                        "title": "Backend Engineer",
                        "company_name": "Acme",
                        "location": {"name": "San Francisco, CA"},
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                        "updated_at": "2026-03-12T10:00:00Z",
                    },
                ]
            },
            "2": {
                "jobs": [
                    {
                        "id": 10,
                        "title": "Data Engineer",
                        "company_name": "Acme",
                        "location": {"name": "New York, NY"},
                        "absolute_url": "https://boards.greenhouse.io/acme/jobs/10",
                        "updated_at": "2026-03-11T10:00:00Z",
                    }
                ]
            },
            "3": {"jobs": []},
        }
    )

    connector = GreenhouseConnector(http_client=client, board_token="acme", page_size=2)

    jobs = connector.fetch_jobs()

    assert [job["external_id"] for job in jobs] == ["1", "10", "22"]
    assert jobs[0] == {
        "external_id": "1",
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "San Francisco, CA",
        "url": "https://boards.greenhouse.io/acme/jobs/1",
        "posted_at": "2026-03-12T10:00:00Z",
    }
    assert client.calls == [
        (
            "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            {"content": "true", "page": "1", "per_page": "2"},
        ),
        (
            "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            {"content": "true", "page": "2", "per_page": "2"},
        ),
        (
            "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
            {"content": "true", "page": "3", "per_page": "2"},
        ),
    ]


def test_greenhouse_normalization_handles_missing_or_empty_fields_safely() -> None:
    client = StubHttpClient(
        {
            "1": {
                "jobs": [
                    {
                        "id": None,
                        "title": None,
                        "company_name": None,
                        "location": None,
                        "absolute_url": None,
                        "updated_at": None,
                    }
                ]
            },
            "2": {"jobs": []},
        }
    )

    connector = GreenhouseConnector(http_client=client, board_token="acme", page_size=50)

    jobs = connector.fetch_jobs()

    assert jobs == [
        {
            "external_id": "",
            "title": "",
            "company": "",
            "location": "",
            "url": "",
            "posted_at": "",
        }
    ]
