from sqlmodel import Session, select

from jobharbor.models import (
    ACTIVE_APPLICATION_STATUSES,
    Application,
    ApplicationStatus,
)


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(self, job_id: int) -> Application:
        existing_active = self._session.exec(
            select(Application.id)
            .where(Application.job_id == job_id)
            .where(Application.status.in_(ACTIVE_APPLICATION_STATUSES))
            .limit(1)
        ).first()
        if existing_active is not None:
            raise ValueError(f"active application already exists for job_id={job_id}")

        application = Application(job_id=job_id, status=ApplicationStatus.drafting)
        self._session.add(application)
        self._session.commit()
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

        application.status = to_status
        self._session.add(application)
        self._session.commit()
        self._session.refresh(application)
        return application
