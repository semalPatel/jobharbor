from collections.abc import Mapping
from typing import Any, Protocol


class HttpResponse(Protocol):
    def raise_for_status(self) -> None:
        ...

    def json(self) -> Any:
        ...


class RequestCallable(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HttpResponse:
        ...


class HttpClientError(Exception):
    def __init__(self, method: str, url: str, cause: Exception) -> None:
        self.method = method
        self.url = url
        super().__init__(f"HTTP client failed for {method} {url}: {cause}")


class HttpClient:
    """Thin wrapper around a request callable for shared connector HTTP usage."""

    def __init__(self, request: RequestCallable, timeout: float = 10.0) -> None:
        self._request = request
        self._timeout = timeout

    def get_json(self, url: str, params: Mapping[str, str] | None = None) -> Any:
        method = "GET"
        try:
            response = self._request(
                method,
                url,
                params=dict(params) if params is not None else None,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # pragma: no cover - exercised by tests
            raise HttpClientError(method=method, url=url, cause=exc) from exc
