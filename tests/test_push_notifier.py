from typing import Any

import pytest

from jobharbor.notifications.push import PushNotifier


class StubResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def test_push_notifier_sends_required_payload_fields_including_message() -> None:
    captured: dict[str, Any] = {}

    def request(
        method: str,
        url: str,
        *,
        json: dict[str, str],
        timeout: float,
    ) -> StubResponse:
        captured["method"] = method
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return StubResponse(status_code=200)

    notifier = PushNotifier(
        api_token="token-123",
        user_key="user-456",
        request=request,
    )

    delivered = notifier.send(
        title="Review Ready",
        company="Acme",
        source="greenhouse",
        review_url="https://jobharbor.local/review/1",
    )

    assert delivered is True
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.pushover.net/1/messages.json"
    assert captured["timeout"] == 10.0
    assert captured["json"] == {
        "token": "token-123",
        "user": "user-456",
        "title": "Review Ready",
        "message": (
            "Review Ready\n"
            "company: Acme\n"
            "source: greenhouse\n"
            "review_url: https://jobharbor.local/review/1"
        ),
        "company": "Acme",
        "source": "greenhouse",
        "review_url": "https://jobharbor.local/review/1",
    }


def test_push_notifier_treats_non_2xx_as_delivery_failure() -> None:
    def request(
        method: str,
        url: str,
        *,
        json: dict[str, str],
        timeout: float,
    ) -> StubResponse:
        return StubResponse(status_code=503)

    notifier = PushNotifier(
        api_token="token-123",
        user_key="user-456",
        request=request,
    )

    delivered = notifier.send(
        title="Review Ready",
        company="Acme",
        source="greenhouse",
        review_url="https://jobharbor.local/review/1",
    )

    assert delivered is False


def test_push_notifier_returns_false_on_transport_exception() -> None:
    def request(
        method: str,
        url: str,
        *,
        json: dict[str, str],
        timeout: float,
    ) -> StubResponse:
        raise TimeoutError("network timeout")

    notifier = PushNotifier(
        api_token="token-123",
        user_key="user-456",
        request=request,
    )

    delivered = notifier.send(
        title="Review Ready",
        company="Acme",
        source="greenhouse",
        review_url="https://jobharbor.local/review/1",
    )

    assert delivered is False


@pytest.mark.parametrize(
    ("kwargs", "error_message"),
    [
        (
            {"api_token": "", "user_key": "user-456"},
            "api_token must be non-empty",
        ),
        (
            {"api_token": "token-123", "user_key": ""},
            "user_key must be non-empty",
        ),
        (
            {"api_token": "token-123", "user_key": "user-456", "endpoint": ""},
            "endpoint must be a non-empty http/https URL",
        ),
        (
            {
                "api_token": "token-123",
                "user_key": "user-456",
                "endpoint": "ftp://example.com/push",
            },
            "endpoint must be a non-empty http/https URL",
        ),
        (
            {
                "api_token": "token-123",
                "user_key": "user-456",
                "timeout_seconds": 0,
            },
            "timeout_seconds must be greater than 0",
        ),
    ],
)
def test_push_notifier_constructor_validation_raises_value_error(
    kwargs: dict[str, object],
    error_message: str,
) -> None:
    with pytest.raises(ValueError, match=error_message):
        PushNotifier(**kwargs)
