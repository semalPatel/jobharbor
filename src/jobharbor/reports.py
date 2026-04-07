from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from jobharbor.evaluation import (
    EvaluationDimension,
    EvaluationResult,
    StubEvaluationProvider,
    store_evaluation,
)
from jobharbor.models import Application, Artifact, Evaluation, Job


class ReportRenderer:
    def render(self, result: EvaluationResult, *, job_url: str | None = None) -> str:
        lines = [
            f"# {result.company} - {result.role}",
            "",
            f"- URL: {job_url or ''}",
            f"- Score: {result.score}/5",
            f"- Recommendation: {result.recommendation}",
            "",
            "## Summary",
            "",
            result.summary,
            "",
            "## Dimensions",
            "",
        ]
        for dimension in result.dimensions:
            lines.append(f"- {dimension.name}: {dimension.score}/5 - {dimension.rationale}")
        lines.extend(["", "## Gaps", ""])
        lines.extend(f"- {gap}" for gap in result.gaps)
        lines.extend(["", "## Risks", ""])
        lines.extend(f"- {risk}" for risk in result.risks)
        lines.extend(["", "## Next Actions", ""])
        lines.extend(f"- {action}" for action in result.next_actions)
        return "\n".join(lines) + "\n"

    def write(self, result: EvaluationResult, *, job_url: str | None, reports_dir: Path) -> Path:
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / f"{result.application_id:03d}-{_slug(result.company)}.md"
        path.write_text(self.render(result, job_url=job_url), encoding="utf-8")
        return path


class EvaluationReportStageWorker:
    def __init__(
        self,
        *,
        session: Session,
        reports_dir: Path,
        provider: StubEvaluationProvider | None = None,
        renderer: ReportRenderer | None = None,
    ) -> None:
        self._session = session
        self._reports_dir = reports_dir
        self._provider = provider or StubEvaluationProvider()
        self._renderer = renderer or ReportRenderer()

    def run(self, context: dict[str, Any]) -> None:
        queued_items = context.get("queued_items")
        if not isinstance(queued_items, list):
            return

        artifacts: list[dict[str, object]] = []
        for item in queued_items:
            if not isinstance(item, dict) or not isinstance(item.get("app_id"), int):
                continue
            application = self._session.get(Application, item["app_id"])
            if application is None:
                continue
            job = self._session.get(Job, application.job_id)
            if job is None:
                continue

            result = self._provider.evaluate(application=application, job=job)
            evaluation = store_evaluation(self._session, result=result, provider=self._provider.provider_name)
            path = self._renderer.write(result, job_url=job.url, reports_dir=self._reports_dir)
            artifact = Artifact(application_id=application.id, kind="report", path=str(path))
            self._session.add(artifact)
            self._session.commit()
            self._session.refresh(artifact)
            artifacts.append({"evaluation_id": evaluation.id, "artifact_id": artifact.id, "path": str(path)})

        context["report_artifacts"] = artifacts


def report_artifact_for_application(session: Session, application_id: int) -> Artifact | None:
    stmt = (
        select(Artifact)
        .where(Artifact.application_id == application_id)
        .where(Artifact.kind == "report")
        .order_by(Artifact.id.desc())
        .limit(1)
    )
    return session.exec(stmt).first()


def evaluation_result_from_model(evaluation: Evaluation) -> EvaluationResult:
    payload = json.loads(evaluation.payload_json)
    return EvaluationResult(
        application_id=payload["application_id"],
        job_id=payload["job_id"],
        company=payload["company"],
        role=payload["role"],
        score=payload["score"],
        recommendation=payload["recommendation"],
        summary=payload["summary"],
        dimensions=tuple(EvaluationDimension(**row) for row in payload.get("dimensions", [])),
        gaps=tuple(payload.get("gaps", [])),
        risks=tuple(payload.get("risks", [])),
        next_actions=tuple(payload.get("next_actions", [])),
        draft_answers=tuple(payload.get("draft_answers", [])),
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"
