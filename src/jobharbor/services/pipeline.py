from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from jobharbor.models import RunLog, RunStatus

STAGE_ORDER: tuple[str, ...] = (
    "discover",
    "normalize",
    "dedupe",
    "score",
    "queue",
    "evaluate",
    "prefill",
    "review",
    "notify",
)

StageHandler = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class PipelineRunOutcome:
    status: RunStatus
    failed_stage: str | None
    failure_classification: str | None


class PipelineCoordinator:
    """Executes scan-to-notify stages in deterministic order and persists run outcomes."""

    def __init__(self, *, session: Session, stages: Mapping[str, StageHandler]) -> None:
        self._session = session
        self._stages = dict(stages)
        self._validate_stage_set()

    def run(self) -> PipelineRunOutcome:
        context: dict[str, Any] = {}
        completed_stages = 0

        for stage_name in STAGE_ORDER:
            handler = self._stages[stage_name]
            try:
                handler(context)
            except Exception as exc:
                classification = classify_pipeline_failure(exc)
                self._persist_run_log(
                    source=f"pipeline:{stage_name}",
                    status=RunStatus.failed,
                    message=(
                        f"stage={stage_name} classification={classification} "
                        f"error_type={type(exc).__name__} error={exc}"
                    ),
                )
                pipeline_status = (
                    RunStatus.failed if completed_stages == 0 else RunStatus.partial_failure
                )
                self._persist_run_log(
                    source="pipeline",
                    status=pipeline_status,
                    message=f"pipeline halted at stage {stage_name}",
                )
                return PipelineRunOutcome(
                    status=pipeline_status,
                    failed_stage=stage_name,
                    failure_classification=classification,
                )

            completed_stages += 1
            self._persist_run_log(
                source=f"pipeline:{stage_name}",
                status=RunStatus.success,
                message=f"stage {stage_name} completed",
            )

        self._persist_run_log(
            source="pipeline",
            status=RunStatus.success,
            message="pipeline completed all stages",
        )
        return PipelineRunOutcome(
            status=RunStatus.success,
            failed_stage=None,
            failure_classification=None,
        )

    def _persist_run_log(self, *, source: str, status: RunStatus, message: str) -> None:
        entry = RunLog(source=source, status=status, message=message)
        self._session.add(entry)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _validate_stage_set(self) -> None:
        provided = set(self._stages)
        required = set(STAGE_ORDER)
        if provided != required:
            missing = sorted(required - provided)
            extra = sorted(provided - required)
            raise ValueError(f"invalid stage set: missing={missing}, extra={extra}")


def classify_pipeline_failure(error: BaseException) -> str:
    if isinstance(error, TimeoutError | ConnectionError):
        return "transient"
    if isinstance(error, ValueError | TypeError):
        return "validation"
    return "terminal"
