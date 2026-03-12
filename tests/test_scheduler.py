from dataclasses import dataclass
from typing import Any, Callable

from jobharbor.scheduler import SCAN_JOB_ID, bootstrap_scheduler


@dataclass
class StubScheduler:
    jobs: dict[str, dict[str, Any]]

    def __init__(self) -> None:
        self.jobs = {}

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


def test_bootstrap_scheduler_registers_scan_job_only_once() -> None:
    scheduler = StubScheduler()

    def scan() -> None:
        return None

    bootstrap_scheduler(scan_job=scan, scheduler=scheduler)
    bootstrap_scheduler(scan_job=scan, scheduler=scheduler)

    assert len(scheduler.jobs) == 1
    assert SCAN_JOB_ID in scheduler.jobs
