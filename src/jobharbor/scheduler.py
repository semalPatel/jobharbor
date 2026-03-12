from collections.abc import Callable
from typing import Any, Protocol

SCAN_JOB_ID = "scan-job"


class SchedulerProtocol(Protocol):
    def get_job(self, job_id: str) -> Any | None:
        ...

    def add_job(
        self,
        func: Callable[[], None],
        trigger: str,
        *,
        id: str,
        hours: int,
        replace_existing: bool,
    ) -> Any:
        ...


try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ModuleNotFoundError:  # pragma: no cover - exercised only when dependency missing
    BackgroundScheduler = None


def _create_scheduler() -> SchedulerProtocol:
    if BackgroundScheduler is None:
        raise RuntimeError("APScheduler is required to create a default scheduler instance")
    return BackgroundScheduler()


def _get_job_interval_hours(job: Any) -> int | None:
    if isinstance(job, dict):
        hours = job.get("hours")
        return hours if isinstance(hours, int) else None

    trigger = getattr(job, "trigger", None)
    interval = getattr(trigger, "interval", None)
    if interval is not None and hasattr(interval, "total_seconds"):
        total_seconds = interval.total_seconds()
        if total_seconds % 3600 == 0:
            return int(total_seconds // 3600)

    return None


def bootstrap_scheduler(
    *,
    scan_job: Callable[[], None],
    scheduler: SchedulerProtocol | None = None,
    interval_hours: int = 6,
) -> SchedulerProtocol:
    if interval_hours <= 0:
        raise ValueError("interval_hours must be greater than 0")

    active_scheduler = scheduler or _create_scheduler()

    existing_job = active_scheduler.get_job(SCAN_JOB_ID)
    if existing_job is None:
        active_scheduler.add_job(
            scan_job,
            "interval",
            id=SCAN_JOB_ID,
            hours=interval_hours,
            replace_existing=False,
        )
        return active_scheduler

    if _get_job_interval_hours(existing_job) != interval_hours:
        active_scheduler.add_job(
            scan_job,
            "interval",
            id=SCAN_JOB_ID,
            hours=interval_hours,
            replace_existing=True,
        )

    return active_scheduler
