from typing import Protocol


class PushNotifierProtocol(Protocol):
    def send(
        self,
        *,
        title: str,
        company: str,
        source: str,
        review_url: str,
    ) -> bool:
        ...


class EmailFallbackNotifierProtocol(Protocol):
    def send(
        self,
        *,
        title: str,
        company: str,
        source: str,
        review_url: str,
    ) -> bool:
        ...


class NotificationRouter:
    def __init__(
        self,
        *,
        push_notifier: PushNotifierProtocol,
        email_fallback_notifier: EmailFallbackNotifierProtocol,
    ) -> None:
        self._push_notifier = push_notifier
        self._email_fallback_notifier = email_fallback_notifier

    def send(
        self,
        *,
        title: str,
        company: str,
        source: str,
        review_url: str,
    ) -> bool:
        try:
            push_delivered = self._push_notifier.send(
                title=title,
                company=company,
                source=source,
                review_url=review_url,
            )
        except Exception:
            push_delivered = False
        if push_delivered:
            return True

        try:
            return self._email_fallback_notifier.send(
                title=title,
                company=company,
                source=source,
                review_url=review_url,
            )
        except Exception:
            return False
