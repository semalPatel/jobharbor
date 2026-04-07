from sqlmodel import Session, SQLModel, create_engine

from jobharbor.api.review import get_review_applications, review_dashboard
from jobharbor.models import Application, ApplicationStatus, Artifact, Job


def test_review_applications_returns_artifact_paths() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        job = Job(
            source="greenhouse",
            external_id="gh-1",
            company="Acme",
            title="AI Engineer",
            url="https://example.com/job",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        application = Application(job_id=job.id, status=ApplicationStatus.ready_for_review)
        session.add(application)
        session.commit()
        session.refresh(application)
        session.add(Artifact(application_id=application.id, kind="report", path="/tmp/report.md"))
        session.add(Artifact(application_id=application.id, kind="pdf", path="/tmp/cv.pdf"))
        session.commit()

        rows = get_review_applications(session=session)

    assert rows[0].company == "Acme"
    assert rows[0].title == "AI Engineer"
    assert rows[0].report == "/tmp/report.md"
    assert rows[0].pdf == "/tmp/cv.pdf"


def test_review_dashboard_renders_same_db_state() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        job = Job(source="greenhouse", external_id="gh-1", company="Acme", title="AI Engineer")
        session.add(job)
        session.commit()
        session.refresh(job)
        application = Application(job_id=job.id, status=ApplicationStatus.ready_for_review)
        session.add(application)
        session.commit()
        response = review_dashboard(session=session)

    html = response.body.decode("utf-8")
    assert "Jobharbor Review" in html
    assert "Acme" in html
    assert "AI Engineer" in html
    assert "ready_for_review" in html
