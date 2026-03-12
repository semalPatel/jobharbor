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
