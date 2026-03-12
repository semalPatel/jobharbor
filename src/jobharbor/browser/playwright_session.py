from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar
import time

DEFAULT_LAUNCH_TIMEOUT_MS = 30_000
DEFAULT_ACTION_TIMEOUT_MS = 10_000
DEFAULT_NAVIGATION_TIMEOUT_MS = 30_000
DEFAULT_RETRY_ATTEMPTS = 3


class ConfigurablePage(Protocol):
    def set_default_timeout(self, timeout_ms: int) -> None: ...

    def set_default_navigation_timeout(self, timeout_ms: int) -> None: ...


T = TypeVar("T")


class PlaywrightSession:
    def __init__(
        self,
        *,
        headless: bool = True,
        launch_timeout_ms: int = DEFAULT_LAUNCH_TIMEOUT_MS,
        action_timeout_ms: int = DEFAULT_ACTION_TIMEOUT_MS,
        navigation_timeout_ms: int = DEFAULT_NAVIGATION_TIMEOUT_MS,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if retry_attempts <= 0:
            raise ValueError("retry_attempts must be greater than 0")

        self.headless = headless
        self.launch_timeout_ms = launch_timeout_ms
        self.action_timeout_ms = action_timeout_ms
        self.navigation_timeout_ms = navigation_timeout_ms
        self.retry_attempts = retry_attempts
        self._sleep = sleep

    def launch_kwargs(self) -> dict[str, bool | int]:
        return {
            "headless": self.headless,
            "timeout": self.launch_timeout_ms,
        }

    def configure_page(self, page: ConfigurablePage) -> None:
        page.set_default_timeout(self.action_timeout_ms)
        page.set_default_navigation_timeout(self.navigation_timeout_ms)

    def run_with_retries(
        self,
        operation: Callable[[], T],
        *,
        attempts: int | None = None,
        retry_exceptions: tuple[type[BaseException], ...],
        retry_delay_seconds: float = 0.0,
    ) -> T:
        max_attempts = attempts if attempts is not None else self.retry_attempts
        if max_attempts <= 0:
            raise ValueError("attempts must be greater than 0")

        for attempt in range(1, max_attempts + 1):
            try:
                return operation()
            except retry_exceptions:
                if attempt >= max_attempts:
                    raise
                if retry_delay_seconds > 0:
                    self._sleep(retry_delay_seconds)

        raise RuntimeError("unreachable")
