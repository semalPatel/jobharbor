from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from jobharbor.api.review import router as review_router
from jobharbor.config import Settings
from jobharbor.db import init_db
from jobharbor.runner import run_scan_cycle
from jobharbor.scheduler import bootstrap_scheduler

app = FastAPI()
app.include_router(review_router)

_scheduler: BackgroundScheduler | None = None


@app.on_event("startup")
def _ensure_scheduler_started() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    init_db()
    settings = Settings()

    def _scan_job() -> None:
        run_scan_cycle(settings=settings)

    scheduler = bootstrap_scheduler(
        scan_job=_scan_job,
        interval_hours=settings.scan_interval_hours,
    )
    scheduler.start()
    _scheduler = scheduler

    _scan_job()


@app.on_event("shutdown")
def _stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None


@app.get('/health')
def health() -> dict[str, bool]:
    return {'ok': True}
