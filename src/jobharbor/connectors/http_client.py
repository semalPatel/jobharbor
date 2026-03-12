from collections.abc import Callable, Mapping
from typing import Any, Protocol


class HttpResponse(Protocol):
    def raise_for_status(self) -> None:
        ...

    def json(self) -> Any:
        ...


RequestCallable = Callable[..., HttpResponse]


class HttpClient:
    """Thin wrapper around a request callable for shared connector HTTP usage."""

    def __init__(self, request: RequestCallable, timeout: float = 10.0) -> None:
        self._request = request
        self._timeout = timeout

    def get_json(self, url: str, params: Mapping[str, str] | None = None) -> Any:
        response = self._request(
            "GET",
            url,
            params=dict(params) if params is not None else None,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()
