from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from jobharbor.models import Application, Job
from jobharbor.reports import evaluation_result_from_model, report_artifact_for_application
from jobharbor.evaluation import latest_evaluation_for_application


@dataclass(frozen=True)
class DraftAnswer:
    question: str
    answer: str


@dataclass(frozen=True)
class FillPlan:
    application_id: int
    fields: tuple[DraftAnswer, ...]
    submit_allowed: bool = False

    def to_payload(self) -> dict[str, object]:
        return {
            "application_id": self.application_id,
            "fields": [field.__dict__ for field in self.fields],
            "submit_allowed": False,
        }


class ApplyAssistService:
    def __init__(self, *, session: Session) -> None:
        self._session = session

    def draft_answers(self, *, application_id: int, questions_text: str) -> FillPlan:
        application = self._session.get(Application, application_id)
        if application is None:
            raise LookupError(f"application not found: id={application_id}")
        job = self._session.get(Job, application.job_id)
        if job is None:
            raise LookupError(f"job not found: id={application.job_id}")
        evaluation = latest_evaluation_for_application(self._session, application_id)
        if evaluation is None:
            raise LookupError(f"evaluation not found for application_id={application_id}")
        report = report_artifact_for_application(self._session, application_id)
        if report is None:
            raise LookupError(f"report not found for application_id={application_id}")

        result = evaluation_result_from_model(evaluation)
        questions = _parse_questions(questions_text)
        fields = tuple(
            DraftAnswer(
                question=question,
                answer=(
                    f"Draft answer for {job.company or result.company}: "
                    f"connect this response to {result.role} and review before submitting."
                ),
            )
            for question in questions
        )
        fill_plan = FillPlan(application_id=application_id, fields=fields)
        _append_report_section(Path(report.path), fill_plan)
        return fill_plan


def _parse_questions(text: str) -> tuple[str, ...]:
    questions = tuple(line.strip("- ").strip() for line in text.splitlines() if line.strip())
    if not questions:
        raise ValueError("at least one application question is required")
    return questions


def _append_report_section(path: Path, fill_plan: FillPlan) -> None:
    content = path.read_text(encoding="utf-8")
    marker = "## Draft Application Answers"
    section_lines = ["", marker, ""]
    for field in fill_plan.fields:
        section_lines.extend([f"### {field.question}", "", field.answer, ""])
    section = "\n".join(section_lines).rstrip() + "\n"
    if marker in content:
        content = content.split(marker, maxsplit=1)[0].rstrip() + "\n" + section
    else:
        content = content.rstrip() + "\n" + section
    path.write_text(content, encoding="utf-8")
