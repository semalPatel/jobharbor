import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect
from sqlmodel import SQLModel, Session, create_engine, select

import jobharbor.db as db
from jobharbor.models import (
    Application,
    ApplicationStatus,
    Job,
    JobStatus,
    RunLog,
    RunStatus,
)


def test_job_status_values() -> None:
    assert [status.value for status in JobStatus] == [
        "discovered",
        "normalized",
        "queued",
        "skipped",
    ]


def test_application_status_values_include_ready_for_review() -> None:
    assert [status.value for status in ApplicationStatus] == [
        "drafting",
        "ready_for_review",
        "submitted",
        "failed",
        "abandoned",
    ]


def test_run_status_values() -> None:
    assert [status.value for status in RunStatus] == [
        "started",
        "success",
        "partial_failure",
        "failed",
    ]


def test_models_are_registered_in_sqlmodel_metadata() -> None:
    table_names = set(SQLModel.metadata.tables)

    assert Job.__tablename__ in table_names
    assert Application.__tablename__ in table_names
    assert RunLog.__tablename__ in table_names


def test_models_create_tables_and_round_trip_rows() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    created_tables = set(inspect(engine).get_table_names())

    assert Job.__tablename__ in created_tables
    assert Application.__tablename__ in created_tables
    assert RunLog.__tablename__ in created_tables

    with Session(engine) as session:
        job = Job(source="greenhouse", external_id="gh-1", status=JobStatus.discovered)
        session.add(job)
        session.commit()
        session.refresh(job)

        application = Application(job_id=job.id, status=ApplicationStatus.ready_for_review)
        run_log = RunLog(source="greenhouse", status=RunStatus.started)
        session.add(application)
        session.add(run_log)
        session.commit()

        saved_job = session.exec(select(Job)).one()
        saved_application = session.exec(select(Application)).one()
        saved_run_log = session.exec(select(RunLog)).one()

    assert saved_job.status == JobStatus.discovered
    assert saved_application.status == ApplicationStatus.ready_for_review
    assert saved_run_log.status == RunStatus.started


def test_job_source_external_id_is_unique() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Job(source="greenhouse", external_id="dupe-id"))
        session.commit()

        session.add(Job(source="greenhouse", external_id="dupe-id"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_application_fk_rejects_nonexistent_job_id_when_enforced() -> None:
    db._engine_for_url.cache_clear()
    engine = db.get_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Application(job_id=999_999, status=ApplicationStatus.drafting))
        with pytest.raises(IntegrityError):
            session.commit()
