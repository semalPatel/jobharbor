from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session

from jobharbor.config import Settings
from jobharbor.db import get_engine, init_db
from jobharbor.observability.metrics import MetricsRecorder
from jobharbor.services.pipeline import PipelineCoordinator, STAGE_ORDER, StageHandler

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
            stages=_build_stage_handlers(),
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


def _build_stage_handlers() -> dict[str, StageHandler]:
    return {stage: _make_noop_stage(stage) for stage in STAGE_ORDER}


def _make_noop_stage(stage_name: str) -> StageHandler:
    def _stage(context: dict[str, Any]) -> None:
        history = context.setdefault("pipeline_history", [])
        history.append(stage_name)

    return _stage
