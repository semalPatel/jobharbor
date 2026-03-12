import math

import pytest

from jobharbor.services.ranking import compute_job_score, is_job_eligible


def test_compute_job_score_increases_with_target_keyword_coverage() -> None:
    target_keywords = {"python", "backend", "platform", "distributed"}

    low_coverage_job = {
        "title": "Software Engineer",
        "description": "Build internal tools",
    }
    high_coverage_job = {
        "title": "Senior Backend Python Engineer",
        "description": "Build distributed platform services",
    }

    low_score = compute_job_score(low_coverage_job, target_keywords=target_keywords)
    high_score = compute_job_score(high_coverage_job, target_keywords=target_keywords)

    assert high_score > low_score


def test_compute_job_score_distinguishes_c_plus_plus_and_c_sharp() -> None:
    target_keywords = {"c++", "c#"}

    c_plus_plus_job = {
        "title": "Senior C++ Engineer",
        "description": "Build low-latency services",
    }
    c_sharp_job = {
        "title": "Senior C# Engineer",
        "description": "Build internal tooling",
    }

    c_plus_plus_score = compute_job_score(c_plus_plus_job, target_keywords=target_keywords)
    c_sharp_score = compute_job_score(c_sharp_job, target_keywords=target_keywords)

    assert c_plus_plus_score == 0.5
    assert c_sharp_score == 0.5


def test_compute_job_score_requires_contiguous_phrase_matches() -> None:
    target_keywords = {"machine learning"}

    contiguous_job = {
        "title": "Machine Learning Engineer",
        "description": "Build ranking models",
    }
    split_job = {
        "title": "Machine Engineer",
        "description": "Design distributed learning systems",
    }

    assert compute_job_score(contiguous_job, target_keywords=target_keywords) == 1.0
    assert compute_job_score(split_job, target_keywords=target_keywords) == 0.0


def test_is_job_eligible_applies_minimum_threshold_gate() -> None:
    target_keywords = {"python", "backend", "platform", "distributed"}
    job = {
        "title": "Backend Python Engineer",
        "description": "Work on platform reliability",
    }

    score = compute_job_score(job, target_keywords=target_keywords)

    assert score == 0.75
    assert is_job_eligible(score, minimum_threshold=0.75) is True
    assert is_job_eligible(score, minimum_threshold=0.8) is False


@pytest.mark.parametrize("score", [-0.01, 1.01, math.nan, math.inf, -math.inf])
def test_is_job_eligible_rejects_invalid_score(score: float) -> None:
    with pytest.raises(ValueError, match="score"):
        is_job_eligible(score, minimum_threshold=0.5)


@pytest.mark.parametrize("minimum_threshold", [-0.01, 1.01, math.nan, math.inf, -math.inf])
def test_is_job_eligible_rejects_invalid_minimum_threshold(minimum_threshold: float) -> None:
    with pytest.raises(ValueError, match="minimum_threshold"):
        is_job_eligible(0.5, minimum_threshold=minimum_threshold)
