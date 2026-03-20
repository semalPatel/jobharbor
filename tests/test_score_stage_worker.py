from jobharbor.workers.score_stage import ScoreStageWorker


class _Settings:
    include_domain_keywords = ("mobile",)
    exclude_domain_keywords = ()
    allowed_location_keywords = ()
    allowed_work_auth = ()
    connector_rollout = ("greenhouse", "ashby", "lever", "ycombinator")


def test_score_stage_allows_workday_and_smartrecruiters_with_explicit_rollout() -> None:
    worker = ScoreStageWorker(settings=_Settings())
    context = {
        "deduped_jobs": [
            {
                "source": "workday",
                "title": "Mobile Engineer",
                "description": "mobile apps",
                "location": "San Francisco",
                "work_auth": "",
            },
            {
                "source": "smartrecruiters",
                "title": "Senior Mobile Engineer",
                "description": "mobile platform",
                "location": "Remote",
                "work_auth": "",
            },
        ]
    }

    worker.run(context)
    eligible = context.get("eligible_jobs", [])
    assert isinstance(eligible, list)
    assert len(eligible) == 2

