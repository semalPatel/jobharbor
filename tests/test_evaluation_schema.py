import pytest
from sqlmodel import Session, SQLModel, create_engine

from jobharbor.evaluation import EvaluationResult, StubEvaluationProvider, latest_evaluation_for_application, store_evaluation
from jobharbor.models import Application, ApplicationStatus, Job


def test_invalid_score_rejected() -> None:
    with pytest.raises(ValueError, match=r"\[0, 5\]"):
        EvaluationResult(
            application_id=1,
            job_id=1,
            company="Acme",
            role="AI Engineer",
            score=5.1,
            recommendation="review",
            summary="",
        )


def test_invalid_recommendation_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported recommendation"):
        EvaluationResult(
            application_id=1,
            job_id=1,
            company="Acme",
            role="AI Engineer",
            score=4,
            recommendation="yes",
            summary="",
        )


def test_stub_provider_returns_deterministic_result() -> None:
    job = Job(id=2, source="greenhouse", external_id="gh-1", title="Senior AI Engineer", company="Acme")
    application = Application(id=1, job_id=2, status=ApplicationStatus.drafting)

    result = StubEvaluationProvider().evaluate(application=application, job=job)

    assert result.company == "Acme"
    assert result.role == "Senior AI Engineer"
    assert result.score == 3.5
    assert result.recommendation == "review"


def test_store_evaluation_round_trips_payload() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    result = EvaluationResult(
        application_id=1,
        job_id=2,
        company="Acme",
        role="AI Engineer",
        score=4.0,
        recommendation="apply",
        summary="Strong fit.",
    )

    with Session(engine) as session:
        stored = store_evaluation(session, result=result, provider="stub")
        latest = latest_evaluation_for_application(session, 1)

    assert stored.provider == "stub"
    assert latest is not None
    assert latest.payload_json
