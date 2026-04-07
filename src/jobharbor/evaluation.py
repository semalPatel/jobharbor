from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from sqlmodel import Session, select

from jobharbor.models import Application, Evaluation, Job

RECOMMENDATIONS = {"apply", "review", "hold", "skip"}


@dataclass(frozen=True)
class EvaluationDimension:
    name: str
    score: float
    rationale: str


@dataclass(frozen=True)
class EvaluationResult:
    application_id: int
    job_id: int
    company: str
    role: str
    score: float
    recommendation: str
    summary: str
    dimensions: tuple[EvaluationDimension, ...] = ()
    gaps: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    draft_answers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 5:
            raise ValueError("evaluation score must be within [0, 5]")
        if self.recommendation not in RECOMMENDATIONS:
            raise ValueError(f"unsupported recommendation: {self.recommendation}")

    def to_payload(self) -> dict[str, Any]:
        return {
            "application_id": self.application_id,
            "job_id": self.job_id,
            "company": self.company,
            "role": self.role,
            "score": self.score,
            "recommendation": self.recommendation,
            "summary": self.summary,
            "dimensions": [dimension.__dict__ for dimension in self.dimensions],
            "gaps": list(self.gaps),
            "risks": list(self.risks),
            "next_actions": list(self.next_actions),
            "draft_answers": list(self.draft_answers),
        }


class StubEvaluationProvider:
    provider_name = "stub"

    def evaluate(
        self,
        *,
        application: Application,
        job: Job,
        cv_text: str = "",
        profile_text: str = "",
        prompt_text: str = "",
    ) -> EvaluationResult:
        del cv_text, prompt_text
        role = job.title or "Unknown role"
        company = job.company or "Unknown company"
        profile_bonus = 0.2 if profile_text.strip() else 0.0
        score = min(5.0, round(3.0 + profile_bonus + (0.5 if "senior" in role.lower() else 0.0), 1))
        recommendation = "apply" if score >= 4 else "review"
        return EvaluationResult(
            application_id=application.id or 0,
            job_id=job.id or 0,
            company=company,
            role=role,
            score=score,
            recommendation=recommendation,
            summary=f"Stub evaluation for {role} at {company}.",
            dimensions=(
                EvaluationDimension(
                    name="role_fit",
                    score=score,
                    rationale="Deterministic stub score based on role title and profile presence.",
                ),
            ),
            gaps=("Replace stub evaluation with provider output.",),
            risks=("No live agent analysis was performed.",),
            next_actions=("Review the job description and decide whether to apply.",),
        )


def store_evaluation(
    session: Session,
    *,
    result: EvaluationResult,
    provider: str,
) -> Evaluation:
    evaluation = Evaluation(
        application_id=result.application_id,
        job_id=result.job_id,
        score=result.score,
        recommendation=result.recommendation,
        summary=result.summary,
        payload_json=json.dumps(result.to_payload(), sort_keys=True),
        provider=provider,
    )
    session.add(evaluation)
    session.commit()
    session.refresh(evaluation)
    return evaluation


def latest_evaluation_for_application(session: Session, application_id: int) -> Evaluation | None:
    stmt = (
        select(Evaluation)
        .where(Evaluation.application_id == application_id)
        .order_by(Evaluation.id.desc())
        .limit(1)
    )
    return session.exec(stmt).first()


def build_evaluation_provider(settings):
    if settings.evaluation_provider == "stub":
        return StubEvaluationProvider()
    if settings.evaluation_provider in {"command", "codex"}:
        from jobharbor.agents.command_provider import CommandEvaluationProvider

        if not settings.evaluation_command:
            raise ValueError("evaluation_command is required for command/codex provider")
        provider = CommandEvaluationProvider(
            command=settings.evaluation_command,
            timeout_seconds=settings.evaluation_timeout_seconds,
        )
        provider.provider_name = settings.evaluation_provider
        return provider
    raise ValueError(f"unsupported evaluation provider: {settings.evaluation_provider}")
