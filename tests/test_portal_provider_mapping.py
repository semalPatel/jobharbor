from jobharbor.portal_config import infer_provider_from_url


def test_infers_greenhouse_provider_slug() -> None:
    assert infer_provider_from_url("https://job-boards.greenhouse.io/anthropic") == (
        "greenhouse",
        "anthropic",
    )
    assert infer_provider_from_url("https://boards.greenhouse.io/acme") == ("greenhouse", "acme")


def test_infers_ashby_provider_slug() -> None:
    assert infer_provider_from_url("https://jobs.ashbyhq.com/openai") == ("ashby", "openai")


def test_infers_lever_provider_slug() -> None:
    assert infer_provider_from_url("https://jobs.lever.co/palantir") == ("lever", "palantir")


def test_infers_smartrecruiters_provider_slug() -> None:
    assert infer_provider_from_url("https://jobs.smartrecruiters.com/acme/123") == (
        "smartrecruiters",
        "acme",
    )
