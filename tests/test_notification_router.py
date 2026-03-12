from dataclasses import dataclass, field

from jobharbor.notifications.router import NotificationRouter


@dataclass
class StubPushNotifier:
    should_deliver: bool
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
        return self.should_deliver


@dataclass
class StubEmailFallbackNotifier:
    should_deliver: bool = True
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
    assert email.calls[0]["title"] == "Review Ready"


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
