from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlmodel import select
from pydantic import BaseModel
from sqlmodel import Session

from jobharbor.config import Settings
from jobharbor.db import get_session
from jobharbor.models import Application, ApplicationStatus, Evaluation, Job
from jobharbor.repositories.application_repo import ApplicationRepository
from jobharbor.reports import report_artifact_for_application
from jobharbor.tracker import TrackerExportService, set_tracker_note, tracker_status_for
from jobharbor.workspace import WorkspacePaths

router = APIRouter(prefix="/review", tags=["review"])


class ReviewApplicationResponse(BaseModel):
    id: int
    job_id: int
    status: ApplicationStatus
    title: str | None = None
    company: str | None = None
    url: str | None = None
    location: str | None = None
    execution_status: str
    tracker_status: str
    score: float | None = None
    recommendation: str | None = None
    source: str | None = None
    pdf: str | None = None
    report: str | None = None
    notes: str | None = None


class ReviewNoteRequest(BaseModel):
    note: str


@router.get("/queue", response_model=list[ReviewApplicationResponse])
def get_review_queue(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[ReviewApplicationResponse]:
    repository = ApplicationRepository(session)
    applications = repository.list_ready_for_review(limit=limit, offset=offset)
    return [_response_for_application(application, session=session) for application in applications]


@router.get("/applications", response_model=list[ReviewApplicationResponse])
def get_review_applications(
    status: ApplicationStatus | None = None,
    session: Session = Depends(get_session),
) -> list[ReviewApplicationResponse]:
    stmt = select(Application).order_by(Application.id)
    if status is not None:
        stmt = stmt.where(Application.status == status)
    applications = session.exec(stmt).all()
    return [_response_for_application(application, session=session) for application in applications]


@router.get("/dashboard", response_class=HTMLResponse)
def review_dashboard(session: Session = Depends(get_session)) -> HTMLResponse:
    rows = get_review_applications(session=session)
    body_rows = "\n".join(_dashboard_row(row) for row in rows)
    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Jobharbor Review</title>
    <style>
      body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #111827; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border-bottom: 1px solid #d1d5db; padding: 0.5rem; text-align: left; }}
      a {{ color: #0f766e; }}
    </style>
  </head>
  <body>
    <h1>Jobharbor Review</h1>
    <table>
      <thead>
        <tr><th>ID</th><th>Company</th><th>Role</th><th>Location</th><th>Score</th><th>Recommendation</th><th>Execution</th><th>Tracker</th><th>Job</th><th>Report</th><th>PDF</th><th>Notes</th><th>Actions</th></tr>
      </thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
  </body>
</html>"""
    return HTMLResponse(html)


@router.post("/{application_id}/submitted", response_model=ReviewApplicationResponse)
def mark_submitted(
    application_id: int,
    session: Session = Depends(get_session),
) -> ReviewApplicationResponse:
    repository = ApplicationRepository(session)
    try:
        application = repository.transition_status(application_id, ApplicationStatus.submitted)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _regenerate_tracker_export(session)
    return _response_for_application(application, session=session)


@router.post("/{application_id}/discarded", response_model=ReviewApplicationResponse)
def mark_discarded(
    application_id: int,
    session: Session = Depends(get_session),
) -> ReviewApplicationResponse:
    repository = ApplicationRepository(session)
    try:
        application = repository.transition_status(application_id, ApplicationStatus.abandoned)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _regenerate_tracker_export(session)
    return _response_for_application(application, session=session)


@router.post("/{application_id}/note", response_model=ReviewApplicationResponse)
def update_note(
    application_id: int,
    request: ReviewNoteRequest,
    session: Session = Depends(get_session),
) -> ReviewApplicationResponse:
    try:
        application = set_tracker_note(session, application_id, request.note)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _regenerate_tracker_export(session)
    return _response_for_application(application, session=session)


def _response_for_application(application, *, session: Session) -> ReviewApplicationResponse:
    job = session.get(Job, application.job_id)
    evaluation = _latest_evaluation(session, application)
    return ReviewApplicationResponse(
        id=application.id,
        job_id=application.job_id,
        status=application.status,
        title=None if job is None else job.title,
        company=None if job is None else job.company,
        url=None if job is None else job.url,
        location=None if job is None else job.location,
        execution_status=application.status.value,
        tracker_status=tracker_status_for(application),
        score=None if evaluation is None else evaluation.score,
        recommendation=None if evaluation is None else evaluation.recommendation,
        source=None if job is None else job.source,
        pdf=_artifact_path(session, application, "pdf"),
        report=_artifact_path(session, application, "report"),
        notes=application.notes,
    )


def _artifact_path(session: Session, application: Application, kind: str) -> str | None:
    if application.id is None:
        return None
    artifact = report_artifact_for_application(session, application.id, kind=kind)
    return None if artifact is None else artifact.path


def _latest_evaluation(session: Session, application: Application) -> Evaluation | None:
    if application.id is None:
        return None
    stmt = (
        select(Evaluation)
        .where(Evaluation.application_id == application.id)
        .order_by(Evaluation.id.desc())
        .limit(1)
    )
    return session.exec(stmt).first()


def _dashboard_row(row: ReviewApplicationResponse) -> str:
    job_link = _link(row.url, "Job") if row.url else ""
    report_link = _link(row.report, "Report") if row.report else ""
    pdf_link = _link(row.pdf, "PDF") if row.pdf else ""
    return (
        "<tr>"
        f"<td>{row.id}</td>"
        f"<td>{escape(row.company or '')}</td>"
        f"<td>{escape(row.title or '')}</td>"
        f"<td>{escape(row.location or '')}</td>"
        f"<td>{'' if row.score is None else escape(str(row.score))}</td>"
        f"<td>{escape(row.recommendation or '')}</td>"
        f"<td>{escape(row.execution_status)}</td>"
        f"<td>{escape(row.tracker_status)}</td>"
        f"<td>{job_link}</td>"
        f"<td>{report_link}</td>"
        f"<td>{pdf_link}</td>"
        f"<td>{escape(row.notes or '')}</td>"
        f"<td>{_action_buttons(row.id)}</td>"
        "</tr>"
    )


def _link(href: str | None, label: str) -> str:
    if not href:
        return ""
    return f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'


def _action_buttons(application_id: int) -> str:
    return (
        f'<form method="post" action="/review/{application_id}/submitted" style="display:inline">'
        '<button type="submit">Mark Applied</button>'
        "</form> "
        f'<form method="post" action="/review/{application_id}/discarded" style="display:inline">'
        '<button type="submit">Discard</button>'
        "</form>"
    )


def _regenerate_tracker_export(session: Session) -> None:
    paths = WorkspacePaths.from_settings(Settings())
    if not paths.root.exists():
        return
    TrackerExportService(session).export_applications(paths.applications_md)
