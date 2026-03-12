from jobharbor.services.filters import (
    ALLOW,
    REJECT_COMPANY_BLACKLIST,
    REJECT_DOMAIN_EXCLUDED_KEYWORD,
    REJECT_DOMAIN_NOT_INCLUDED_KEYWORD,
    REJECT_LOCATION_NOT_ALLOWED,
    REJECT_TITLE_BLACKLIST,
    REJECT_WORK_AUTH_NOT_ALLOWED,
    HardFilterPolicy,
    evaluate_hard_filters,
)


def test_hard_filters_accept_job_when_all_constraints_pass() -> None:
    policy = HardFilterPolicy(
        include_domain_keywords={"backend", "platform"},
        exclude_domain_keywords={"frontend"},
        company_blacklist={"bad co"},
        title_blacklist={"staff"},
        allowed_location_keywords={"remote", "new york"},
        allowed_work_auth={"us_authorized", "citizen"},
    )
    job = {
        "title": "Senior Backend Engineer",
        "company": "Acme",
        "location": "Remote - US",
        "description": "Build platform services",
        "work_auth": "us_authorized",
    }

    decision = evaluate_hard_filters(job, policy=policy)

    assert decision.passed is True
    assert decision.reason_code == ALLOW


def test_hard_filters_rejects_when_include_domain_keyword_missing() -> None:
    policy = HardFilterPolicy(include_domain_keywords={"backend", "platform"})
    job = {
        "title": "People Operations Manager",
        "description": "Own onboarding workflows",
    }

    decision = evaluate_hard_filters(job, policy=policy)

    assert decision.passed is False
    assert decision.reason_code == REJECT_DOMAIN_NOT_INCLUDED_KEYWORD


def test_hard_filters_rejects_when_domain_contains_excluded_keyword() -> None:
    policy = HardFilterPolicy(exclude_domain_keywords={"frontend"})
    job = {
        "title": "Senior Frontend Engineer",
        "description": "React UI ownership",
    }

    decision = evaluate_hard_filters(job, policy=policy)

    assert decision.passed is False
    assert decision.reason_code == REJECT_DOMAIN_EXCLUDED_KEYWORD


def test_hard_filters_rejects_blacklisted_company() -> None:
    policy = HardFilterPolicy(company_blacklist={"bad co", "downround inc"})
    job = {
        "title": "Senior Backend Engineer",
        "company": "Bad Co",
    }

    decision = evaluate_hard_filters(job, policy=policy)

    assert decision.passed is False
    assert decision.reason_code == REJECT_COMPANY_BLACKLIST


def test_hard_filters_rejects_blacklisted_title_keyword() -> None:
    policy = HardFilterPolicy(title_blacklist={"staff", "principal"})
    job = {
        "title": "Principal Engineer",
        "company": "Acme",
    }

    decision = evaluate_hard_filters(job, policy=policy)

    assert decision.passed is False
    assert decision.reason_code == REJECT_TITLE_BLACKLIST


def test_hard_filters_rejects_location_outside_allowed_keywords() -> None:
    policy = HardFilterPolicy(allowed_location_keywords={"remote", "new york"})
    job = {
        "title": "Backend Engineer",
        "location": "Berlin, Germany",
    }

    decision = evaluate_hard_filters(job, policy=policy)

    assert decision.passed is False
    assert decision.reason_code == REJECT_LOCATION_NOT_ALLOWED


def test_hard_filters_rejects_disallowed_work_auth() -> None:
    policy = HardFilterPolicy(allowed_work_auth={"us_authorized", "citizen"})
    job = {
        "title": "Backend Engineer",
        "work_auth": "requires_sponsorship",
    }

    decision = evaluate_hard_filters(job, policy=policy)

    assert decision.passed is False
    assert decision.reason_code == REJECT_WORK_AUTH_NOT_ALLOWED
