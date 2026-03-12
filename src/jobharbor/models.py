from enum import Enum

from sqlalchemy import UniqueConstraint
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


class Application(SQLModel, table=True):
    __tablename__ = "applications"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    status: ApplicationStatus = Field(default=ApplicationStatus.drafting, index=True)


class RunLog(SQLModel, table=True):
    __tablename__ = "run_logs"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    status: RunStatus = Field(default=RunStatus.started, index=True)
    message: str | None = None
