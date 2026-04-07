from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from jobharbor.models import Application, ApplicationStatus, Job
from jobharbor.reports import report_artifact_for_application


TRACKER_STATUSES: tuple[str, ...] = (
    "Drafting",
    "Evaluated",
    "Applied",
    "Responded",
    "Interview",
    "Offer",
    "Rejected",
    "Discarded",
    "SKIP",
    "Failed",
)

APPLICATION_STATUS_TO_TRACKER: dict[ApplicationStatus, str] = {
    ApplicationStatus.drafting: "Drafting",
    ApplicationStatus.ready_for_review: "Evaluated",
    ApplicationStatus.submitted: "Applied",
    ApplicationStatus.failed: "Failed",
    ApplicationStatus.abandoned: "Discarded",
}


@dataclass(frozen=True)
class TrackerRow:
    application_id: int
    date: str
    company: str
    role: str
    score: str
    status: str
    pdf: str
    report: str
    notes: str


class TrackerExportService:
    header = "| # | Date | Company | Role | Score | Status | PDF | Report | Notes |"
    separator = "|---|------|---------|------|-------|--------|-----|--------|-------|"

    def __init__(self, session: Session) -> None:
        self._session = session

    def export_applications(
        self,
        path: Path,
        *,
        status: str | None = None,
        company: str | None = None,
        min_score: float | None = None,
    ) -> list[TrackerRow]:
        rows = self.rows(status=status, company=company, min_score=min_score)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(rows), encoding="utf-8")
        return rows

    def rows(
        self,
        *,
        status: str | None = None,
        company: str | None = None,
        min_score: float | None = None,
    ) -> list[TrackerRow]:
        del min_score
        stmt = select(Application).order_by(Application.id)
        applications = self._session.exec(stmt).all()
        rows: list[TrackerRow] = []
        for application in applications:
            row = self._row_for_application(application)
            if status and row.status != status:
                continue
            if company and company.lower() not in row.company.lower():
                continue
            rows.append(row)
        return rows

    def render(self, rows: list[TrackerRow]) -> str:
        lines = [self.header, self.separator]
        for row in rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row.application_id),
                        _escape_cell(row.date),
                        _escape_cell(row.company),
                        _escape_cell(row.role),
                        _escape_cell(row.score),
                        _escape_cell(row.status),
                        _escape_cell(row.pdf),
                        _escape_cell(row.report),
                        _escape_cell(row.notes),
                    ]
                )
                + " |"
            )
        return "\n".join(lines) + "\n"

    def _row_for_application(self, application: Application) -> TrackerRow:
        job = self._session.get(Job, application.job_id)
        return TrackerRow(
            application_id=application.id or 0,
            date="",
            company="" if job is None else (job.company or ""),
            role="" if job is None else (job.title or ""),
            score="",
            status=tracker_status_for(application),
            pdf="",
            report=self._report_link(application),
            notes=application.notes or "",
        )

    def _report_link(self, application: Application) -> str:
        if application.id is None:
            return ""
        artifact = report_artifact_for_application(self._session, application.id)
        if artifact is None:
            return ""
        return f"[Report]({artifact.path})"


def tracker_status_for(application: Application) -> str:
    if application.tracker_status:
        validate_tracker_status(application.tracker_status)
        return application.tracker_status
    return APPLICATION_STATUS_TO_TRACKER[application.status]


def validate_tracker_status(status: str) -> str:
    if status not in TRACKER_STATUSES:
        raise ValueError(f"unsupported tracker status: {status}")
    return status


def set_tracker_status(session: Session, application_id: int, status: str) -> Application:
    validate_tracker_status(status)
    application = session.get(Application, application_id)
    if application is None:
        raise LookupError(f"application not found: id={application_id}")
    application.tracker_status = status
    session.add(application)
    session.commit()
    session.refresh(application)
    return application


def set_tracker_note(session: Session, application_id: int, note: str) -> Application:
    application = session.get(Application, application_id)
    if application is None:
        raise LookupError(f"application not found: id={application_id}")
    application.notes = note
    session.add(application)
    session.commit()
    session.refresh(application)
    return application


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
