from sqlmodel import Session, SQLModel, create_engine

from jobharbor.models import Job
from jobharbor.services.dedupe import (
    dedupe_fingerprint,
    is_fingerprint_seen,
    job_exists,
)


def test_dedupe_fingerprint_is_stable_for_equivalent_normalized_job() -> None:
    job_a = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "url": "https://jobs.example.test/123",
    }
    job_b = {
        "url": "https://jobs.example.test/123",
        "location": " remote ",
        "company": "acme corp",
        "title": "  Senior Python Engineer  ",
    }

    assert dedupe_fingerprint(job_a) == dedupe_fingerprint(job_b)


def test_dedupe_fingerprint_preserves_url_case_sensitivity() -> None:
    upper_path = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "url": "https://jobs.example.test/Role/ABC123",
    }
    lower_path = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "url": "https://jobs.example.test/role/abc123",
    }

    assert dedupe_fingerprint(upper_path) != dedupe_fingerprint(lower_path)


def test_dedupe_fingerprint_changes_when_key_fields_change() -> None:
    baseline = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "url": "https://jobs.example.test/123",
    }
    changed = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "location": "Hybrid",
        "url": "https://jobs.example.test/123",
    }

    assert dedupe_fingerprint(baseline) != dedupe_fingerprint(changed)


def test_dedupe_fingerprint_non_scalar_content_changes_hash() -> None:
    baseline = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "location": {"region": "US", "remote": True},
        "url": "https://jobs.example.test/123",
    }
    changed = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "location": {"region": "CA", "remote": True},
        "url": "https://jobs.example.test/123",
    }

    assert dedupe_fingerprint(baseline) != dedupe_fingerprint(changed)


def test_dedupe_fingerprint_missing_fields_are_deterministic() -> None:
    with_missing = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "url": "https://jobs.example.test/123",
    }
    explicit_none = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "location": None,
        "url": "https://jobs.example.test/123",
    }

    assert dedupe_fingerprint(with_missing) == dedupe_fingerprint(explicit_none)


def test_is_fingerprint_seen_detects_duplicate_candidates() -> None:
    seen = {"abc123"}

    assert is_fingerprint_seen("abc123", seen) is True
    assert is_fingerprint_seen("different", seen) is False


def test_job_exists_checks_existing_source_external_id() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Job(source="greenhouse", external_id="gh-123"))
        session.commit()

        assert job_exists(session, source="greenhouse", external_id="gh-123") is True
        assert job_exists(session, source="ashby", external_id="gh-123") is False
        assert job_exists(session, source="greenhouse", external_id="gh-999") is False
