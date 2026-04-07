from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from jobharbor.models import Application, ApplicationStatus, Job, JobStatus
from jobharbor.repositories.application_repo import ApplicationRepository


class QueueStageWorker:
    def __init__(self, *, session: Session) -> None:
        self._session = session
        self._repo = ApplicationRepository(session)

    def run(self, context: dict[str, Any]) -> None:
        eligible = context.get("eligible_jobs")
        if not isinstance(eligible, list):
            context["queued_items"] = []
            return

        queued_items: list[dict[str, Any]] = []
        for item in eligible:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "")).strip()
            external_id = str(item.get("external_id", "")).strip()
            if not source or not external_id:
                continue

            job = self._get_or_create_job(item, source=source, external_id=external_id)
            app_id = self._enqueue_or_get_drafting(job_id=job.id)
            if app_id is None:
                continue

            queued_items.append({"app_id": app_id, "job": item})

        context["queued_items"] = queued_items

    def _get_or_create_job(self, item: dict[str, Any], *, source: str, external_id: str) -> Job:
        stmt = select(Job).where(Job.source == source, Job.external_id == external_id).limit(1)
        existing = self._session.exec(stmt).first()
        if existing is not None:
            self._populate_job_details(existing, item)
            self._session.add(existing)
            self._session.commit()
            self._session.refresh(existing)
            return existing

        job = Job(source=source, external_id=external_id, status=JobStatus.queued)
        self._populate_job_details(job, item)
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def _enqueue_or_get_drafting(self, *, job_id: int | None) -> int | None:
        if job_id is None:
            return None
        try:
            app = self._repo.enqueue(job_id)
            return app.id
        except ValueError:
            stmt = (
                select(Application)
                .where(Application.job_id == job_id)
                .where(Application.status == ApplicationStatus.drafting)
                .order_by(Application.id.desc())
                .limit(1)
            )
            existing = self._session.exec(stmt).first()
            return None if existing is None else existing.id

    def _populate_job_details(self, job: Job, item: dict[str, Any]) -> None:
        for field_name in (
            "title",
            "company",
            "url",
            "location",
            "posted_at",
            "description",
            "provider",
            "source_url",
            "scan_query_name",
        ):
            value = self._optional_text(item.get(field_name))
            if value is not None:
                setattr(job, field_name, value)
        if job.provider is None:
            job.provider = job.source
        if job.source_url is None:
            job.source_url = job.url

    def _optional_text(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
