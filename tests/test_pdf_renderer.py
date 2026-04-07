from sqlmodel import Session, SQLModel, create_engine, select

from jobharbor.evaluation import EvaluationResult, store_evaluation
from jobharbor.models import Application, ApplicationStatus, Artifact, Job
from jobharbor.pdf import PdfArtifactService, PdfRenderer
from jobharbor.tracker import TrackerExportService


def test_pdf_renderer_writes_pdf_artifact_and_tracker_links_it(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    tracker_path = tmp_path / "applications.md"

    with Session(engine) as session:
        job = Job(source="greenhouse", external_id="gh-1", company="Acme", title="AI Engineer")
        session.add(job)
        session.commit()
        session.refresh(job)
        application = Application(job_id=job.id, status=ApplicationStatus.ready_for_review)
        session.add(application)
        session.commit()
        session.refresh(application)
        evaluation = store_evaluation(
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
        evaluation_id = evaluation.id

        artifact = PdfArtifactService(session=session, output_dir=tmp_path / "output").render_for_application(
            application_id=application.id,
            cv_text="Experienced builder.",
        )
        TrackerExportService(session).export_applications(tracker_path)
        artifact_kind = None if artifact is None else artifact.kind
        artifact_path = None if artifact is None else artifact.path

    assert evaluation_id is not None
    assert artifact is not None
    assert artifact_kind == "pdf"
    assert artifact_path is not None
    assert artifact_path.endswith(".pdf")
    assert "%PDF" in (tmp_path / "output" / artifact_path.split("/")[-1]).read_text(encoding="ascii")
    assert "[PDF]" in tracker_path.read_text(encoding="utf-8")


def test_pdf_renderer_failure_does_not_fail_existing_report_state(tmp_path) -> None:
    class _FailingRenderer(PdfRenderer):
        def render(self, **kwargs):
            raise RuntimeError("browser unavailable")

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

        artifact = PdfArtifactService(
            session=session,
            output_dir=tmp_path,
            renderer=_FailingRenderer(),
        ).render_for_application(application_id=application.id)
        saved_application = session.get(Application, application.id)
        pdf_artifacts = session.exec(select(Artifact).where(Artifact.kind == "pdf")).all()

    assert artifact is None
    assert saved_application is not None
    assert saved_application.status is ApplicationStatus.ready_for_review
    assert pdf_artifacts == []
