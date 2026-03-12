import json as jsonlib
from dataclasses import dataclass
from typing import Protocol
from urllib import parse as urllib_parse
from urllib import request as urllib_request


class PushResponse(Protocol):
    status_code: int


class PushRequestCallable(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, str],
        timeout: float,
    ) -> PushResponse:
        ...


@dataclass(frozen=True)
class _SimplePushResponse:
    status_code: int


def _default_push_request(
    method: str,
    url: str,
    *,
    json: dict[str, str],
    timeout: float,
) -> PushResponse:
    body = jsonlib.dumps(json).encode("utf-8")
    request = urllib_request.Request(
        url=url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", response.getcode())
    except urllib_request.HTTPError as exc:
        status_code = exc.code

    return _SimplePushResponse(status_code=int(status_code))


class PushNotifier:
    def __init__(
        self,
        *,
        api_token: str,
        user_key: str,
        endpoint: str = "https://api.pushover.net/1/messages.json",
        timeout_seconds: float = 10.0,
        request: PushRequestCallable | None = None,
    ) -> None:
        if not api_token.strip():
            raise ValueError("api_token must be non-empty")
        if not user_key.strip():
            raise ValueError("user_key must be non-empty")
        if not self._is_valid_http_url(endpoint):
            raise ValueError("endpoint must be a non-empty http/https URL")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")

        self._api_token = api_token
        self._user_key = user_key
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._request = request or _default_push_request

    @staticmethod
    def _is_valid_http_url(value: str) -> bool:
        text = value.strip()
        if not text:
            return False
        parsed = urllib_parse.urlparse(text)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _build_message(
        *,
        title: str,
        company: str,
        source: str,
        review_url: str,
    ) -> str:
        return (
            f"{title}\n"
            f"company: {company}\n"
            f"source: {source}\n"
            f"review_url: {review_url}"
        )

    def send(
        self,
        *,
        title: str,
        company: str,
        source: str,
        review_url: str,
    ) -> bool:
        payload = {
            "token": self._api_token,
            "user": self._user_key,
            "title": title,
            "message": self._build_message(
                title=title,
                company=company,
                source=source,
                review_url=review_url,
            ),
            "company": company,
            "source": source,
            "review_url": review_url,
        }

        try:
            response = self._request(
                "POST",
                self._endpoint,
                json=payload,
                timeout=self._timeout_seconds,
            )
        except (TimeoutError, ConnectionError, OSError):
            return False

        return 200 <= response.status_code < 300
