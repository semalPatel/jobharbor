from dataclasses import dataclass, field
from typing import Any

import pytest

from jobharbor.notifications.email_fallback import EmailFallbackNotifier
from jobharbor.notifications.router import NotificationRouter


@dataclass
class StubPushNotifier:
    should_deliver: bool = True
    raises: bool = False
    calls: list[dict[str, str]] = field(default_factory=list)

    def send(
        self,
        *,
        title: str,
        company: str,
        source: str,
        review_url: str,
    ) -> bool:
        self.calls.append(
            {
                "title": title,
                "company": company,
                "source": source,
                "review_url": review_url,
            }
        )
        if self.raises:
            raise RuntimeError("push transport failed")
        return self.should_deliver


@dataclass
class StubEmailFallbackNotifier:
    should_deliver: bool = True
    raises: bool = False
    calls: list[dict[str, str]] = field(default_factory=list)

    def send(
        self,
        *,
        title: str,
        company: str,
        source: str,
        review_url: str,
    ) -> bool:
        self.calls.append(
            {
                "title": title,
                "company": company,
                "source": source,
                "review_url": review_url,
            }
        )
        if self.raises:
            raise RuntimeError("smtp down")
        return self.should_deliver


def test_notification_router_uses_email_fallback_when_push_fails() -> None:
    push = StubPushNotifier(should_deliver=False)
    email = StubEmailFallbackNotifier()
    router = NotificationRouter(push_notifier=push, email_fallback_notifier=email)

    delivered = router.send(
        title="Review Ready",
        company="Acme",
        source="greenhouse",
        review_url="https://jobharbor.local/review/1",
    )

    assert delivered is True
    assert len(push.calls) == 1
    assert len(email.calls) == 1


def test_notification_router_skips_email_fallback_when_push_succeeds() -> None:
    push = StubPushNotifier(should_deliver=True)
    email = StubEmailFallbackNotifier()
    router = NotificationRouter(push_notifier=push, email_fallback_notifier=email)

    delivered = router.send(
        title="Review Ready",
        company="Acme",
        source="greenhouse",
        review_url="https://jobharbor.local/review/1",
    )

    assert delivered is True
    assert len(push.calls) == 1
    assert email.calls == []


def test_notification_router_attempts_email_fallback_when_push_raises() -> None:
    push = StubPushNotifier(raises=True)
    email = StubEmailFallbackNotifier(should_deliver=True)
    router = NotificationRouter(push_notifier=push, email_fallback_notifier=email)

    delivered = router.send(
        title="Review Ready",
        company="Acme",
        source="greenhouse",
        review_url="https://jobharbor.local/review/1",
    )

    assert delivered is True
    assert len(push.calls) == 1
    assert len(email.calls) == 1


def test_notification_router_returns_false_when_fallback_returns_false() -> None:
    push = StubPushNotifier(should_deliver=False)
    email = StubEmailFallbackNotifier(should_deliver=False)
    router = NotificationRouter(push_notifier=push, email_fallback_notifier=email)

    delivered = router.send(
        title="Review Ready",
        company="Acme",
        source="greenhouse",
        review_url="https://jobharbor.local/review/1",
    )

    assert delivered is False


def test_notification_router_returns_false_when_fallback_raises() -> None:
    push = StubPushNotifier(should_deliver=False)
    email = StubEmailFallbackNotifier(raises=True)
    router = NotificationRouter(push_notifier=push, email_fallback_notifier=email)

    delivered = router.send(
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
            {
                "smtp_host": "   ",
                "smtp_port": 587,
                "smtp_user": "sender@example.com",
                "smtp_pass": "pw",
                "smtp_to": "recipient@example.com",
            },
            "smtp_host must be non-empty",
        ),
        (
            {
                "smtp_host": "smtp.example.com",
                "smtp_port": 0,
                "smtp_user": "sender@example.com",
                "smtp_pass": "pw",
                "smtp_to": "recipient@example.com",
            },
            "smtp_port must be greater than 0",
        ),
        (
            {
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "   ",
                "smtp_pass": "pw",
                "smtp_to": "recipient@example.com",
            },
            "smtp_user must be non-empty",
        ),
        (
            {
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "sender@example.com",
                "smtp_pass": "   ",
                "smtp_to": "recipient@example.com",
            },
            "smtp_pass must be non-empty",
        ),
        (
            {
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "sender@example.com",
                "smtp_pass": "pw",
                "smtp_to": "   ",
            },
            "smtp_to must be non-empty",
        ),
    ],
)
def test_email_fallback_notifier_constructor_validation(
    kwargs: dict[str, Any],
    error_message: str,
) -> None:
    with pytest.raises(ValueError, match=error_message):
        EmailFallbackNotifier(**kwargs)


@pytest.mark.parametrize("field_name", ["title", "company", "source", "review_url"])
def test_email_fallback_notifier_returns_false_for_blank_send_inputs(
    field_name: str,
) -> None:
    captured: dict[str, Any] = {}

    def sender(**kwargs: Any) -> None:
        captured.update(kwargs)

    notifier = EmailFallbackNotifier(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="sender@example.com",
        smtp_pass="pw",
        smtp_to="recipient@example.com",
        sender=sender,
    )

    payload = {
        "title": "Review Ready",
        "company": "Acme",
        "source": "greenhouse",
        "review_url": "https://jobharbor.local/review/1",
    }
    payload[field_name] = "   "

    delivered = notifier.send(**payload)

    assert delivered is False
    assert captured == {}


def test_email_fallback_notifier_returns_false_when_sender_raises_any_exception() -> None:
    def sender(**kwargs: Any) -> None:
        raise ValueError("unexpected formatter error")

    notifier = EmailFallbackNotifier(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="sender@example.com",
        smtp_pass="pw",
        smtp_to="recipient@example.com",
        sender=sender,
    )

    delivered = notifier.send(
        title="Review Ready",
        company="Acme",
        source="greenhouse",
        review_url="https://jobharbor.local/review/1",
    )

    assert delivered is False
