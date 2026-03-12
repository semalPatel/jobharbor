from collections.abc import Collection, Mapping, Sequence, Set
import hashlib
import json
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

    canonical = "\x1f".join(_normalize_value(field, job.get(field)) for field in fields)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_fingerprint_seen(fingerprint: str, seen_fingerprints: Collection[str]) -> bool:
    """True when a candidate fingerprint already exists in a dedupe set."""

    return fingerprint in seen_fingerprints


def job_exists(session: Session, *, source: str, external_id: str) -> bool:
    """True when the source/external_id pair already exists in persisted jobs."""

    stmt = select(Job.id).where(Job.source == source, Job.external_id == external_id).limit(1)
    return session.exec(stmt).first() is not None


def _normalize_value(field: str, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        if field == "url":
            # URL path/query can be case-sensitive, so do not lowercase.
            return value.strip()
        return " ".join(value.strip().lower().split())
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(_to_stable_json(value), sort_keys=True, separators=(",", ":"))


def _to_stable_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _to_stable_json(nested)
            for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_stable_json(item) for item in value]
    if isinstance(value, Set):
        normalized = [_to_stable_json(item) for item in value]
        normalized.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        return normalized
    return str(value)
