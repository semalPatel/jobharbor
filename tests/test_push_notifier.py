from typing import Any

from jobharbor.notifications.push import PushNotifier


class StubResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def test_push_notifier_sends_required_payload_fields() -> None:
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
