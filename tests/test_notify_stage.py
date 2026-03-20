from collections.abc import Iterator

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from jobharbor.models import Application, ApplicationStatus, Job, RunLog, RunStatus
from jobharbor.workers.notify_stage import NotifyStageWorker


class StubRouter:
    def __init__(self, outcomes: list[bool]) -> None:
        self._outcomes = outcomes
        self.calls: list[dict[str, str]] = []

    def send(self, *, title: str, company: str, source: str, review_url: str) -> bool:
        self.calls.append(
            {
                "title": title,
                "company": company,
                "source": source,
                "review_url": review_url,
            }
        )
        if self._outcomes:
            return self._outcomes.pop(0)
        return True


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


def _create_ready_application(session: Session) -> Application:
    job = Job(source="greenhouse", external_id="gh-1")
    session.add(job)
    session.commit()
    session.refresh(job)

    app = Application(job_id=job.id, status=ApplicationStatus.ready_for_review)
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


def test_notify_stage_sends_email_for_ready_for_review_application(session: Session) -> None:
    app = _create_ready_application(session)
    router = StubRouter([True])
    worker = NotifyStageWorker(session=session, notification_router=router)

    worker.run({})

    assert len(router.calls) == 1
    assert router.calls[0]["source"] == "greenhouse"
    assert f"{app.id}" in router.calls[0]["title"]

    run_logs = list(
        session.exec(select(RunLog).where(RunLog.source == f"notify:application:{app.id}")).all()
    )
    assert len(run_logs) == 1
    assert run_logs[0].status is RunStatus.success


def test_notify_stage_does_not_resend_when_already_notified(session: Session) -> None:
    app = _create_ready_application(session)
    router = StubRouter([True, True])
    worker = NotifyStageWorker(session=session, notification_router=router)

    worker.run({})
    worker.run({})

    assert len(router.calls) == 1

    run_logs = list(
        session.exec(select(RunLog).where(RunLog.source == f"notify:application:{app.id}")).all()
    )
    assert len(run_logs) == 1


def test_notify_stage_retries_after_failed_delivery(session: Session) -> None:
    app = _create_ready_application(session)
    router = StubRouter([False, True])
    worker = NotifyStageWorker(session=session, notification_router=router)

    worker.run({})

    first_pass_logs = list(
        session.exec(select(RunLog).where(RunLog.source == f"notify:application:{app.id}")).all()
    )
    assert first_pass_logs == []

    worker.run({})

    assert len(router.calls) == 2
    final_logs = list(
        session.exec(select(RunLog).where(RunLog.source == f"notify:application:{app.id}")).all()
    )
    assert len(final_logs) == 1
    assert final_logs[0].status is RunStatus.success


def test_notify_stage_uses_apply_url_from_prefill_log_when_available(session: Session) -> None:
    app = _create_ready_application(session)
    session.add(
        RunLog(
            source=f"prefill:application:{app.id}",
            status=RunStatus.success,
            message='{"apply_url":"https://boards.greenhouse.io/acme/jobs/123"}',
        )
    )
    session.commit()

    router = StubRouter([True])
    worker = NotifyStageWorker(session=session, notification_router=router)

    worker.run({})

    assert len(router.calls) == 1
    assert router.calls[0]["review_url"] == "https://boards.greenhouse.io/acme/jobs/123"
