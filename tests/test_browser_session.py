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


@pytest.mark.parametrize(
    ("kwargs", "field_name"),
    [
        ({"launch_timeout_ms": 0}, "launch_timeout_ms"),
        ({"launch_timeout_ms": -1}, "launch_timeout_ms"),
        ({"action_timeout_ms": 0}, "action_timeout_ms"),
        ({"action_timeout_ms": -1}, "action_timeout_ms"),
        ({"navigation_timeout_ms": 0}, "navigation_timeout_ms"),
        ({"navigation_timeout_ms": -1}, "navigation_timeout_ms"),
    ],
)
def test_constructor_rejects_non_positive_timeout_values(
    kwargs: dict[str, int],
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        PlaywrightSession(**kwargs)


def test_retry_helper_sleeps_attempts_minus_one_times_when_delay_enabled() -> None:
    sleep_calls: list[float] = []
    session = PlaywrightSession(sleep=sleep_calls.append)
    attempts = 0

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 4:
            raise RuntimeError("transient")
        return "ok"

    result = session.run_with_retries(
        flaky,
        attempts=4,
        retry_exceptions=(RuntimeError,),
        retry_delay_seconds=0.25,
    )

    assert result == "ok"
    assert attempts == 4
    assert sleep_calls == [0.25, 0.25, 0.25]


def test_retry_helper_non_retry_exception_propagates_without_retries_or_sleep() -> None:
    sleep_calls: list[float] = []
    session = PlaywrightSession(sleep=sleep_calls.append)
    attempts = 0

    def fail_non_retry() -> None:
        nonlocal attempts
        attempts += 1
        raise ValueError("fatal")

    with pytest.raises(ValueError, match="fatal"):
        session.run_with_retries(
            fail_non_retry,
            attempts=5,
            retry_exceptions=(RuntimeError,),
            retry_delay_seconds=0.5,
        )

    assert attempts == 1
    assert sleep_calls == []


def test_retry_helper_exponential_backoff_progression() -> None:
    sleep_calls: list[float] = []
    session = PlaywrightSession(sleep=sleep_calls.append)
    attempts = 0

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 4:
            raise RuntimeError("transient")
        return "ok"

    result = session.run_with_retries(
        flaky,
        attempts=4,
        retry_exceptions=(RuntimeError,),
        retry_delay_seconds=0.1,
        exponential_backoff=True,
    )

    assert result == "ok"
    assert sleep_calls == [0.1, 0.2, 0.4]


def test_retry_helper_custom_backoff_hook_overrides_default_progression() -> None:
    sleep_calls: list[float] = []
    session = PlaywrightSession(sleep=sleep_calls.append)
    attempts = 0

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 4:
            raise RuntimeError("transient")
        return "ok"

    def hook(retry_index: int, base_delay: float) -> float:
        return base_delay * retry_index * 3

    result = session.run_with_retries(
        flaky,
        attempts=4,
        retry_exceptions=(RuntimeError,),
        retry_delay_seconds=0.1,
        backoff_strategy=hook,
    )

    assert result == "ok"
    assert sleep_calls == pytest.approx([0.3, 0.6, 0.9])
