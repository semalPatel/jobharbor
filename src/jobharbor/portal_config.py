from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml


SUPPORTED_PROVIDERS = {
    "greenhouse",
    "ashby",
    "lever",
    "smartrecruiters",
    "workday",
    "workable",
    "custom",
    "unknown",
}
SUPPORTED_SCAN_METHODS = {"api", "http", "browser", "search", "agent"}
SCAN_METHOD_ALIASES = {
    "greenhouse_api": "api",
    "playwright": "browser",
    "websearch": "search",
}
SUPPORTED_REQUIRES = {"http", "browser", "search", "agent"}
CONNECTOR_PROVIDERS = {"greenhouse", "ashby", "lever", "smartrecruiters"}
DEFAULT_CAPABILITIES = {"http"}


@dataclass(frozen=True)
class TitleFilterConfig:
    positive: tuple[str, ...] = ()
    negative: tuple[str, ...] = ()
    seniority_boost: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchQueryConfig:
    name: str
    query: str
    enabled: bool = False
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class TrackedCompanyConfig:
    name: str
    careers_url: str
    provider: str = "unknown"
    provider_slug: str | None = None
    api_url: str | None = None
    scan_method: str = "http"
    enabled: bool = True
    requires: tuple[str, ...] = ()
    notes: str | None = None
    scan_query: str | None = None


@dataclass(frozen=True)
class PortalConfig:
    title_filter: TitleFilterConfig = field(default_factory=TitleFilterConfig)
    search_queries: tuple[SearchQueryConfig, ...] = ()
    tracked_companies: tuple[TrackedCompanyConfig, ...] = ()


@dataclass(frozen=True)
class PortalDiscoveryPlan:
    provider_targets: dict[str, set[str]]
    skipped: tuple[str, ...] = ()


def load_portals_config(path: Path) -> PortalConfig:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, Mapping):
        raise TypeError("portals config must define a mapping")

    return PortalConfig(
        title_filter=_load_title_filter(payload.get("title_filter")),
        search_queries=tuple(_load_search_query(row) for row in _as_sequence(payload.get("search_queries"))),
        tracked_companies=tuple(
            _load_tracked_company(row) for row in _as_sequence(payload.get("tracked_companies"))
        ),
    )


def infer_provider_from_url(url: str) -> tuple[str, str | None]:
    parsed = urlparse((url or "").strip())
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    slug = path_parts[0] if path_parts else None

    if host in {"job-boards.greenhouse.io", "boards.greenhouse.io"} and slug:
        return "greenhouse", slug
    if host == "job-boards.eu.greenhouse.io" and slug:
        return "greenhouse", slug
    if host == "jobs.ashbyhq.com" and slug:
        return "ashby", slug
    if host == "jobs.lever.co" and slug:
        return "lever", slug
    if host == "jobs.smartrecruiters.com" and slug:
        return "smartrecruiters", slug
    if host == "apply.workable.com" and slug:
        return "workable", slug
    if host:
        return "custom", None
    return "unknown", None


def build_portal_discovery_plan(
    config: PortalConfig,
    *,
    capabilities: Iterable[str] = DEFAULT_CAPABILITIES,
) -> PortalDiscoveryPlan:
    capability_set = set(capabilities)
    targets: dict[str, set[str]] = {}
    skipped: list[str] = []

    for company in config.tracked_companies:
        if not company.enabled:
            continue
        reason = _skip_reason(company, capability_set)
        if reason is not None:
            skipped.append(f"{company.name}: {reason}")
            continue
        if company.provider not in CONNECTOR_PROVIDERS:
            skipped.append(f"{company.name}: unsupported provider {company.provider}")
            continue
        if not company.provider_slug:
            skipped.append(f"{company.name}: missing provider slug")
            continue
        targets.setdefault(company.provider, set()).add(company.provider_slug)

    for query in config.search_queries:
        if not query.enabled:
            continue
        missing = set(query.requires or ("search",)) - capability_set
        if missing:
            skipped.append(f"{query.name}: missing capability {','.join(sorted(missing))}")

    return PortalDiscoveryPlan(provider_targets=targets, skipped=tuple(skipped))


def _skip_reason(company: TrackedCompanyConfig, capabilities: set[str]) -> str | None:
    required = set(company.requires)
    if company.scan_method == "search":
        required.add("search")
    elif company.scan_method == "browser":
        required.add("browser")
    elif company.scan_method == "agent":
        required.add("agent")
    elif company.scan_method in {"api", "http"}:
        required.add("http")

    missing = required - capabilities
    if missing:
        return f"missing capability {','.join(sorted(missing))}"
    return None


def _load_title_filter(value: object) -> TitleFilterConfig:
    if not isinstance(value, Mapping):
        return TitleFilterConfig()
    return TitleFilterConfig(
        positive=_as_text_tuple(value.get("positive")),
        negative=_as_text_tuple(value.get("negative")),
        seniority_boost=_as_text_tuple(value.get("seniority_boost")),
    )


def _load_search_query(value: object) -> SearchQueryConfig:
    if not isinstance(value, Mapping):
        raise TypeError("search query entries must be mappings")
    requires = _validate_values(_as_text_tuple(value.get("requires")), SUPPORTED_REQUIRES, "requires")
    return SearchQueryConfig(
        name=str(value.get("name", "")).strip(),
        query=str(value.get("query", "")).strip(),
        enabled=bool(value.get("enabled", False)),
        requires=requires,
    )


def _load_tracked_company(value: object) -> TrackedCompanyConfig:
    if not isinstance(value, Mapping):
        raise TypeError("tracked company entries must be mappings")

    careers_url = str(value.get("careers_url", "")).strip()
    inferred_provider, inferred_slug = infer_provider_from_url(careers_url)
    provider = str(value.get("provider") or inferred_provider).strip().lower()
    provider = _validate_value(provider, SUPPORTED_PROVIDERS, "provider")
    scan_method = str(value.get("scan_method") or ("api" if value.get("api") or value.get("api_url") else "http"))
    scan_method = SCAN_METHOD_ALIASES.get(scan_method.strip().lower(), scan_method.strip().lower())
    scan_method = _validate_value(scan_method, SUPPORTED_SCAN_METHODS, "scan_method")

    return TrackedCompanyConfig(
        name=str(value.get("name", "")).strip(),
        careers_url=careers_url,
        provider=provider,
        provider_slug=_optional_text(value.get("provider_slug")) or inferred_slug,
        api_url=_optional_text(value.get("api_url")) or _optional_text(value.get("api")),
        scan_method=scan_method,
        enabled=bool(value.get("enabled", True)),
        requires=_validate_values(_as_text_tuple(value.get("requires")), SUPPORTED_REQUIRES, "requires"),
        notes=_optional_text(value.get("notes")),
        scan_query=_optional_text(value.get("scan_query")),
    )


def _as_sequence(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    raise TypeError("portals config list fields must be sequences")


def _as_text_tuple(value: object) -> tuple[str, ...]:
    return tuple(str(item).strip() for item in _as_sequence(value) if str(item).strip())


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _validate_value(value: str, accepted: set[str], field_name: str) -> str:
    if value not in accepted:
        raise ValueError(f"unsupported {field_name}: {value}")
    return value


def _validate_values(values: tuple[str, ...], accepted: set[str], field_name: str) -> tuple[str, ...]:
    for value in values:
        _validate_value(value, accepted, field_name)
    return values
