from collections.abc import Collection, Mapping, Sequence
import hashlib
from typing import Any

from sqlmodel import Session, select

from jobharbor.models import Job

DEFAULT_FINGERPRINT_FIELDS: tuple[str, ...] = (
    "title",
    "company",
    "location",
    "url",
)


def dedupe_fingerprint(
    job: Mapping[str, Any],
    *,
    fields: Sequence[str] = DEFAULT_FINGERPRINT_FIELDS,
) -> str:
    """Return a deterministic hash for normalized job content used in dedupe."""

    canonical = "\x1f".join(_normalize_value(job.get(field)) for field in fields)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_fingerprint_seen(fingerprint: str, seen_fingerprints: Collection[str]) -> bool:
    """True when a candidate fingerprint already exists in a dedupe set."""

    return fingerprint in seen_fingerprints


def job_exists(session: Session, *, source: str, external_id: str) -> bool:
    """True when the source/external_id pair already exists in persisted jobs."""

    stmt = select(Job.id).where(Job.source == source, Job.external_id == external_id).limit(1)
    return session.exec(stmt).first() is not None


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        return ""

    return " ".join(text.strip().lower().split())
