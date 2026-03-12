from sqlmodel import Session, SQLModel, create_engine

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from jobharbor.models import Application, ApplicationStatus, Job
from jobharbor.repositories.application_repo import ApplicationRepository


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


def _create_job(session: Session, *, source: str, external_id: str) -> Job:
    job = Job(source=source, external_id=external_id)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_enqueue_creates_drafting_application(session: Session) -> None:
    job = _create_job(session, source="greenhouse", external_id="gh-1")
    repo = ApplicationRepository(session)

    application = repo.enqueue(job.id)

    assert application.job_id == job.id
    assert application.status == ApplicationStatus.drafting


def test_enqueue_blocks_duplicate_for_same_job_when_active(session: Session) -> None:
    job = _create_job(session, source="greenhouse", external_id="gh-2")
    repo = ApplicationRepository(session)

    first = repo.enqueue(job.id)
    assert first.status == ApplicationStatus.drafting

    with pytest.raises(ValueError, match="active application"):
        repo.enqueue(job.id)


def test_enqueue_allows_requeue_after_terminal_status(session: Session) -> None:
    job = _create_job(session, source="greenhouse", external_id="gh-3")
    repo = ApplicationRepository(session)

    first = repo.enqueue(job.id)
    repo.transition_status(first.id, ApplicationStatus.ready_for_review)
    repo.transition_status(first.id, ApplicationStatus.submitted)

    second = repo.enqueue(job.id)

    assert second.id != first.id
    assert second.status == ApplicationStatus.drafting


def test_list_ready_for_review_applies_status_and_pagination(session: Session) -> None:
    job_a = _create_job(session, source="greenhouse", external_id="gh-4")
    job_b = _create_job(session, source="greenhouse", external_id="gh-5")
    job_c = _create_job(session, source="greenhouse", external_id="gh-6")
    repo = ApplicationRepository(session)

    app_a = repo.enqueue(job_a.id)
    app_b = repo.enqueue(job_b.id)
    repo.enqueue(job_c.id)

    repo.transition_status(app_a.id, ApplicationStatus.ready_for_review)
    repo.transition_status(app_b.id, ApplicationStatus.ready_for_review)

    page = repo.list_ready_for_review(limit=1, offset=1)

    assert len(page) == 1
    assert page[0].id == app_b.id
    assert page[0].status == ApplicationStatus.ready_for_review


def test_transition_status_updates_existing_application(session: Session) -> None:
    job = _create_job(session, source="greenhouse", external_id="gh-7")
    repo = ApplicationRepository(session)
    app = repo.enqueue(job.id)

    updated = repo.transition_status(app.id, ApplicationStatus.ready_for_review)

    assert updated.id == app.id
    assert updated.status == ApplicationStatus.ready_for_review


def test_transition_status_raises_for_missing_application(session: Session) -> None:
    repo = ApplicationRepository(session)

    with pytest.raises(LookupError, match="application not found"):
        repo.transition_status(999999, ApplicationStatus.ready_for_review)


def test_transition_status_rejects_disallowed_transition(session: Session) -> None:
    job = _create_job(session, source="greenhouse", external_id="gh-8")
    repo = ApplicationRepository(session)
    app = repo.enqueue(job.id)

    with pytest.raises(ValueError, match="disallowed transition"):
        repo.transition_status(app.id, ApplicationStatus.submitted)


def test_transition_into_active_blocked_when_other_active_exists(session: Session) -> None:
    job = _create_job(session, source="greenhouse", external_id="gh-9")
    repo = ApplicationRepository(session)

    active = repo.enqueue(job.id)
    inactive = Application(job_id=job.id, status=ApplicationStatus.failed)
    session.add(inactive)
    session.commit()
    session.refresh(inactive)

    with pytest.raises(ValueError, match="active application"):
        repo.transition_status(inactive.id, ApplicationStatus.drafting)

    current_active = session.get(Application, active.id)
    assert current_active is not None
    assert current_active.status == ApplicationStatus.drafting


def test_db_invariant_rejects_duplicate_active_application(session: Session) -> None:
    job = _create_job(session, source="greenhouse", external_id="gh-10")
    first = Application(job_id=job.id, status=ApplicationStatus.drafting)
    session.add(first)
    session.commit()

    second = Application(job_id=job.id, status=ApplicationStatus.ready_for_review)
    session.add(second)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_enqueue_commit_failure_rolls_back_and_session_remains_usable(
    session: Session,
) -> None:
    job = _create_job(session, source="greenhouse", external_id="gh-11")
    repo = ApplicationRepository(session)
    existing = Application(job_id=job.id, status=ApplicationStatus.drafting)
    session.add(existing)
    session.commit()

    repo._has_other_active_application = (  # type: ignore[method-assign]
        lambda **_: False
    )
    with pytest.raises(IntegrityError):
        repo.enqueue(job.id)

    applications = session.exec(select(Application)).all()
    assert len(applications) == 1
    assert applications[0].id == existing.id


def test_transition_commit_failure_rolls_back_and_session_remains_usable(
    session: Session,
) -> None:
    job = _create_job(session, source="greenhouse", external_id="gh-12")
    repo = ApplicationRepository(session)
    active = repo.enqueue(job.id)
    inactive = Application(job_id=job.id, status=ApplicationStatus.failed)
    session.add(inactive)
    session.commit()
    session.refresh(inactive)

    repo._has_other_active_application = (  # type: ignore[method-assign]
        lambda **_: False
    )
    with pytest.raises(IntegrityError):
        repo.transition_status(inactive.id, ApplicationStatus.drafting)

    current_inactive = session.get(Application, inactive.id)
    assert current_inactive is not None
    assert current_inactive.status == ApplicationStatus.failed

    current_active = session.get(Application, active.id)
    assert current_active is not None
    assert current_active.status == ApplicationStatus.drafting
