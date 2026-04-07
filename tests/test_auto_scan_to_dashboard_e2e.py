from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from jobharbor.api.review import get_review_applications
from jobharbor.evaluation import StubEvaluationProvider
from jobharbor.models import Application, ApplicationStatus, Artifact, Evaluation, Job
from jobharbor.reports import EvaluationReportStageWorker
from jobharbor.services.pipeline import STAGE_ORDER, PipelineCoordinator
from jobharbor.tracker import TrackerExportService
from jobharbor.workers.dedupe_stage import DedupeStageWorker
from jobharbor.workers.discover_stage import DiscoverStageWorker
from jobharbor.workers.normalize_stage import NormalizeStageWorker
from jobharbor.workers.prefill_stage import PrefillStageWorker
from jobharbor.workers.queue_stage import QueueStageWorker
from jobharbor.workers.review_stage import ReviewStageWorker
from jobharbor.workers.score_stage import ScoreStageWorker


class _Settings:
    connector_rollout: tuple[str, ...] = ("ashby",)
    discovery_capabilities: tuple[str, ...] = ("http",)
    include_domain_keywords: tuple[str, ...] = ()
    exclude_domain_keywords: tuple[str, ...] = ()
    allowed_location_keywords: tuple[str, ...] = ()
    allowed_work_auth: tuple[str, ...] = ()

    def __init__(self, jobharbor_home: Path) -> None:
        self.jobharbor_home = jobharbor_home


class _FakeConnector:
    def fetch_jobs(self):
        return [
            {
                "external_id": "ashby-1",
                "title": "AI Platform Engineer",
                "company": "Acme AI",
                "location": "Remote",
                "url": "https://jobs.ashbyhq.com/acme/ashby-1",
                "posted_at": "2026-04-07",
                "description": "Build AI platform systems.",
            }
        ]


def test_auto_scan_to_dashboard_e2e_without_live_network(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "cv.md").write_text("# CV\n\nAI platform experience.\n", encoding="utf-8")
    (workspace / "config").mkdir()
    profile_path = workspace / "config" / "profile.yml"
    profile_path.write_text("first_name: Ada\nemail: ada@example.com\n", encoding="utf-8")
    (workspace / "portals.yml").write_text(
        """\
tracked_companies:
  - name: Acme AI
    careers_url: https://jobs.ashbyhq.com/acme
    provider: ashby
    provider_slug: acme
    scan_method: http
    enabled: true
""",
        encoding="utf-8",
    )

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    settings = _Settings(workspace)

    with Session(engine) as session:
        discover = DiscoverStageWorker(
            session=session,
            settings=settings,
            feed_fetcher=lambda **_: [],
            company_site_urls=(),
            search_fetcher=lambda **_: [],
            connector_builder=lambda **_: [("ashby", _FakeConnector())],
        )
        evaluate = EvaluationReportStageWorker(
            session=session,
            reports_dir=workspace / "reports",
            provider=StubEvaluationProvider(),
            cv_path=workspace / "cv.md",
            profile_path=profile_path,
        )
        prefill = PrefillStageWorker(session=session, profile_path=profile_path)

        coordinator = PipelineCoordinator(
            session=session,
            stages={
                "discover": discover.run,
                "normalize": NormalizeStageWorker().run,
                "dedupe": DedupeStageWorker().run,
                "score": ScoreStageWorker(settings=settings).run,
                "queue": QueueStageWorker(session=session).run,
                "evaluate": evaluate.run,
                "prefill": prefill.run,
                "review": ReviewStageWorker().run,
                "notify": lambda context: context.update({"notified": True}),
            },
        )

        outcome = coordinator.run()
        TrackerExportService(session).export_applications(workspace / "data" / "applications.md")
        dashboard_rows = get_review_applications(session=session)

        jobs = list(session.exec(select(Job)).all())
        applications = list(session.exec(select(Application)).all())
        evaluations = list(session.exec(select(Evaluation)).all())
        artifacts = list(session.exec(select(Artifact)).all())

    assert outcome.failed_stage is None
    assert tuple(STAGE_ORDER) == (
        "discover",
        "normalize",
        "dedupe",
        "score",
        "queue",
        "evaluate",
        "prefill",
        "review",
        "notify",
    )
    assert len(jobs) == 1
    assert jobs[0].company == "Acme AI"
    assert jobs[0].provider == "ashby"
    assert len(applications) == 1
    assert applications[0].status == ApplicationStatus.ready_for_review
    assert len(evaluations) == 1
    assert len(artifacts) == 1
    assert artifacts[0].kind == "report"
    assert (workspace / "reports").is_dir()
    assert (workspace / "data" / "applications.md").read_text(encoding="utf-8").count("Acme AI") == 1
    assert dashboard_rows[0].company == "Acme AI"
    assert dashboard_rows[0].report is not None
    assert dashboard_rows[0].pdf is None
    assert applications[0].status != ApplicationStatus.submitted
