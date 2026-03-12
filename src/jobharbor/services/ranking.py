from collections.abc import Mapping, Sequence, Set
import re
from typing import Any

DEFAULT_SCORING_FIELDS: tuple[str, ...] = (
    "title",
    "description",
    "team",
    "department",
)


def compute_job_score(
    job: Mapping[str, Any],
    *,
    target_keywords: Set[str],
    fields: Sequence[str] = DEFAULT_SCORING_FIELDS,
) -> float:
    """Return keyword-coverage score in the range [0.0, 1.0]."""

    normalized_keywords = _normalize_terms(target_keywords)
    if not normalized_keywords:
        return 0.0

    searchable_tokens = _tokenize(_join_text(*(job.get(field) for field in fields)))
    matched_keywords = sum(
        1
        for keyword in normalized_keywords
        if _contains_phrase(searchable_tokens, _tokenize(keyword))
    )
    return matched_keywords / len(normalized_keywords)


def is_job_eligible(score: float, *, minimum_threshold: float) -> bool:
    """Return True when score satisfies the minimum threshold policy."""

    return score >= minimum_threshold


def _contains_phrase(tokens: tuple[str, ...], phrase_tokens: tuple[str, ...]) -> bool:
    if not tokens or not phrase_tokens:
        return False
    phrase_len = len(phrase_tokens)
    if phrase_len > len(tokens):
        return False
    for idx in range(len(tokens) - phrase_len + 1):
        if tokens[idx : idx + phrase_len] == phrase_tokens:
            return True
    return False


def _join_text(*values: Any) -> str:
    return " ".join(_as_text(value) for value in values if _as_text(value))


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _tokenize(text: str) -> tuple[str, ...]:
    if not text:
        return ()
    return tuple(text.split(" "))


def _normalize_terms(terms: Set[str]) -> set[str]:
    return {normalized for term in terms if (normalized := _as_text(term))}
