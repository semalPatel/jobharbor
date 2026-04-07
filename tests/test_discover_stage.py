from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine, select

from jobharbor.models import Job
from jobharbor.scan_history import ScanHistoryWriter
from jobharbor.workers.discover_stage import DiscoverStageWorker


class _FakeConnector:
    def __init__(self, rows):
        self._rows = rows

    def fetch_jobs(self):
        return list(self._rows)


class _Settings:
    connector_rollout: tuple[str, ...] = ()
    jobharbor_home = None
    discovery_capabilities: tuple[str, ...] = ("http",)


def test_discover_stage_persists_feed_jobs_with_non_provider_urls() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    def _feed_fetcher(*, feed_urls):
        assert feed_urls
        return [
            {
                "source": "feed",
                "external_id": "feed-1",
                "title": "Role A",
                "company": "X",
                "location": "Remote",
                "url": "https://example.com/jobs/1",
                "posted_at": "2026-03-14",
            }
        ]

    with Session(engine) as session:
        worker = DiscoverStageWorker(
            session=session,
            settings=_Settings(),
            feed_urls=("https://feed.example/jobs.rss",),
            feed_fetcher=_feed_fetcher,
            company_site_urls=(),
            search_fetcher=lambda **_: [],
            connector_builder=lambda **_: [],
        )

        worker.run({})

        jobs = list(session.exec(select(Job)).all())
        assert len(jobs) == 1
        assert jobs[0].source == "feed"
        assert jobs[0].external_id == "feed-1"
        assert jobs[0].title == "Role A"
        assert jobs[0].company == "X"
        assert jobs[0].url == "https://example.com/jobs/1"
        assert jobs[0].location == "Remote"
        assert jobs[0].posted_at == "2026-03-14"
        assert jobs[0].provider == "feed"
        assert jobs[0].source_url == "https://example.com/jobs/1"


def test_discover_stage_dedupes_existing_jobs() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Job(source="feed", external_id="feed-1"))
        session.commit()

        worker = DiscoverStageWorker(
            session=session,
            settings=_Settings(),
            feed_urls=("https://feed.example/jobs.rss",),
            feed_fetcher=lambda **_: [
                {
                    "source": "feed",
                    "external_id": "feed-1",
                    "title": "Role A",
                    "company": "X",
                    "location": "Remote",
                    "url": "https://example.com/jobs/1",
                    "posted_at": "2026-03-14",
                }
            ],
            company_site_urls=(),
            search_fetcher=lambda **_: [],
            connector_builder=lambda **_: [],
        )

        worker.run({})

        jobs = list(session.exec(select(Job)).all())
        assert len(jobs) == 1


def test_discover_stage_adds_provider_connector_results() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        worker = DiscoverStageWorker(
            session=session,
            settings=_Settings(),
            feed_urls=("https://feed.example/jobs.rss",),
            feed_fetcher=lambda **_: [
                {
                    "source": "feed",
                    "external_id": "feed-1",
                    "title": "Role A",
                    "company": "X",
                    "location": "Remote",
                    "url": "https://boards.greenhouse.io/acme/jobs/1",
                    "posted_at": "2026-03-14",
                }
            ],
            company_site_urls=(),
            search_fetcher=lambda **_: [],
            connector_builder=lambda **_: [
                (
                    "greenhouse",
                    _FakeConnector(
                        [
                            {
                                "external_id": "gh-1",
                                "title": "Role G",
                                "company": "G",
                                "location": "Remote",
                                "url": "https://boards.greenhouse.io/acme/jobs/2",
                                "posted_at": "2026-03-14",
                            }
                        ]
                    ),
                )
            ],
        )

        worker.run({})

        jobs = list(session.exec(select(Job).order_by(Job.source, Job.external_id)).all())
        assert [(j.source, j.external_id) for j in jobs] == [
            ("feed", "feed-1"),
            ("greenhouse", "gh-1"),
        ]


def test_discover_stage_uses_search_seed_urls_to_build_provider_targets() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    captured_targets: dict[str, set[str]] = {}

    class _SearchSettings(_Settings):
        discovery_capabilities = ("http", "search")

    def _connector_builder(*, targets, rollout):
        del rollout
        captured_targets.update({k: set(v) for k, v in targets.items()})
        return []

    with Session(engine) as session:
        worker = DiscoverStageWorker(
                session=session,
                settings=_SearchSettings(),
            feed_urls=("https://feed.example/jobs.rss",),
            feed_fetcher=lambda **_: [],
            company_site_urls=(),
            search_fetcher=lambda **_: [
                {
                    "source": "greenhouse",
                    "external_id": "seed-1",
                    "title": "Android Engineer",
                    "company": "",
                    "location": "Remote",
                    "url": "https://boards.greenhouse.io/acme/jobs/1",
                    "posted_at": "",
                    "description": "",
                }
            ],
            connector_builder=_connector_builder,
        )

        worker.run({})

        assert "greenhouse" in captured_targets
        assert "acme" in captured_targets["greenhouse"]


def test_discover_stage_build_connectors_includes_ycombinator_when_requested() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        worker = DiscoverStageWorker(
            session=session,
            settings=_Settings(),
            feed_urls=("https://feed.example/jobs.rss",),
            feed_fetcher=lambda **_: [],
        )

        connectors = worker._build_connectors(  # noqa: SLF001 - covered behavior for rollout wiring
            targets={},
            rollout=("ycombinator",),
        )

        assert [source for source, _ in connectors] == ["ycombinator"]


def test_discover_stage_build_connectors_includes_smartrecruiters_when_requested() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        worker = DiscoverStageWorker(
            session=session,
            settings=_Settings(),
            feed_urls=("https://feed.example/jobs.rss",),
            feed_fetcher=lambda **_: [],
        )

        connectors = worker._build_connectors(  # noqa: SLF001 - covered behavior for rollout wiring
            targets={"smartrecruiters": {"acme"}},
            rollout=("smartrecruiters",),
        )

        assert [source for source, _ in connectors] == ["smartrecruiters"]


def test_discover_stage_uses_company_site_seed_urls_for_targets() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    captured_targets: dict[str, set[str]] = {}

    def _connector_builder(*, targets, rollout):
        del rollout
        captured_targets.update({k: set(v) for k, v in targets.items()})
        return []

    with Session(engine) as session:
        worker = DiscoverStageWorker(
            session=session,
            settings=_Settings(),
            feed_urls=("https://feed.example/jobs.rss",),
            feed_fetcher=lambda **_: [],
            company_site_fetcher=lambda **_: [
                {
                    "source": "company_site",
                    "external_id": "company-1",
                    "title": "Mobile",
                    "company": "Example",
                    "location": "",
                    "url": "https://jobs.lever.co/acme/mobile-engineer",
                    "posted_at": "",
                    "description": "mobile",
                }
            ],
            search_fetcher=lambda **_: [],
            connector_builder=_connector_builder,
        )
        worker.run({})

    assert "lever" in captured_targets
    assert "acme" in captured_targets["lever"]


def test_discover_stage_uses_portals_yml_targets_when_present(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    (tmp_path / "portals.yml").write_text(
        """\
tracked_companies:
  - name: Anthropic
    careers_url: https://job-boards.greenhouse.io/anthropic
    api_url: https://boards-api.greenhouse.io/v1/boards/anthropic/jobs
    enabled: true
  - name: Browser Only
    careers_url: https://example.com/careers
    scan_method: browser
    enabled: true
""",
        encoding="utf-8",
    )
    captured_targets: dict[str, set[str]] = {}

    class _PortalSettings(_Settings):
        jobharbor_home = tmp_path

    def _connector_builder(*, targets, rollout):
        del rollout
        captured_targets.update({k: set(v) for k, v in targets.items()})
        return []

    with Session(engine) as session:
        worker = DiscoverStageWorker(
            session=session,
            settings=_PortalSettings(),
            feed_urls=("https://feed.example/jobs.rss",),
            feed_fetcher=lambda **_: [],
            company_site_urls=(),
            search_fetcher=lambda **_: [],
            connector_builder=_connector_builder,
        )
        context: dict[str, object] = {}

        worker.run(context)

    assert captured_targets == {"greenhouse": {"anthropic"}}
    assert context["portal_config_skipped"] == ("Browser Only: missing capability browser",)


def test_discover_stage_records_scan_history_for_added_duplicate_and_skipped(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    (tmp_path / "portals.yml").write_text(
        """\
tracked_companies:
  - name: Browser Only
    careers_url: https://example.com/careers
    scan_method: browser
    enabled: true
""",
        encoding="utf-8",
    )

    class _PortalSettings(_Settings):
        jobharbor_home = tmp_path

    with Session(engine) as session:
        session.add(Job(source="feed", external_id="feed-duplicate"))
        session.commit()
        worker = DiscoverStageWorker(
            session=session,
            settings=_PortalSettings(),
            feed_fetcher=lambda **_: [
                {
                    "source": "feed",
                    "external_id": "feed-duplicate",
                    "url": "https://example.com/duplicate",
                },
                {
                    "source": "feed",
                    "external_id": "feed-added",
                    "url": "https://example.com/added",
                    "title": "AI Engineer",
                    "company": "Acme",
                },
            ],
            company_site_urls=(),
            search_fetcher=lambda **_: [],
            connector_builder=lambda **_: [],
            scan_history_writer=ScanHistoryWriter(tmp_path / "data" / "scan-history.tsv"),
        )

        worker.run({})

    history = (tmp_path / "data" / "scan-history.tsv").read_text(encoding="utf-8")
    assert "skipped_capability" in history
    assert "skipped_dup" in history
    assert "added" in history


def test_discover_stage_does_not_fallback_to_default_search_when_portals_have_no_enabled_queries(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    (tmp_path / "portals.yml").write_text(
        """\
search_queries:
  - name: Disabled Search
    query: site:jobs.ashbyhq.com acme
    enabled: false
    requires:
      - search
tracked_companies:
  - name: Acme
    careers_url: https://jobs.ashbyhq.com/acme
    enabled: true
""",
        encoding="utf-8",
    )
    search_called = False

    class _PortalSearchSettings(_Settings):
        jobharbor_home = tmp_path
        discovery_capabilities = ("http", "search")

    def _search_fetcher(**_):
        nonlocal search_called
        search_called = True
        return []

    with Session(engine) as session:
        worker = DiscoverStageWorker(
            session=session,
            settings=_PortalSearchSettings(),
            feed_fetcher=lambda **_: [],
            company_site_urls=(),
            search_fetcher=_search_fetcher,
            connector_builder=lambda **_: [],
        )
        worker.run({})

    assert search_called is False
