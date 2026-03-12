from datetime import datetime, timezone

import pytest

from jobharbor.observability.logging import build_log_record
from jobharbor.observability.metrics import MetricsRecorder


def test_metrics_increment_for_scan_prep_and_notify_fallback() -> None:
    metrics = MetricsRecorder()

    metrics.increment_scan_runs()
    metrics.increment_prep_success()
    metrics.increment_prep_failure()
    metrics.increment_notify_fallback()

    assert metrics.snapshot() == {
        "scan_runs": 1,
        "prep_success": 1,
        "prep_failure": 1,
        "notify_fallback": 1,
    }


def test_metrics_snapshot_returns_copy() -> None:
    metrics = MetricsRecorder()
    metrics.increment_scan_runs()

    snapshot = metrics.snapshot()
    snapshot["scan_runs"] = 0

    assert metrics.snapshot()["scan_runs"] == 1


def test_build_log_record_produces_structured_payload() -> None:
    ts = datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc)

    record = build_log_record(
        event="pipeline.stage.complete",
        level="INFO",
        timestamp=ts,
        stage="discover",
        source="greenhouse",
    )

    assert record == {
        "timestamp": "2026-03-12T18:00:00+00:00",
        "level": "INFO",
        "event": "pipeline.stage.complete",
        "stage": "discover",
        "source": "greenhouse",
    }


@pytest.mark.parametrize(
    ("event", "level", "error_message"),
    [
        ("", "INFO", "event must be non-empty"),
        ("pipeline.start", "", "level must be non-empty"),
    ],
)
def test_build_log_record_validates_required_fields(
    event: str,
    level: str,
    error_message: str,
) -> None:
    with pytest.raises(ValueError, match=error_message):
        build_log_record(event=event, level=level)
