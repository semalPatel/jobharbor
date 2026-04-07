from sqlmodel import Session, SQLModel, create_engine, select

from jobharbor.evaluation import EvaluationDimension, EvaluationResult
from jobharbor.models import Application, ApplicationStatus, Artifact, Evaluation, Job
from jobharbor.reports import EvaluationReportStageWorker, ReportRenderer
from jobharbor.tracker import TrackerExportService


def test_report_renderer_produces_expected_markdown_fields(tmp_path) -> None:
    result = EvaluationResult(
        application_id=42,
        job_id=99,
        company="Anthropic",
        role="Forward Deployed Engineer",
        score=4.4,
        recommendation="apply",
        summary="Strong fit.",
        dimensions=(EvaluationDimension(name="role_fit", score=4.5, rationale="Relevant."),),
        gaps=("One gap.",),
        risks=("One risk.",),
        next_actions=("Review comp.",),
    )

    path = ReportRenderer().write(result, job_url="https://example.com/job", reports_dir=tmp_path)
    content = path.read_text(encoding="utf-8")

    assert "# Anthropic - Forward Deployed Engineer" in content
    assert "- URL: https://example.com/job" in content
    assert "- Score: 4.4/5" in content
    assert "- Recommendation: apply" in content
    assert "Strong fit." in content


def test_evaluation_stage_stores_artifact_and_tracker_links_report(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    tracker_path = tmp_path / "applications.md"

    with Session(engine) as session:
        job = Job(
            source="greenhouse",
            external_id="gh-1",
            title="AI Engineer",
            company="Acme",
            url="https://example.com/job",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        application = Application(job_id=job.id, status=ApplicationStatus.drafting)
        session.add(application)
        session.commit()
        session.refresh(application)
        context = {"queued_items": [{"app_id": application.id, "job": {}}]}

        EvaluationReportStageWorker(session=session, reports_dir=tmp_path / "reports").run(context)
        TrackerExportService(session).export_applications(tracker_path)

        evaluations = session.exec(select(Evaluation)).all()
        artifacts = session.exec(select(Artifact)).all()

    assert len(evaluations) == 1
    assert len(artifacts) == 1
    assert artifacts[0].kind == "report"
    assert "Report" in tracker_path.read_text(encoding="utf-8")
