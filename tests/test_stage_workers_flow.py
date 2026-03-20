from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from jobharbor.models import Application, ApplicationStatus, Job, RunLog
from jobharbor.workers.normalize_stage import NormalizeStageWorker
from jobharbor.workers.dedupe_stage import DedupeStageWorker
from jobharbor.workers.score_stage import ScoreStageWorker
from jobharbor.workers.queue_stage import QueueStageWorker
from jobharbor.workers.prefill_stage import PrefillStageWorker


class _Settings:
    include_domain_keywords = ("android", "kotlin")
    exclude_domain_keywords = ()
    allowed_location_keywords = ("remote",)
    allowed_work_auth = ("us_authorized",)
    connector_rollout = ("greenhouse", "ashby", "lever")


def _context_with_discovered_jobs() -> dict[str, object]:
    return {
        "discovered_jobs": [
            {
                "source": "greenhouse",
                "external_id": "gh-1",
                "title": "Senior Android Engineer",
                "description": "Kotlin role. Remote in US.",
                "location": "Remote - US",
                "url": "https://boards.greenhouse.io/acme/jobs/1",
                "posted_at": "2026-03-14",
            },
            {
                "source": "feed",
                "external_id": "feed-1",
                "title": "Android Kotlin Developer",
                "description": "Fully remote role.",
                "location": "Remote",
                "url": "https://example.com/jobs/1",
                "posted_at": "2026-03-14",
            },
        ]
    }


def test_stage_flow_queues_and_prefills_ready_for_review_with_profile_file(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        """
first_name: Semal
last_name: Patel
email: skpatel@alumni.scu.edu
location: san francisco bay area
resume_path: /Users/corrupt/Documents/resumes/resume_semal.pdf
""".strip()
    )

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    context = _context_with_discovered_jobs()

    with Session(engine) as session:
        NormalizeStageWorker().run(context)
        DedupeStageWorker().run(context)
        ScoreStageWorker(settings=_Settings()).run(context)
        QueueStageWorker(session=session).run(context)
        PrefillStageWorker(session=session, profile_path=profile_path).run(context)

        apps = list(session.exec(select(Application).order_by(Application.id)).all())
        assert len(apps) == 1
        assert all(app.status is ApplicationStatus.ready_for_review for app in apps)

        prefill_logs = list(
            session.exec(
                select(RunLog).where(RunLog.source.like("prefill:application:%")).order_by(RunLog.id)
            ).all()
        )
        assert len(prefill_logs) == 1
        assert all('"apply_url"' in (log.message or "") for log in prefill_logs)


def test_unknown_work_auth_is_allowed_when_policy_requires_work_auth() -> None:
    context = _context_with_discovered_jobs()

    NormalizeStageWorker().run(context)
    DedupeStageWorker().run(context)
    ScoreStageWorker(settings=_Settings()).run(context)

    eligible = context["eligible_jobs"]
    assert isinstance(eligible, list)
    assert len(eligible) == 1
