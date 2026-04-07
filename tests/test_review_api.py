from collections.abc import Iterator

import pytest
from fastapi import HTTPException
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from jobharbor.api.review import get_review_queue, mark_submitted
from jobharbor.models import Application, ApplicationStatus, Job


@pytest.fixture
def session_with_db() -> Iterator[tuple[Session, Engine]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session, engine


def _seed_application(
    *,
    engine: Engine,
    source: str,
    external_id: str,
    status: ApplicationStatus,
) -> Application:
    with Session(engine) as session:
        job = Job(source=source, external_id=external_id)
        session.add(job)
        session.commit()
        session.refresh(job)

        application = Application(job_id=job.id, status=status)
        session.add(application)
        session.commit()
        session.refresh(application)
        return application


def test_get_review_queue_returns_only_ready_for_review_items(
    session_with_db: tuple[Session, Engine],
) -> None:
    session, engine = session_with_db
    _seed_application(
        engine=engine,
        source="greenhouse",
        external_id="gh-ready",
        status=ApplicationStatus.ready_for_review,
    )
    _seed_application(
        engine=engine,
        source="greenhouse",
        external_id="gh-drafting",
        status=ApplicationStatus.drafting,
    )

    response = get_review_queue(limit=50, offset=0, session=session)

    assert [row.model_dump(mode="json") for row in response] == [
        {"id": 1, "job_id": 1, "status": "ready_for_review"},
    ]


def test_get_review_queue_supports_pagination_with_stable_id_ordering(
    session_with_db: tuple[Session, Engine],
) -> None:
    session, engine = session_with_db
    first = _seed_application(
        engine=engine,
        source="greenhouse",
        external_id="gh-ready-1",
        status=ApplicationStatus.ready_for_review,
    )
    _seed_application(
        engine=engine,
        source="greenhouse",
        external_id="gh-drafting-1",
        status=ApplicationStatus.drafting,
    )
    second = _seed_application(
        engine=engine,
        source="greenhouse",
        external_id="gh-ready-2",
        status=ApplicationStatus.ready_for_review,
    )
    third = _seed_application(
        engine=engine,
        source="greenhouse",
        external_id="gh-ready-3",
        status=ApplicationStatus.ready_for_review,
    )

    response = get_review_queue(limit=2, offset=1, session=session)

    assert [row.model_dump(mode="json") for row in response] == [
        {"id": second.id, "job_id": second.job_id, "status": "ready_for_review"},
        {"id": third.id, "job_id": third.job_id, "status": "ready_for_review"},
    ]
    assert first.id < second.id < third.id


def test_post_submitted_transitions_application_to_submitted(
    session_with_db: tuple[Session, Engine],
) -> None:
    session, engine = session_with_db
    application = _seed_application(
        engine=engine,
        source="greenhouse",
        external_id="gh-ready-2",
        status=ApplicationStatus.ready_for_review,
    )

    response = mark_submitted(application.id, session=session)

    assert response.model_dump(mode="json") == {
        "id": application.id,
        "job_id": application.job_id,
        "status": "submitted",
    }

    with Session(engine) as session:
        saved = session.get(Application, application.id)

    assert saved is not None
    assert saved.status == ApplicationStatus.submitted


def test_post_submitted_returns_404_for_missing_application(
    session_with_db: tuple[Session, Engine],
) -> None:
    session, _ = session_with_db

    with pytest.raises(HTTPException) as exc_info:
        mark_submitted(999999, session=session)

    assert exc_info.value.status_code == 404
    assert "application not found" in exc_info.value.detail


def test_post_submitted_returns_409_for_invalid_transition_conflict(
    session_with_db: tuple[Session, Engine],
) -> None:
    session, engine = session_with_db
    drafting = _seed_application(
        engine=engine,
        source="greenhouse",
        external_id="gh-drafting-conflict",
        status=ApplicationStatus.drafting,
    )

    with pytest.raises(HTTPException) as exc_info:
        mark_submitted(drafting.id, session=session)

    assert exc_info.value.status_code == 409
    assert "disallowed transition" in exc_info.value.detail
