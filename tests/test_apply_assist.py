from sqlmodel import Session, SQLModel, create_engine

import pytest

from jobharbor.apply_assist import ApplyAssistService
from jobharbor.evaluation import EvaluationResult, store_evaluation
from jobharbor.models import Application, ApplicationStatus, Artifact, Job


def test_drafts_answers_and_appends_report_section(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    report_path = tmp_path / "report.md"
    report_path.write_text("# Report\n", encoding="utf-8")

    with Session(engine) as session:
        job = Job(source="greenhouse", external_id="gh-1", company="Acme", title="AI Engineer")
        session.add(job)
        session.commit()
        session.refresh(job)
        application = Application(job_id=job.id, status=ApplicationStatus.ready_for_review)
        session.add(application)
        session.commit()
        session.refresh(application)
        store_evaluation(
            session,
            result=EvaluationResult(
                application_id=application.id,
                job_id=job.id,
                company="Acme",
                role="AI Engineer",
                score=4.2,
                recommendation="apply",
                summary="Strong fit.",
            ),
            provider="stub",
        )
        session.add(Artifact(application_id=application.id, kind="report", path=str(report_path)))
        session.commit()

        fill_plan = ApplyAssistService(session=session).draft_answers(
            application_id=application.id,
            questions_text="Why this role?\nWhat makes you a fit?",
        )

    assert fill_plan.submit_allowed is False
    assert fill_plan.to_payload()["submit_allowed"] is False
    assert len(fill_plan.fields) == 2
    content = report_path.read_text(encoding="utf-8")
    assert "## Draft Application Answers" in content
    assert "### Why this role?" in content


def test_missing_evaluation_returns_clear_error(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    report_path = tmp_path / "report.md"
    report_path.write_text("# Report\n", encoding="utf-8")

    with Session(engine) as session:
        job = Job(source="greenhouse", external_id="gh-1", company="Acme", title="AI Engineer")
        session.add(job)
        session.commit()
        session.refresh(job)
        application = Application(job_id=job.id, status=ApplicationStatus.ready_for_review)
        session.add(application)
        session.commit()
        session.refresh(application)
        session.add(Artifact(application_id=application.id, kind="report", path=str(report_path)))
        session.commit()

        with pytest.raises(LookupError, match="evaluation not found"):
            ApplyAssistService(session=session).draft_answers(
                application_id=application.id,
                questions_text="Why this role?",
            )
