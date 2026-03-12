from email.message import EmailMessage
import smtplib
from typing import Protocol


class SmtpSendCallable(Protocol):
    def __call__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        recipient: str,
        subject: str,
        body: str,
        timeout_seconds: float,
    ) -> None:
        ...


def _default_smtp_send(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    recipient: str,
    subject: str,
    body: str,
    timeout_seconds: float,
) -> None:
    message = EmailMessage()
    message["From"] = username
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(host=host, port=port, timeout=timeout_seconds) as client:
        client.starttls()
        client.login(username, password)
        client.send_message(message)


class EmailFallbackNotifier:
    def __init__(
        self,
        *,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_pass: str,
        smtp_to: str,
        timeout_seconds: float = 10.0,
        sender: SmtpSendCallable | None = None,
    ) -> None:
        if not smtp_host.strip():
            raise ValueError("smtp_host must be non-empty")
        if smtp_port <= 0:
            raise ValueError("smtp_port must be greater than 0")
        if not smtp_user.strip():
            raise ValueError("smtp_user must be non-empty")
        if not smtp_pass.strip():
            raise ValueError("smtp_pass must be non-empty")
        if not smtp_to.strip():
            raise ValueError("smtp_to must be non-empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than 0")

        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_pass = smtp_pass
        self._smtp_to = smtp_to
        self._timeout_seconds = timeout_seconds
        self._sender = sender or _default_smtp_send

    def send(
        self,
        *,
        title: str,
        company: str,
        source: str,
        review_url: str,
    ) -> bool:
        title_text = title.strip()
        company_text = company.strip()
        source_text = source.strip()
        review_url_text = review_url.strip()
        if not title_text or not company_text or not source_text or not review_url_text:
            return False

        subject = f"Job review ready: {title_text}"
        body = (
            f"title: {title_text}\n"
            f"company: {company_text}\n"
            f"source: {source_text}\n"
            f"review_url: {review_url_text}"
        )

        try:
            self._sender(
                host=self._smtp_host,
                port=self._smtp_port,
                username=self._smtp_user,
                password=self._smtp_pass,
                recipient=self._smtp_to,
                subject=subject,
                body=body,
                timeout_seconds=self._timeout_seconds,
            )
        except Exception:
            return False

        return True
