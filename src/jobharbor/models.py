from enum import Enum

from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel


class JobStatus(str, Enum):
    discovered = "discovered"
    normalized = "normalized"
    queued = "queued"
    skipped = "skipped"


class ApplicationStatus(str, Enum):
    drafting = "drafting"
    ready_for_review = "ready_for_review"
    submitted = "submitted"
    failed = "failed"
    abandoned = "abandoned"


ACTIVE_APPLICATION_STATUSES: tuple[ApplicationStatus, ...] = (
    ApplicationStatus.drafting,
    ApplicationStatus.ready_for_review,
)

ALLOWED_APPLICATION_TRANSITIONS: dict[ApplicationStatus, tuple[ApplicationStatus, ...]] = {
    ApplicationStatus.drafting: (
        ApplicationStatus.ready_for_review,
        ApplicationStatus.failed,
        ApplicationStatus.abandoned,
    ),
    ApplicationStatus.ready_for_review: (
        ApplicationStatus.submitted,
        ApplicationStatus.failed,
        ApplicationStatus.abandoned,
    ),
    ApplicationStatus.submitted: (),
    ApplicationStatus.failed: (ApplicationStatus.drafting,),
    ApplicationStatus.abandoned: (),
}


class RunStatus(str, Enum):
    started = "started"
    success = "success"
    partial_failure = "partial_failure"
    failed = "failed"


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    external_id: str = Field(index=True)
    status: JobStatus = Field(default=JobStatus.discovered, index=True)
    title: str | None = None
    company: str | None = None
    url: str | None = Field(default=None, index=True)
    location: str | None = None
    posted_at: str | None = None
    description: str | None = None
    provider: str | None = Field(default=None, index=True)
    source_url: str | None = None
    scan_query_name: str | None = None


class Application(SQLModel, table=True):
    __tablename__ = "applications"
    __table_args__ = (
        Index(
            "uq_applications_active_per_job",
            "job_id",
            unique=True,
            sqlite_where=text("status IN ('drafting', 'ready_for_review')"),
            postgresql_where=text("status IN ('drafting', 'ready_for_review')"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    status: ApplicationStatus = Field(default=ApplicationStatus.drafting, index=True)
    tracker_status: str | None = Field(default=None, index=True)
    notes: str | None = None


class RunLog(SQLModel, table=True):
    __tablename__ = "run_logs"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    status: RunStatus = Field(default=RunStatus.started, index=True)
    message: str | None = None
