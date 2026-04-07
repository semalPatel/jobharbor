from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from jobharbor.models import Application, ApplicationStatus, Job
from jobharbor.tracker import TrackerExportService, set_tracker_note


def test_tracker_export_writes_career_ops_compatible_markdown(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    output = tmp_path / "data" / "applications.md"

    with Session(engine) as session:
        job = Job(
            source="greenhouse",
            external_id="gh-1",
            company="Anthropic",
            title="Forward Deployed Engineer",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        application = Application(
            job_id=job.id,
            status=ApplicationStatus.ready_for_review,
            notes="Review comp | assumptions",
        )
        session.add(application)
        session.commit()

        rows = TrackerExportService(session).export_applications(output)

    assert len(rows) == 1
    assert output.read_text(encoding="utf-8") == (
        "| # | Date | Company | Role | Score | Status | PDF | Report | Notes |\n"
        "|---|------|---------|------|-------|--------|-----|--------|-------|\n"
        "| 1 |  | Anthropic | Forward Deployed Engineer |  | Evaluated |  |  | Review comp \\| assumptions |\n"
    )


def test_tracker_export_is_deterministic_by_application_id(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    output = tmp_path / "applications.md"

    with Session(engine) as session:
        later = Job(source="greenhouse", external_id="gh-later", company="B", title="Role B")
        earlier = Job(source="greenhouse", external_id="gh-earlier", company="A", title="Role A")
        session.add(later)
        session.add(earlier)
        session.commit()
        session.refresh(later)
        session.refresh(earlier)
        session.add(Application(job_id=later.id, status=ApplicationStatus.drafting))
        session.add(Application(job_id=earlier.id, status=ApplicationStatus.ready_for_review))
        session.commit()

        TrackerExportService(session).export_applications(output)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert "Role B" in lines[2]
    assert "Role A" in lines[3]


def test_tracker_note_updates_exported_notes(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    output = tmp_path / "applications.md"

    with Session(engine) as session:
        job = Job(source="greenhouse", external_id="gh-1", company="Acme", title="AI Engineer")
        session.add(job)
        session.commit()
        session.refresh(job)
        application = Application(job_id=job.id, status=ApplicationStatus.drafting)
        session.add(application)
        session.commit()
        session.refresh(application)

        set_tracker_note(session, application.id, "Applied via Greenhouse.")
        TrackerExportService(session).export_applications(output)

    assert "Applied via Greenhouse." in output.read_text(encoding="utf-8")
