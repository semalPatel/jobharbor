from sqlmodel import Session, select

from jobharbor.models import (
    ACTIVE_APPLICATION_STATUSES,
    ALLOWED_APPLICATION_TRANSITIONS,
    Application,
    ApplicationStatus,
)


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(self, job_id: int) -> Application:
        if self._has_other_active_application(job_id=job_id):
            raise ValueError(f"active application already exists for job_id={job_id}")

        application = Application(job_id=job_id, status=ApplicationStatus.drafting)
        self._session.add(application)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        self._session.refresh(application)
        return application

    def list_ready_for_review(self, limit: int, offset: int) -> list[Application]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        stmt = (
            select(Application)
            .where(Application.status == ApplicationStatus.ready_for_review)
            .order_by(Application.id)
            .offset(offset)
            .limit(limit)
        )
        return list(self._session.exec(stmt).all())

    def transition_status(self, app_id: int, to_status: ApplicationStatus) -> Application:
        application = self._session.get(Application, app_id)
        if application is None:
            raise LookupError(f"application not found: id={app_id}")

        self._ensure_transition_allowed(from_status=application.status, to_status=to_status)
        if to_status in ACTIVE_APPLICATION_STATUSES and self._has_other_active_application(
            job_id=application.job_id,
            excluded_app_id=application.id,
        ):
            raise ValueError(f"active application already exists for job_id={application.job_id}")

        application.status = to_status
        self._session.add(application)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        self._session.refresh(application)
        return application

    def _has_other_active_application(self, *, job_id: int, excluded_app_id: int | None = None) -> bool:
        stmt = (
            select(Application.id)
            .where(Application.job_id == job_id)
            .where(Application.status.in_(ACTIVE_APPLICATION_STATUSES))
        )
        if excluded_app_id is not None:
            stmt = stmt.where(Application.id != excluded_app_id)
        return self._session.exec(stmt.limit(1)).first() is not None

    def _ensure_transition_allowed(
        self,
        *,
        from_status: ApplicationStatus,
        to_status: ApplicationStatus,
    ) -> None:
        if from_status == to_status:
            return

        allowed = ALLOWED_APPLICATION_TRANSITIONS[from_status]
        if to_status not in allowed:
            raise ValueError(
                f"disallowed transition from {from_status.value} to {to_status.value}"
            )
