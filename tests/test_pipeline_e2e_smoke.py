from collections.abc import Callable

from sqlmodel import Session, SQLModel, create_engine, select

from jobharbor.models import RunLog, RunStatus
from jobharbor.services.pipeline import STAGE_ORDER, PipelineCoordinator


StageFn = Callable[[dict[str, object]], None]


def _build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _build_stage_map(
    *,
    call_log: list[str],
    failing_stage: str | None = None,
) -> dict[str, StageFn]:
    stages: dict[str, StageFn] = {}

    for stage_name in STAGE_ORDER:

        def _make_stage(name: str) -> StageFn:
            def _stage(context: dict[str, object]) -> None:
                context[name] = True
                call_log.append(name)
                if failing_stage == name:
                    raise TimeoutError(f"{name} timed out")

            return _stage

        stages[stage_name] = _make_stage(stage_name)

    return stages


def test_pipeline_runs_stages_in_deterministic_order() -> None:
    call_log: list[str] = []

    with _build_session() as session:
        coordinator = PipelineCoordinator(
            session=session,
            stages=_build_stage_map(call_log=call_log),
        )

        outcome = coordinator.run()

        logs = list(session.exec(select(RunLog).order_by(RunLog.id)).all())

    assert outcome.status is RunStatus.success
    assert outcome.failed_stage is None
    assert call_log == list(STAGE_ORDER)
    assert [log.source for log in logs] == [
        "pipeline:discover",
        "pipeline:normalize",
        "pipeline:dedupe",
        "pipeline:score",
        "pipeline:queue",
        "pipeline:evaluate",
        "pipeline:prefill",
        "pipeline:review",
        "pipeline:notify",
        "pipeline",
    ]
    assert logs[-1].status is RunStatus.success


def test_pipeline_classifies_stage_failure_and_persists_run_log() -> None:
    call_log: list[str] = []

    with _build_session() as session:
        coordinator = PipelineCoordinator(
            session=session,
            stages=_build_stage_map(call_log=call_log, failing_stage="dedupe"),
        )

        outcome = coordinator.run()

        logs = list(session.exec(select(RunLog).order_by(RunLog.id)).all())

    assert outcome.status is RunStatus.partial_failure
    assert outcome.failed_stage == "dedupe"
    assert outcome.failure_classification == "transient"
    assert call_log == ["discover", "normalize", "dedupe"]

    dedupe_failure_log = logs[2]
    assert dedupe_failure_log.source == "pipeline:dedupe"
    assert dedupe_failure_log.status is RunStatus.failed
    assert dedupe_failure_log.message == (
        "stage=dedupe classification=transient error_type=TimeoutError error=dedupe timed out"
    )

    summary = logs[-1]
    assert summary.source == "pipeline"
    assert summary.status is RunStatus.partial_failure
    assert summary.message == "pipeline halted at stage dedupe"
