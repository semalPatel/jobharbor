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
