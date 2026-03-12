from dataclasses import dataclass
from typing import Any, Callable

import pytest

from jobharbor.scheduler import SCAN_JOB_ID, bootstrap_scheduler


@dataclass
class StubScheduler:
    jobs: dict[str, dict[str, Any]]
    add_job_calls: list[dict[str, Any]]

    def __init__(self) -> None:
        self.jobs = {}
        self.add_job_calls = []

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self.jobs.get(job_id)

    def add_job(
        self,
        func: Callable[[], None],
        trigger: str,
        *,
        id: str,
        hours: int,
        replace_existing: bool,
    ) -> None:
        self.add_job_calls.append(
            {
                "id": id,
                "hours": hours,
                "replace_existing": replace_existing,
            }
        )
        self.jobs[id] = {
            "func": func,
            "trigger": trigger,
            "hours": hours,
            "replace_existing": replace_existing,
        }


def test_bootstrap_scheduler_defaults_to_6_hour_interval() -> None:
    scheduler = StubScheduler()

    def scan() -> None:
        return None

    bootstrap_scheduler(scan_job=scan, scheduler=scheduler)

    job = scheduler.get_job(SCAN_JOB_ID)
    assert job is not None
    assert job["trigger"] == "interval"
    assert job["hours"] == 6


def test_bootstrap_scheduler_registers_scan_job_only_once_when_interval_unchanged() -> None:
    scheduler = StubScheduler()

    def scan() -> None:
        return None

    bootstrap_scheduler(scan_job=scan, scheduler=scheduler)
    bootstrap_scheduler(scan_job=scan, scheduler=scheduler)

    assert len(scheduler.jobs) == 1
    assert SCAN_JOB_ID in scheduler.jobs
    assert len(scheduler.add_job_calls) == 1


def test_bootstrap_scheduler_raises_value_error_for_non_positive_interval() -> None:
    scheduler = StubScheduler()

    def scan() -> None:
        return None

    with pytest.raises(ValueError, match="interval_hours must be greater than 0"):
        bootstrap_scheduler(scan_job=scan, scheduler=scheduler, interval_hours=0)

    with pytest.raises(ValueError, match="interval_hours must be greater than 0"):
        bootstrap_scheduler(scan_job=scan, scheduler=scheduler, interval_hours=-1)


def test_bootstrap_scheduler_updates_existing_job_when_interval_drifts() -> None:
    scheduler = StubScheduler()

    def scan() -> None:
        return None

    bootstrap_scheduler(scan_job=scan, scheduler=scheduler, interval_hours=6)
    bootstrap_scheduler(scan_job=scan, scheduler=scheduler, interval_hours=12)

    assert len(scheduler.jobs) == 1
    assert SCAN_JOB_ID in scheduler.jobs
    assert scheduler.jobs[SCAN_JOB_ID]["hours"] == 12
    assert len(scheduler.add_job_calls) == 2
    assert scheduler.add_job_calls[0]["replace_existing"] is False
    assert scheduler.add_job_calls[1]["replace_existing"] is True
