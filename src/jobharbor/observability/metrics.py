from threading import Lock


class MetricsRecorder:
    """In-memory counters for MVP observability signals."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = {
            "scan_runs": 0,
            "prep_success": 0,
            "prep_failure": 0,
            "notify_fallback": 0,
        }

    def increment_scan_runs(self) -> None:
        self._increment("scan_runs")

    def increment_prep_success(self) -> None:
        self._increment("prep_success")

    def increment_prep_failure(self) -> None:
        self._increment("prep_failure")

    def increment_notify_fallback(self) -> None:
        self._increment("notify_fallback")

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def _increment(self, key: str) -> None:
        with self._lock:
            self._counters[key] += 1
