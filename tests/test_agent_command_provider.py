import json
import shlex
import sys

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from jobharbor.agents.command_provider import CommandEvaluationProvider
from jobharbor.models import Application, ApplicationStatus, Artifact, Evaluation, Job
from jobharbor.reports import EvaluationReportStageWorker


def _python_command(code: str) -> str:
    return f"{sys.executable} -c {shlex.quote(code)}"


def test_command_provider_passes_expected_json_input() -> None:
    code = """
import json, sys
payload = json.load(sys.stdin)
assert payload["cv_text"] == "cv"
assert payload["profile_text"] == "profile"
assert payload["prompt_text"] == "prompt"
print(json.dumps({
  "application_id": payload["application"]["id"],
  "job_id": payload["job"]["id"],
  "company": payload["job"]["company"],
  "role": payload["job"]["title"],
  "score": 4.2,
  "recommendation": "apply",
  "summary": "Strong fit.",
  "dimensions": [{"name": "role_fit", "score": 4.2, "rationale": "Relevant."}],
  "gaps": [],
  "risks": [],
  "next_actions": ["Apply manually."],
  "draft_answers": []
}))
"""
    provider = CommandEvaluationProvider(command=_python_command(code), timeout_seconds=5)
    job = Job(id=2, source="greenhouse", external_id="gh-1", title="AI Engineer", company="Acme")
    application = Application(id=1, job_id=2, status=ApplicationStatus.drafting)

    result = provider.evaluate(
        job=job,
        application=application,
        cv_text="cv",
        profile_text="profile",
        prompt_text="prompt",
    )

    assert result.application_id == 1
    assert result.job_id == 2
    assert result.score == 4.2
    assert result.recommendation == "apply"


def test_malformed_provider_output_is_rejected() -> None:
    provider = CommandEvaluationProvider(command=_python_command("print('not json')"), timeout_seconds=5)
    job = Job(id=2, source="greenhouse", external_id="gh-1")
    application = Application(id=1, job_id=2, status=ApplicationStatus.drafting)

    with pytest.raises(ValueError, match="malformed JSON"):
        provider.evaluate(job=job, application=application)


def test_provider_timeout_is_handled() -> None:
    provider = CommandEvaluationProvider(
        command=_python_command("import time; time.sleep(2)"),
        timeout_seconds=1,
    )
    job = Job(id=2, source="greenhouse", external_id="gh-1")
    application = Application(id=1, job_id=2, status=ApplicationStatus.drafting)

    with pytest.raises(TimeoutError, match="timed out"):
        provider.evaluate(job=job, application=application)


def test_failed_provider_does_not_transition_application_or_store_artifacts(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        job = Job(source="greenhouse", external_id="gh-1", title="AI Engineer", company="Acme")
        session.add(job)
        session.commit()
        session.refresh(job)
        application = Application(job_id=job.id, status=ApplicationStatus.drafting)
        session.add(application)
        session.commit()
        session.refresh(application)
        provider = CommandEvaluationProvider(command=_python_command("print('not json')"), timeout_seconds=5)
        context = {"queued_items": [{"app_id": application.id, "job": {}}]}

        EvaluationReportStageWorker(
            session=session,
            reports_dir=tmp_path,
            provider=provider,
        ).run(context)

        saved = session.get(Application, application.id)
        evaluations = session.exec(select(Evaluation)).all()
        artifacts = session.exec(select(Artifact)).all()

    assert saved is not None
    assert saved.status is ApplicationStatus.drafting
    assert evaluations == []
    assert artifacts == []
    assert context["report_artifacts"][0]["status"] == "failed"
