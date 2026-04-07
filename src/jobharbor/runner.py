from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from sqlmodel import Session

from jobharbor.config import Settings
from jobharbor.db import get_engine, init_db
from jobharbor.notifications.email_fallback import EmailFallbackNotifier
from jobharbor.notifications.push import PushNotifier
from jobharbor.notifications.router import NotificationRouter
from jobharbor.observability.metrics import MetricsRecorder
from jobharbor.reports import EvaluationReportStageWorker
from jobharbor.services.pipeline import PipelineCoordinator, STAGE_ORDER, StageHandler
from jobharbor.workers.dedupe_stage import DedupeStageWorker
from jobharbor.workers.discover_stage import DiscoverStageWorker
from jobharbor.workers.notify_stage import NotifyStageWorker
from jobharbor.workers.normalize_stage import NormalizeStageWorker
from jobharbor.workers.prefill_stage import PrefillStageWorker
from jobharbor.workers.queue_stage import QueueStageWorker
from jobharbor.workers.review_stage import ReviewStageWorker
from jobharbor.workers.score_stage import ScoreStageWorker
from jobharbor.workspace import WorkspacePaths

_LOGGER = logging.getLogger(__name__)
_METRICS = MetricsRecorder()


def get_metrics_recorder() -> MetricsRecorder:
    return _METRICS


def run_scan_cycle(*, settings: Settings) -> None:
    """Run one deterministic scan-to-notify pass using the configured pipeline."""

    engine = get_engine(settings.database_url)
    init_db(engine=engine)

    with Session(engine) as session:
        coordinator = PipelineCoordinator(
            session=session,
            stages=_build_stage_handlers(session=session, settings=settings),
        )
        outcome = coordinator.run()

    _METRICS.increment_scan_runs()
    _LOGGER.info(
        "scan cycle completed",
        extra={
            "status": outcome.status.value,
            "failed_stage": outcome.failed_stage,
            "failure_classification": outcome.failure_classification,
        },
    )


def _build_stage_handlers(*, session: Session, settings: Settings) -> dict[str, StageHandler]:
    handlers = {stage: _make_noop_stage(stage) for stage in STAGE_ORDER}
    handlers["discover"] = _make_discover_stage(session=session, settings=settings)
    handlers["normalize"] = _make_normalize_stage()
    handlers["dedupe"] = _make_dedupe_stage()
    handlers["score"] = _make_score_stage(settings=settings)
    handlers["queue"] = _make_queue_stage(session=session)
    handlers["evaluate"] = _make_evaluate_stage(session=session, settings=settings)
    handlers["prefill"] = _make_prefill_stage(session=session)
    handlers["review"] = _make_review_stage()
    handlers["notify"] = _make_notify_stage(session=session, settings=settings)
    return handlers


def _make_discover_stage(*, session: Session, settings: Settings) -> StageHandler:
    worker = DiscoverStageWorker(session=session, settings=settings)

    def _stage(context: dict[str, Any]) -> None:
        worker.run(context)

    return _stage


def _make_normalize_stage() -> StageHandler:
    worker = NormalizeStageWorker()

    def _stage(context: dict[str, Any]) -> None:
        worker.run(context)

    return _stage


def _make_dedupe_stage() -> StageHandler:
    worker = DedupeStageWorker()

    def _stage(context: dict[str, Any]) -> None:
        worker.run(context)

    return _stage


def _make_score_stage(*, settings: Settings) -> StageHandler:
    worker = ScoreStageWorker(settings=settings)

    def _stage(context: dict[str, Any]) -> None:
        worker.run(context)

    return _stage


def _make_queue_stage(*, session: Session) -> StageHandler:
    worker = QueueStageWorker(session=session)

    def _stage(context: dict[str, Any]) -> None:
        worker.run(context)

    return _stage


def _make_evaluate_stage(*, session: Session, settings: Settings) -> StageHandler:
    worker = EvaluationReportStageWorker(
        session=session,
        reports_dir=WorkspacePaths.from_settings(settings).reports_dir,
    )

    def _stage(context: dict[str, Any]) -> None:
        worker.run(context)

    return _stage


def _make_prefill_stage(*, session: Session) -> StageHandler:
    profile_path = Path(os.getenv("JOBHARBOR_PROFILE_PATH", "profile.yaml"))
    worker = PrefillStageWorker(session=session, profile_path=profile_path)

    def _stage(context: dict[str, Any]) -> None:
        worker.run(context)

    return _stage


def _make_review_stage() -> StageHandler:
    worker = ReviewStageWorker()

    def _stage(context: dict[str, Any]) -> None:
        worker.run(context)

    return _stage


def _make_notify_stage(*, session: Session, settings: Settings) -> StageHandler:
    router = _build_notification_router(settings=settings)
    worker = NotifyStageWorker(session=session, notification_router=router)

    def _stage(context: dict[str, Any]) -> None:
        worker.run(context)

    return _stage


class _NoopNotifier:
    def send(
        self,
        *,
        title: str,
        company: str,
        source: str,
        review_url: str,
    ) -> bool:
        del title, company, source, review_url
        return False


def _build_notification_router(*, settings: Settings) -> NotificationRouter:
    noop = _NoopNotifier()
    email_notifier = _build_email_notifier(settings=settings) or noop
    push_notifier = _build_push_notifier(settings=settings) or noop

    if settings.notification_provider == "email":
        return NotificationRouter(
            push_notifier=email_notifier,
            email_fallback_notifier=noop,
        )
    return NotificationRouter(
        push_notifier=push_notifier,
        email_fallback_notifier=email_notifier,
    )


def _build_email_notifier(*, settings: Settings) -> EmailFallbackNotifier | None:
    if not (
        settings.smtp_host
        and settings.smtp_port
        and settings.smtp_user
        and settings.smtp_pass
        and settings.smtp_to
    ):
        return None
    return EmailFallbackNotifier(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user,
        smtp_pass=settings.smtp_pass,
        smtp_to=settings.smtp_to,
    )


def _build_push_notifier(*, settings: Settings) -> PushNotifier | None:
    if not (settings.pushover_api_token and settings.pushover_user_key):
        return None
    return PushNotifier(
        api_token=settings.pushover_api_token,
        user_key=settings.pushover_user_key,
    )


def _make_noop_stage(stage_name: str) -> StageHandler:
    def _stage(context: dict[str, Any]) -> None:
        history = context.setdefault("pipeline_history", [])
        history.append(stage_name)

    return _stage
