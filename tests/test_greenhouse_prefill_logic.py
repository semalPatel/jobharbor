from sqlmodel import Session, SQLModel, create_engine

import pytest

from jobharbor.models import ApplicationStatus, Job
from jobharbor.repositories.application_repo import ApplicationRepository
from jobharbor.workers.greenhouse_prefill import (
    FINAL_SUBMIT_SELECTOR,
    GreenhousePrefillWorker,
)


def _create_job(session: Session, *, source: str, external_id: str) -> Job:
    job = Job(source=source, external_id=external_id)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


def test_prefill_maps_profile_fields_into_greenhouse_payload(session: Session) -> None:
    repo = ApplicationRepository(session)
    worker = GreenhousePrefillWorker(application_repo=repo)

    payload = worker.build_form_payload(
        {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "phone": "+1-555-111-2222",
            "location": "San Francisco, CA",
            "linkedin_url": "https://linkedin.com/in/ada",
            "website_url": "https://ada.dev",
        }
    )

    assert payload == {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "phone": "+1-555-111-2222",
        "location": "San Francisco, CA",
        "linkedin": "https://linkedin.com/in/ada",
        "website": "https://ada.dev",
    }


def test_prefill_marks_resume_upload_requested_when_resume_present(session: Session) -> None:
    repo = ApplicationRepository(session)
    worker = GreenhousePrefillWorker(application_repo=repo)
    job = _create_job(session, source="greenhouse", external_id="gh-prefill-2")
    app = repo.enqueue(job.id)

    outcome = worker.prepare_for_review(
        app_id=app.id,
        profile={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "resume_path": "/tmp/resume.pdf",
        },
        planned_actions=[
            {"action": "fill", "selector": "#first_name"},
            {"action": "upload", "selector": "input[type='file'][name='resume']"},
        ],
    )

    assert outcome.resume_upload_requested is True


def test_prefill_transitions_to_ready_for_review_without_submit(session: Session) -> None:
    repo = ApplicationRepository(session)
    worker = GreenhousePrefillWorker(application_repo=repo)
    job = _create_job(session, source="greenhouse", external_id="gh-prefill-3")
    app = repo.enqueue(job.id)

    outcome = worker.prepare_for_review(
        app_id=app.id,
        profile={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
        planned_actions=[{"action": "fill", "selector": "#first_name"}],
    )

    saved = session.get(type(app), app.id)

    assert outcome.final_status is ApplicationStatus.ready_for_review
    assert saved is not None
    assert saved.status is ApplicationStatus.ready_for_review


def test_prefill_hard_blocks_final_submit_selector(session: Session) -> None:
    repo = ApplicationRepository(session)
    worker = GreenhousePrefillWorker(application_repo=repo)
    job = _create_job(session, source="greenhouse", external_id="gh-prefill-4")
    app = repo.enqueue(job.id)

    with pytest.raises(RuntimeError, match="submit boundary"):
        worker.prepare_for_review(
            app_id=app.id,
            profile={
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.com",
            },
            planned_actions=[
                {"action": "fill", "selector": "#first_name"},
                {"action": "click", "selector": FINAL_SUBMIT_SELECTOR},
            ],
        )

    saved = session.get(type(app), app.id)
    assert saved is not None
    assert saved.status is ApplicationStatus.drafting
