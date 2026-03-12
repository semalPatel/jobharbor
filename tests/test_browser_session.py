import pytest

from jobharbor.browser.playwright_session import (
    DEFAULT_ACTION_TIMEOUT_MS,
    DEFAULT_LAUNCH_TIMEOUT_MS,
    DEFAULT_NAVIGATION_TIMEOUT_MS,
    PlaywrightSession,
)


class StubPage:
    def __init__(self) -> None:
        self.default_timeout_ms: int | None = None
        self.default_navigation_timeout_ms: int | None = None

    def set_default_timeout(self, timeout_ms: int) -> None:
        self.default_timeout_ms = timeout_ms

    def set_default_navigation_timeout(self, timeout_ms: int) -> None:
        self.default_navigation_timeout_ms = timeout_ms


def test_launch_kwargs_use_default_headless_and_timeout() -> None:
    session = PlaywrightSession()

    assert session.launch_kwargs() == {
        "headless": True,
        "timeout": DEFAULT_LAUNCH_TIMEOUT_MS,
    }


def test_launch_kwargs_support_headed_mode() -> None:
    session = PlaywrightSession(headless=False, launch_timeout_ms=15000)

    assert session.launch_kwargs() == {
        "headless": False,
        "timeout": 15000,
    }


def test_configure_page_applies_default_timeouts() -> None:
    session = PlaywrightSession(
        action_timeout_ms=2222,
        navigation_timeout_ms=3333,
    )
    page = StubPage()

    session.configure_page(page)

    assert page.default_timeout_ms == 2222
    assert page.default_navigation_timeout_ms == 3333


def test_retry_helper_retries_then_succeeds() -> None:
    session = PlaywrightSession()
    attempts = 0

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("transient")
        return "ok"

    result = session.run_with_retries(
        flaky,
        attempts=3,
        retry_exceptions=(RuntimeError,),
    )

    assert result == "ok"
    assert attempts == 3


def test_retry_helper_raises_after_attempt_limit() -> None:
    session = PlaywrightSession()

    def always_fail() -> None:
        raise TimeoutError("still broken")

    with pytest.raises(TimeoutError, match="still broken"):
        session.run_with_retries(
            always_fail,
            attempts=2,
            retry_exceptions=(TimeoutError,),
        )


def test_retry_helper_uses_default_attempt_count() -> None:
    session = PlaywrightSession()
    attempts = 0

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < session.retry_attempts:
            raise RuntimeError("try again")
        return "done"

    assert session.retry_attempts == 3
    assert session.run_with_retries(flaky, retry_exceptions=(RuntimeError,)) == "done"
    assert attempts == 3


def test_default_timeout_constants_are_stable() -> None:
    assert DEFAULT_LAUNCH_TIMEOUT_MS == 30_000
    assert DEFAULT_ACTION_TIMEOUT_MS == 10_000
    assert DEFAULT_NAVIGATION_TIMEOUT_MS == 30_000
