from __future__ import annotations

import json
from typing import Any, Protocol

from sqlmodel import Session, select

from jobharbor.models import Application, ApplicationStatus, Job, RunLog, RunStatus


class NotificationRouterProtocol(Protocol):
    def send(
        self,
        *,
        title: str,
        company: str,
        source: str,
        review_url: str,
    ) -> bool:
        ...


class NotifyStageWorker:
    def __init__(
        self,
        *,
        session: Session,
        notification_router: NotificationRouterProtocol,
        review_url_base: str = "http://localhost:8080/review/queue",
    ) -> None:
        self._session = session
        self._notification_router = notification_router
        self._review_url_base = review_url_base

    def run(self, context: dict[str, Any]) -> None:
        del context
        stmt = (
            select(Application)
            .where(Application.status == ApplicationStatus.ready_for_review)
            .order_by(Application.id)
        )
        for application in self._session.exec(stmt).all():
            if self._already_notified(app_id=application.id):
                continue

            job = self._session.get(Job, application.job_id)
            source = job.source if job is not None else "unknown"
            review_url = self._resolve_apply_url(app_id=application.id) or self._build_review_url(
                application.id
            )
            delivered = self._notification_router.send(
                title=f"Application {application.id} ready for review",
                company="unknown",
                source=source,
                review_url=review_url,
            )
            if delivered:
                self._mark_notified(app_id=application.id)

    def _build_review_url(self, app_id: int | None) -> str:
        if app_id is None:
            return self._review_url_base
        separator = "&" if "?" in self._review_url_base else "?"
        return f"{self._review_url_base}{separator}application_id={app_id}"

    def _already_notified(self, *, app_id: int | None) -> bool:
        source = self._notify_source(app_id=app_id)
        stmt = (
            select(RunLog.id)
            .where(RunLog.source == source)
            .where(RunLog.status == RunStatus.success)
            .limit(1)
        )
        return self._session.exec(stmt).first() is not None

    def _mark_notified(self, *, app_id: int | None) -> None:
        self._session.add(
            RunLog(
                source=self._notify_source(app_id=app_id),
                status=RunStatus.success,
                message="notification delivered",
            )
        )
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _resolve_apply_url(self, *, app_id: int | None) -> str | None:
        prefill_source = f"prefill:application:{app_id}"
        stmt = (
            select(RunLog)
            .where(RunLog.source == prefill_source)
            .order_by(RunLog.id.desc())
            .limit(1)
        )
        log = self._session.exec(stmt).first()
        if log is None or not log.message:
            return None
        try:
            payload = json.loads(log.message)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        apply_url = payload.get("apply_url")
        if isinstance(apply_url, str) and apply_url.strip():
            return apply_url.strip()
        return None

    @staticmethod
    def _notify_source(*, app_id: int | None) -> str:
        return f"notify:application:{app_id}"
