from collections import Counter
from pathlib import Path

from jobharbor.portal_config import CONNECTOR_PROVIDERS, build_portal_discovery_plan, load_portals_config


def test_loads_title_filter(tmp_path: Path) -> None:
    path = tmp_path / "portals.yml"
    path.write_text(
        """\
title_filter:
  positive:
    - AI
  negative:
    - Intern
  seniority_boost:
    - Senior
""",
        encoding="utf-8",
    )

    config = load_portals_config(path)

    assert config.title_filter.positive == ("AI",)
    assert config.title_filter.negative == ("Intern",)
    assert config.title_filter.seniority_boost == ("Senior",)


def test_loads_tracked_companies_and_normalizes_career_ops_fields(tmp_path: Path) -> None:
    path = tmp_path / "portals.yml"
    path.write_text(
        """\
tracked_companies:
  - name: Anthropic
    careers_url: https://job-boards.greenhouse.io/anthropic
    api: https://boards-api.greenhouse.io/v1/boards/anthropic/jobs
    enabled: true
  - name: OpenAI
    careers_url: https://openai.com/careers
    scan_method: websearch
    enabled: true
""",
        encoding="utf-8",
    )

    config = load_portals_config(path)

    assert config.tracked_companies[0].api_url == "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs"
    assert config.tracked_companies[0].scan_method == "api"
    assert config.tracked_companies[0].provider == "greenhouse"
    assert config.tracked_companies[0].provider_slug == "anthropic"
    assert config.tracked_companies[1].scan_method == "search"


def test_browser_only_company_is_skipped_without_browser_capability(tmp_path: Path) -> None:
    path = tmp_path / "portals.yml"
    path.write_text(
        """\
tracked_companies:
  - name: Browser Only
    careers_url: https://example.com/careers
    scan_method: browser
    enabled: true
""",
        encoding="utf-8",
    )

    plan = build_portal_discovery_plan(load_portals_config(path))

    assert plan.provider_targets == {}
    assert plan.skipped == ("Browser Only: missing capability browser",)


def test_greenhouse_api_company_builds_connector_target(tmp_path: Path) -> None:
    path = tmp_path / "portals.yml"
    path.write_text(
        """\
tracked_companies:
  - name: Anthropic
    careers_url: https://job-boards.greenhouse.io/anthropic
    api_url: https://boards-api.greenhouse.io/v1/boards/anthropic/jobs
    enabled: true
""",
        encoding="utf-8",
    )

    plan = build_portal_discovery_plan(load_portals_config(path))

    assert plan.provider_targets == {"greenhouse": {"anthropic"}}


def test_template_catalog_loads_full_career_ops_catalog() -> None:
    config = load_portals_config(Path("templates/portals.example.yml"))

    assert "AI" in config.title_filter.positive
    assert len(config.tracked_companies) == 76
    assert len(config.search_queries) == 19
    assert all(not query.enabled for query in config.search_queries)
    assert all("search" in query.requires for query in config.search_queries)


def test_template_enabled_companies_are_connector_safe_or_skipped() -> None:
    config = load_portals_config(Path("templates/portals.example.yml"))
    plan = build_portal_discovery_plan(config)
    provider_counts = Counter(company.provider for company in config.tracked_companies if company.enabled)

    assert provider_counts["greenhouse"] > 0
    assert provider_counts["ashby"] > 0
    assert provider_counts["lever"] > 0
    assert set(provider_counts).issubset(CONNECTOR_PROVIDERS)
    assert all(
        company.provider in plan.provider_targets and company.provider_slug in plan.provider_targets[company.provider]
        for company in config.tracked_companies
        if company.enabled
    )
