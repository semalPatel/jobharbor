from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from jobharbor.db import get_session
from jobharbor.main import app
from jobharbor.models import Application, ApplicationStatus, Job


def _make_client_with_db() -> tuple[TestClient, object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), engine


def _seed_application(*, engine: object, source: str, external_id: str, status: ApplicationStatus) -> Application:
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


def test_get_review_queue_returns_only_ready_for_review_items() -> None:
    client, engine = _make_client_with_db()
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

    response = client.get("/review/queue")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "job_id": 1, "status": "ready_for_review"},
    ]
    app.dependency_overrides.clear()


def test_post_submitted_transitions_application_to_submitted() -> None:
    client, engine = _make_client_with_db()
    application = _seed_application(
        engine=engine,
        source="greenhouse",
        external_id="gh-ready-2",
        status=ApplicationStatus.ready_for_review,
    )

    response = client.post(f"/review/{application.id}/submitted")

    assert response.status_code == 200
    assert response.json() == {
        "id": application.id,
        "job_id": application.job_id,
        "status": "submitted",
    }

    with Session(engine) as session:
        saved = session.get(Application, application.id)

    assert saved is not None
    assert saved.status == ApplicationStatus.submitted
    app.dependency_overrides.clear()
