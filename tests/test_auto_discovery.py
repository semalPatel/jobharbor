from jobharbor.services.auto_discovery import (
    DEFAULT_MOBILE_COMPANY_CAREER_URLS,
    default_provider_targets,
    discover_jobs_from_company_career_sites,
    discover_jobs_from_public_feeds,
    discover_provider_urls_from_search,
    expand_feed_jobs_with_provider_urls,
    extract_provider_targets,
    prefilter_jobs_for_mobile_focus,
)


def test_discover_jobs_from_public_feeds_parses_rss_items_with_any_apply_url() -> None:
    sample_rss = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
    <rss version=\"2.0\"><channel>
      <item>
        <title>Senior Backend Engineer at ExampleCo</title>
        <link>https://example.com/jobs/backend-1</link>
        <pubDate>Sat, 14 Mar 2026 12:00:00 GMT</pubDate>
        <description>Remote role</description>
      </item>
    </channel></rss>
    """

    def _fetch(_: str) -> str:
        return sample_rss

    jobs = discover_jobs_from_public_feeds(
        ["https://feed.example/jobs.rss"],
        fetch_text=_fetch,
    )

    assert len(jobs) == 1
    assert jobs[0]["source"] == "feed"
    assert jobs[0]["title"] == "Senior Backend Engineer at ExampleCo"
    assert jobs[0]["url"] == "https://example.com/jobs/backend-1"
    assert jobs[0]["external_id"]


def test_extract_provider_targets_includes_known_providers_and_ignores_generic_urls() -> None:
    targets = extract_provider_targets(
        [
            "https://boards.greenhouse.io/acme/jobs/123",
            "https://jobs.ashbyhq.com/zenith/abc",
            "https://jobs.lever.co/halcyon/xyz",
            "https://jobs.smartrecruiters.com/acme/123-mobile-engineer",
            "https://example.com/jobs/anything",
        ]
    )

    assert targets == {
        "greenhouse": {"acme"},
        "ashby": {"zenith"},
        "lever": {"halcyon"},
        "smartrecruiters": {"acme"},
    }


def test_discover_jobs_from_public_feeds_skips_failed_feed_and_continues() -> None:
    sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel>
      <item>
        <title>Role</title>
        <link>https://example.com/jobs/ok</link>
      </item>
    </channel></rss>
    """

    def _fetch(url: str) -> str:
        if "bad" in url:
            raise RuntimeError("forbidden")
        return sample_rss

    jobs = discover_jobs_from_public_feeds(
        ["https://bad.feed/jobs.rss", "https://good.feed/jobs.rss"],
        fetch_text=_fetch,
    )

    assert len(jobs) == 1
    assert jobs[0]["url"] == "https://example.com/jobs/ok"


def test_expand_feed_jobs_with_provider_urls_extracts_greenhouse_apply_links() -> None:
    jobs = [
        {
            "source": "feed",
            "external_id": "x",
            "title": "Android Engineer",
            "company": "Acme",
            "location": "Remote",
            "url": "https://news.example/job-1",
            "posted_at": "2026-03-14",
            "description": "Kotlin",
        }
    ]

    def _fetch(url: str) -> str:
        assert url == "https://news.example/job-1"
        return '<html><a href="https://boards.greenhouse.io/acme/jobs/12345">Apply</a></html>'

    expanded = expand_feed_jobs_with_provider_urls(jobs, fetch_text=_fetch, max_pages=10)

    assert len(expanded) == 1
    assert expanded[0]["source"] == "greenhouse"
    assert expanded[0]["url"] == "https://boards.greenhouse.io/acme/jobs/12345"


def test_discover_provider_urls_from_search_extracts_encoded_provider_urls() -> None:
    html = """
    <html>
      <a href="/l/?uddg=https%3A%2F%2Fboards.greenhouse.io%2Facme%2Fjobs%2F12345">
        Result 1
      </a>
      <a href="/l/?uddg=https%3A%2F%2Fjobs.lever.co%2Fbeta%2Fabcd-1234">
        Result 2
      </a>
    </html>
    """

    def _fetch(_: str) -> str:
        return html

    jobs = discover_provider_urls_from_search(
        include_keywords=("android", "kotlin"),
        fetch_text=_fetch,
        max_results_per_query=5,
    )

    urls = {job["url"] for job in jobs}
    assert "https://boards.greenhouse.io/acme/jobs/12345" in urls
    assert "https://jobs.lever.co/beta/abcd-1234" in urls
    assert {job["source"] for job in jobs} == {"greenhouse", "lever"}


def test_default_provider_targets_returns_seeded_provider_tokens() -> None:
    targets = default_provider_targets()
    assert "greenhouse" in targets
    assert "nearsure" in targets["greenhouse"]
    assert "lever" in targets


def test_discover_jobs_from_company_career_sites_extracts_job_links() -> None:
    html = """
    <html>
      <a href="/careers/mobile-engineer">Mobile Engineer</a>
      <a href="https://jobs.smartrecruiters.com/acme/ios-engineer">Apply</a>
      <a href="https://example.com/about">About</a>
    </html>
    """

    def _fetch(_: str) -> str:
        return html

    jobs = discover_jobs_from_company_career_sites(
        ["https://example.com/careers"],
        fetch_text=_fetch,
        max_job_links_per_site=10,
    )

    urls = {job["url"] for job in jobs}
    assert "https://example.com/careers/mobile-engineer" in urls
    assert "https://jobs.smartrecruiters.com/acme/ios-engineer" in urls


def test_expand_feed_jobs_with_provider_urls_extracts_workday_and_smartrecruiters() -> None:
    jobs = [
        {
            "source": "company_site",
            "external_id": "seed-1",
            "title": "Mobile Engineer",
            "company": "Acme",
            "location": "SF Bay Area",
            "url": "https://example.com/careers/mobile",
            "posted_at": "",
            "description": "mobile ios",
        }
    ]

    def _fetch(_: str) -> str:
        return """
        <html>
          <a href="https://acme.wd1.myworkdayjobs.com/en-US/Jobs/job/San-Francisco/Mobile-Engineer_123">Workday</a>
          <a href="https://jobs.smartrecruiters.com/acme/Mobile-Engineer">Smart</a>
        </html>
        """

    expanded = expand_feed_jobs_with_provider_urls(jobs, fetch_text=_fetch, max_pages=10)
    pairs = {(item["source"], item["url"]) for item in expanded}
    assert (
        "workday",
        "https://acme.wd1.myworkdayjobs.com/en-US/Jobs/job/San-Francisco/Mobile-Engineer_123",
    ) in pairs
    assert ("smartrecruiters", "https://jobs.smartrecruiters.com/acme/Mobile-Engineer") in pairs


def test_default_mobile_company_career_urls_contains_mobile_first_companies() -> None:
    assert "https://careers.doordash.com/" in DEFAULT_MOBILE_COMPANY_CAREER_URLS


def test_prefilter_jobs_for_mobile_focus_keeps_mobile_and_drops_irrelevant_roles() -> None:
    jobs = [
        {"title": "Senior Mobile Engineer", "description": "ios swift", "source": "lever"},
        {"title": "Finance Manager", "description": "accounting", "source": "lever"},
    ]

    filtered = prefilter_jobs_for_mobile_focus(jobs, include_keywords=("mobile", "ios"))
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Senior Mobile Engineer"
