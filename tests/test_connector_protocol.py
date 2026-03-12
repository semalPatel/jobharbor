from typing import Any

from jobharbor.connectors.base import JobConnector
from jobharbor.connectors.http_client import HttpClient, HttpResponse


class StubResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class ValidConnector:
    def fetch_jobs(self) -> list[dict[str, str]]:
        return [{"external_id": "1"}]


class MissingFetch:
    pass


def test_job_connector_protocol_requires_fetch_jobs() -> None:
    connector: JobConnector = ValidConnector()

    assert connector.fetch_jobs() == [{"external_id": "1"}]
    assert isinstance(ValidConnector(), JobConnector)
    assert not isinstance(MissingFetch(), JobConnector)


def test_http_client_get_json_delegates_request() -> None:
    captured: dict[str, Any] = {}

    def request(
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HttpResponse:
        captured["method"] = method
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return StubResponse({"jobs": []})

    client = HttpClient(request=request, timeout=3.5)

    payload = client.get_json("https://example.test/jobs", params={"page": "1"})

    assert payload == {"jobs": []}
    assert captured == {
        "method": "GET",
        "url": "https://example.test/jobs",
        "params": {"page": "1"},
        "timeout": 3.5,
    }
