from collections.abc import Mapping, Set
from dataclasses import dataclass, field
from typing import Any

ALLOW = "ALLOW"
REJECT_DOMAIN_NOT_INCLUDED_KEYWORD = "REJECT_DOMAIN_NOT_INCLUDED_KEYWORD"
REJECT_DOMAIN_EXCLUDED_KEYWORD = "REJECT_DOMAIN_EXCLUDED_KEYWORD"
REJECT_COMPANY_BLACKLIST = "REJECT_COMPANY_BLACKLIST"
REJECT_TITLE_BLACKLIST = "REJECT_TITLE_BLACKLIST"
REJECT_LOCATION_NOT_ALLOWED = "REJECT_LOCATION_NOT_ALLOWED"
REJECT_WORK_AUTH_NOT_ALLOWED = "REJECT_WORK_AUTH_NOT_ALLOWED"


@dataclass(frozen=True)
class HardFilterPolicy:
    include_domain_keywords: Set[str] = field(default_factory=frozenset)
    exclude_domain_keywords: Set[str] = field(default_factory=frozenset)
    company_blacklist: Set[str] = field(default_factory=frozenset)
    title_blacklist: Set[str] = field(default_factory=frozenset)
    allowed_location_keywords: Set[str] = field(default_factory=frozenset)
    allowed_work_auth: Set[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class FilterDecision:
    passed: bool
    reason_code: str


def evaluate_hard_filters(job: Mapping[str, Any], *, policy: HardFilterPolicy) -> FilterDecision:
    domain_text = _join_text(
        job.get("title"),
        job.get("description"),
        job.get("team"),
        job.get("department"),
    )
    excluded_keywords = _normalize_terms(policy.exclude_domain_keywords)
    if excluded_keywords and _contains_any(domain_text, excluded_keywords):
        return FilterDecision(passed=False, reason_code=REJECT_DOMAIN_EXCLUDED_KEYWORD)

    included_keywords = _normalize_terms(policy.include_domain_keywords)
    if included_keywords and not _contains_any(domain_text, included_keywords):
        return FilterDecision(passed=False, reason_code=REJECT_DOMAIN_NOT_INCLUDED_KEYWORD)

    company_blacklist = _normalize_terms(policy.company_blacklist)
    if company_blacklist and _as_text(job.get("company")) in company_blacklist:
        return FilterDecision(passed=False, reason_code=REJECT_COMPANY_BLACKLIST)

    title_blacklist = _normalize_terms(policy.title_blacklist)
    if title_blacklist and _contains_any(_as_text(job.get("title")), title_blacklist):
        return FilterDecision(passed=False, reason_code=REJECT_TITLE_BLACKLIST)

    allowed_locations = _normalize_terms(policy.allowed_location_keywords)
    if allowed_locations and not _contains_any(_as_text(job.get("location")), allowed_locations):
        return FilterDecision(passed=False, reason_code=REJECT_LOCATION_NOT_ALLOWED)

    allowed_work_auth = _normalize_terms(policy.allowed_work_auth)
    if allowed_work_auth and _as_text(job.get("work_auth")) not in allowed_work_auth:
        return FilterDecision(passed=False, reason_code=REJECT_WORK_AUTH_NOT_ALLOWED)

    return FilterDecision(passed=True, reason_code=ALLOW)


def _contains_any(text: str, terms: Set[str]) -> bool:
    return any(term in text for term in terms)


def _join_text(*values: Any) -> str:
    parts = [_as_text(value) for value in values]
    return " ".join(part for part in parts if part)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _normalize_terms(terms: Set[str]) -> set[str]:
    return {normalized for term in terms if (normalized := _as_text(term))}
