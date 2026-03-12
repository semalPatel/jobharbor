from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from jobharbor.db import get_session
from jobharbor.main import app
from jobharbor.models import Application, ApplicationStatus, Job


@pytest.fixture
def client_with_db() -> Iterator[tuple[TestClient, Engine]]:
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
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()


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
    client_with_db: tuple[TestClient, Engine],
) -> None:
    client, engine = client_with_db
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


def test_get_review_queue_supports_pagination_with_stable_id_ordering(
    client_with_db: tuple[TestClient, Engine],
) -> None:
    client, engine = client_with_db
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

    response = client.get("/review/queue?limit=2&offset=1")

    assert response.status_code == 200
    assert response.json() == [
        {"id": second.id, "job_id": second.job_id, "status": "ready_for_review"},
        {"id": third.id, "job_id": third.job_id, "status": "ready_for_review"},
    ]
    assert first.id < second.id < third.id


def test_post_submitted_transitions_application_to_submitted(
    client_with_db: tuple[TestClient, Engine],
) -> None:
    client, engine = client_with_db
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


def test_post_submitted_returns_404_for_missing_application(
    client_with_db: tuple[TestClient, Engine],
) -> None:
    client, _ = client_with_db

    response = client.post("/review/999999/submitted")

    assert response.status_code == 404
    assert "application not found" in response.json()["detail"]


def test_post_submitted_returns_409_for_invalid_transition_conflict(
    client_with_db: tuple[TestClient, Engine],
) -> None:
    client, engine = client_with_db
    drafting = _seed_application(
        engine=engine,
        source="greenhouse",
        external_id="gh-drafting-conflict",
        status=ApplicationStatus.drafting,
    )

    response = client.post(f"/review/{drafting.id}/submitted")

    assert response.status_code == 409
    assert "disallowed transition" in response.json()["detail"]
