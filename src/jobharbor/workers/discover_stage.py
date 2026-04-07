from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import json
from urllib import request as urllib_request

from sqlmodel import Session

from jobharbor.connectors.ashby import AshbyConnector
from jobharbor.connectors.base import JobConnector
from jobharbor.connectors.greenhouse import GreenhouseConnector
from jobharbor.connectors.http_client import HttpClient
from jobharbor.connectors.lever import LeverConnector
from jobharbor.connectors.smartrecruiters import SmartRecruitersConnector
from jobharbor.connectors.ycombinator import YCombinatorConnector
from jobharbor.models import Job, JobStatus
from jobharbor.portal_config import build_portal_discovery_plan, load_portals_config
from jobharbor.services.auto_discovery import (
    DEFAULT_MOBILE_COMPANY_CAREER_URLS,
    DEFAULT_FEED_URLS,
    default_provider_targets,
    discover_jobs_from_company_career_sites,
    discover_jobs_from_public_feeds,
    discover_provider_urls_from_search,
    expand_feed_jobs_with_provider_urls,
    extract_provider_targets,
    prefilter_jobs_for_mobile_focus,
)
from jobharbor.services.dedupe import job_exists
from jobharbor.services.discovery_service import DiscoveryService
from jobharbor.workspace import WorkspacePaths


def _default_request(
    method: str,
    url: str,
    *,
    params: Mapping[str, str] | None = None,
    timeout: float = 10.0,
):
    query = ""
    if params:
        from urllib import parse as urllib_parse

        query = urllib_parse.urlencode(params)
    request_url = f"{url}?{query}" if query else url
    request = urllib_request.Request(request_url, method=method)
    response = urllib_request.urlopen(request, timeout=timeout)
    return _UrllibJsonResponse(response)


class _UrllibJsonResponse:
    def __init__(self, response) -> None:
        self._response = response

    def raise_for_status(self) -> None:
        return None

    def json(self):
        body = self._response.read().decode("utf-8", errors="replace")
        if not body:
            return {}
        return json.loads(body)


class DiscoverStageWorker:
    def __init__(
        self,
        *,
        session: Session,
        settings,
        feed_urls: Sequence[str] = DEFAULT_FEED_URLS,
        feed_fetcher: Callable[..., list[dict[str, str]]] = discover_jobs_from_public_feeds,
        company_site_urls: Sequence[str] = DEFAULT_MOBILE_COMPANY_CAREER_URLS,
        company_site_fetcher: Callable[..., list[dict[str, str]]] = discover_jobs_from_company_career_sites,
        search_fetcher: Callable[..., list[dict[str, str]]] = discover_provider_urls_from_search,
        connector_builder: Callable[..., list[tuple[str, JobConnector]]] | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._feed_urls = tuple(feed_urls)
        self._feed_fetcher = feed_fetcher
        self._company_site_urls = tuple(company_site_urls)
        self._company_site_fetcher = company_site_fetcher
        self._search_fetcher = search_fetcher
        self._connector_builder = connector_builder or self._build_connectors

    def run(self, context: dict[str, object]) -> None:
        feed_jobs = self._feed_fetcher(feed_urls=self._feed_urls)
        company_seed_jobs = self._company_site_fetcher(career_urls=self._company_site_urls)
        provider_jobs_from_pages = expand_feed_jobs_with_provider_urls(feed_jobs + company_seed_jobs)
        provider_jobs_from_search = self._search_fetcher(
            include_keywords=getattr(self._settings, "include_domain_keywords", ()),
        )
        merged_seed_jobs = feed_jobs + company_seed_jobs + provider_jobs_from_pages + provider_jobs_from_search
        targets = extract_provider_targets(job.get("url", "") for job in merged_seed_jobs)
        portal_targets, skipped_portal_entries = self._portal_targets()
        targets = self._merge_targets(targets, portal_targets if portal_targets is not None else default_provider_targets())
        rollout = getattr(self._settings, "connector_rollout", ()) or ()
        connectors = self._connector_builder(targets=targets, rollout=rollout)

        provider_jobs: list[dict[str, object]] = []
        if connectors:
            provider_jobs, _ = DiscoveryService(connectors=connectors).discover()
            provider_jobs = prefilter_jobs_for_mobile_focus(
                provider_jobs,
                include_keywords=getattr(self._settings, "include_domain_keywords", ()),
            )

        discovered_jobs = merged_seed_jobs + provider_jobs
        inserted = self._persist_jobs(discovered_jobs)
        context["discovered_jobs"] = discovered_jobs
        context["discovered_jobs_count"] = inserted
        if skipped_portal_entries:
            context["portal_config_skipped"] = skipped_portal_entries

    def _persist_jobs(self, jobs: Sequence[Mapping[str, object]]) -> int:
        inserted = 0
        for job in jobs:
            source = str(job.get("source", "")).strip()
            external_id = str(job.get("external_id", "")).strip()
            if not source or not external_id:
                continue
            if job_exists(self._session, source=source, external_id=external_id):
                continue
            self._session.add(
                Job(
                    source=source,
                    external_id=external_id,
                    status=JobStatus.discovered,
                )
            )
            inserted += 1

        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return inserted

    def _build_connectors(
        self,
        *,
        targets: Mapping[str, set[str]],
        rollout: Sequence[str],
    ) -> list[tuple[str, JobConnector]]:
        requested = set(rollout) if rollout else {"greenhouse", "ashby", "lever", "smartrecruiters", "ycombinator"}
        http_client = HttpClient(request=_default_request, timeout=10.0)
        connectors: list[tuple[str, JobConnector]] = []

        if "greenhouse" in requested:
            for token in sorted(targets.get("greenhouse", set())):
                connectors.append(("greenhouse", GreenhouseConnector(http_client=http_client, board_token=token)))
        if "ashby" in requested:
            for slug in sorted(targets.get("ashby", set())):
                connectors.append(("ashby", AshbyConnector(http_client=http_client, organization_slug=slug)))
        if "lever" in requested:
            for slug in sorted(targets.get("lever", set())):
                connectors.append(("lever", LeverConnector(http_client=http_client, company_slug=slug)))
        if "smartrecruiters" in requested:
            for slug in sorted(targets.get("smartrecruiters", set())):
                connectors.append(
                    ("smartrecruiters", SmartRecruitersConnector(http_client=http_client, company_slug=slug))
                )
        if "ycombinator" in requested:
            connectors.append(("ycombinator", YCombinatorConnector()))

        return connectors

    def _merge_targets(
        self,
        discovered: Mapping[str, set[str]],
        fallback: Mapping[str, set[str]],
    ) -> dict[str, set[str]]:
        merged: dict[str, set[str]] = {provider: set(slugs) for provider, slugs in discovered.items()}
        for provider, slugs in fallback.items():
            if not slugs:
                continue
            merged.setdefault(provider, set()).update(slugs)
        return {provider: slugs for provider, slugs in merged.items() if slugs}

    def _portal_targets(self) -> tuple[dict[str, set[str]] | None, tuple[str, ...]]:
        if getattr(self._settings, "jobharbor_home", None) is None:
            return None, ()
        portals_path = WorkspacePaths.from_settings(self._settings).portals_yml
        if not portals_path.exists():
            return None, ()
        config = load_portals_config(portals_path)
        plan = build_portal_discovery_plan(config)
        return plan.provider_targets, plan.skipped
