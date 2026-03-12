from collections.abc import Sequence
from typing import Any

import pytest

from jobharbor.connectors.base import JobConnector, validate_jobs_payload
from jobharbor.connectors.http_client import HttpClient, HttpClientError, HttpResponse


class StubResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class StatusErrorResponse:
    def raise_for_status(self) -> None:
        raise RuntimeError("bad status")

    def json(self) -> dict[str, Any]:
        return {"jobs": []}


class JsonErrorResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        raise ValueError("invalid json")


class ValidConnector:
    def fetch_jobs(self) -> Sequence[dict[str, Any]]:
        return [{"external_id": "1"}]


class InvalidPayloadConnector:
    def fetch_jobs(self) -> Sequence[Any]:
        return ["not-a-dict"]


def use_connector(connector: JobConnector) -> Sequence[dict[str, Any]]:
    return connector.fetch_jobs()


def test_job_connector_protocol_fetches_jobs_without_runtime_isinstance_check() -> None:
    rows = use_connector(ValidConnector())

    assert rows == [{"external_id": "1"}]


def test_validate_jobs_payload_rejects_non_dict_entries() -> None:
    connector = InvalidPayloadConnector()

    with pytest.raises(TypeError):
        validate_jobs_payload(connector.fetch_jobs())


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


def test_http_client_wraps_request_exceptions_with_context() -> None:
    def request(
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HttpResponse:
        raise TimeoutError("network timeout")

    client = HttpClient(request=request)

    with pytest.raises(HttpClientError) as exc_info:
        client.get_json("https://example.test/jobs")

    error = exc_info.value
    assert error.method == "GET"
    assert error.url == "https://example.test/jobs"
    assert isinstance(error.__cause__, TimeoutError)


def test_http_client_wraps_status_exceptions_with_context() -> None:
    def request(
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HttpResponse:
        return StatusErrorResponse()

    client = HttpClient(request=request)

    with pytest.raises(HttpClientError) as exc_info:
        client.get_json("https://example.test/jobs")

    error = exc_info.value
    assert error.method == "GET"
    assert error.url == "https://example.test/jobs"
    assert isinstance(error.__cause__, RuntimeError)


def test_http_client_wraps_json_exceptions_with_context() -> None:
    def request(
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HttpResponse:
        return JsonErrorResponse()

    client = HttpClient(request=request)

    with pytest.raises(HttpClientError) as exc_info:
        client.get_json("https://example.test/jobs")

    error = exc_info.value
    assert error.method == "GET"
    assert error.url == "https://example.test/jobs"
    assert isinstance(error.__cause__, ValueError)
