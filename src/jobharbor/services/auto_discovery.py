from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import hashlib
from html import unescape
import re
from urllib import parse as urllib_parse
from urllib import request as urllib_request
import xml.etree.ElementTree as ET


DEFAULT_FEED_URLS: tuple[str, ...] = (
    "https://weworkremotely.com/remote-jobs.rss",
    "https://hnrss.org/jobs",
)
DUCKDUCKGO_HTML_SEARCH_URL = "https://duckduckgo.com/html/"
PROVIDER_URL_PATTERN = re.compile(
    r"https?://(?:boards\.greenhouse\.io|job-boards\.greenhouse\.io|jobs\.ashbyhq\.com|jobs\.lever\.co)/[^\"'\s<>()]+",
    flags=re.IGNORECASE,
)
ENCODED_PROVIDER_URL_PATTERN = re.compile(
    r"https?%3A%2F%2F(?:boards\.greenhouse\.io|job-boards\.greenhouse\.io|jobs\.ashbyhq\.com|jobs\.lever\.co)%2F[^\"'\s<>()]+",
    flags=re.IGNORECASE,
)
DEFAULT_PROVIDER_TARGET_SEEDS: dict[str, tuple[str, ...]] = {
    # Seed providers so discovery can run even when public feed/search scraping yields no provider URLs.
    "greenhouse": (
        "nearsure",
        "doordashusa",
        "andurilindustries",
    ),
    "lever": (
        "jobgether",
        "freedompay",
    ),
    "ashby": (),
}


def discover_jobs_from_public_feeds(
    feed_urls: Iterable[str],
    *,
    fetch_text: Callable[[str], str] | None = None,
) -> list[dict[str, str]]:
    fetcher = fetch_text or _default_fetch_text
    discovered: list[dict[str, str]] = []

    for feed_url in feed_urls:
        try:
            content = fetcher(feed_url)
        except Exception:
            continue
        discovered.extend(_parse_rss_jobs(content))

    return discovered


def extract_provider_targets(urls: Iterable[str]) -> dict[str, set[str]]:
    targets: dict[str, set[str]] = {
        "greenhouse": set(),
        "ashby": set(),
        "lever": set(),
    }
    for url in urls:
        parsed = urllib_parse.urlparse((url or "").strip())
        host = parsed.netloc.lower()
        path_parts = [segment for segment in parsed.path.split("/") if segment]
        if not path_parts:
            continue

        slug = path_parts[0]
        if "boards.greenhouse.io" in host or "job-boards.greenhouse.io" in host:
            targets["greenhouse"].add(slug)
        elif "jobs.ashbyhq.com" in host:
            targets["ashby"].add(slug)
        elif "jobs.lever.co" in host:
            targets["lever"].add(slug)

    return {provider: slugs for provider, slugs in targets.items() if slugs}


def expand_feed_jobs_with_provider_urls(
    jobs: Iterable[dict[str, str]],
    *,
    fetch_text: Callable[[str], str] | None = None,
    max_pages: int = 50,
) -> list[dict[str, str]]:
    fetcher = fetch_text or _default_fetch_text
    expanded: list[dict[str, str]] = []
    page_count = 0

    for job in jobs:
        if page_count >= max_pages:
            break
        url = (job.get("url") or "").strip()
        if not url or _is_provider_url(url):
            continue

        page_count += 1
        try:
            html = fetcher(url)
        except Exception:
            continue

        for provider_url in _extract_provider_urls_from_html(html):
            source = _source_from_url(provider_url)
            if not source:
                continue
            expanded.append(
                {
                    "source": source,
                    "external_id": _stable_id(provider_url),
                    "title": (job.get("title") or "").strip(),
                    "company": (job.get("company") or "").strip(),
                    "location": (job.get("location") or "").strip(),
                    "url": provider_url,
                    "posted_at": (job.get("posted_at") or "").strip(),
                    "description": (job.get("description") or "").strip(),
                }
            )

    return expanded


def discover_provider_urls_from_search(
    *,
    include_keywords: Iterable[str] = (),
    fetch_text: Callable[[str], str] | None = None,
    max_results_per_query: int = 10,
) -> list[dict[str, str]]:
    fetcher = fetch_text or _default_fetch_text
    discovered: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for query in _build_provider_search_queries(include_keywords):
        search_url = f"{DUCKDUCKGO_HTML_SEARCH_URL}?{urllib_parse.urlencode({'q': query})}"
        try:
            html = fetcher(search_url)
        except Exception:
            continue

        query_results = 0
        for provider_url in _extract_provider_urls_from_search_html(html):
            normalized = _normalize_provider_url(provider_url)
            if not normalized or normalized in seen_urls:
                continue
            source = _source_from_url(normalized)
            if not source:
                continue
            seen_urls.add(normalized)
            query_results += 1
            discovered.append(
                {
                    "source": source,
                    "external_id": _stable_id(normalized),
                    "title": "",
                    "company": "",
                    "location": "",
                    "url": normalized,
                    "posted_at": "",
                    "description": f"search:{query}",
                }
            )
            if query_results >= max_results_per_query:
                break

    return discovered


def default_provider_targets() -> dict[str, set[str]]:
    return {
        provider: {slug for slug in slugs if slug.strip()}
        for provider, slugs in DEFAULT_PROVIDER_TARGET_SEEDS.items()
        if slugs
    }


def _default_fetch_text(url: str) -> str:
    request = urllib_request.Request(
        url,
        headers={
            "User-Agent": "jobharbor/1.0 (+https://example.local)",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
        },
    )
    with urllib_request.urlopen(request, timeout=10.0) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_rss_jobs(content: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    jobs: list[dict[str, str]] = []
    for item in root.findall("./channel/item"):
        title = _node_text(item, "title")
        url = _node_text(item, "link")
        posted_at = _node_text(item, "pubDate")
        description = _node_text(item, "description")
        if not url:
            continue
        jobs.append(
            {
                "source": "feed",
                "external_id": _stable_id(url),
                "title": title,
                "company": "",
                "location": "",
                "url": url,
                "posted_at": posted_at,
                "description": description,
            }
        )
    return jobs


def _node_text(parent: ET.Element, tag: str) -> str:
    node = parent.find(tag)
    if node is None or node.text is None:
        return ""
    return unescape(node.text).strip()


def _stable_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _extract_provider_urls_from_html(html: str) -> list[str]:
    found = [match.group(0).strip() for match in PROVIDER_URL_PATTERN.finditer(html)]
    deduped: list[str] = []
    seen: set[str] = set()
    for url in found:
        normalized = url.rstrip(".,)")
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _extract_provider_urls_from_search_html(html: str) -> list[str]:
    candidates: list[str] = []
    candidates.extend(_extract_provider_urls_from_html(html))

    for encoded in ENCODED_PROVIDER_URL_PATTERN.findall(html):
        candidates.append(_decode_url(encoded))

    for match in re.findall(r"[?&]uddg=([^\"'\s&<>]+)", html):
        candidates.append(_decode_url(match))

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_provider_url(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _is_provider_url(url: str) -> bool:
    host = urllib_parse.urlparse(url).netloc.lower()
    return any(
        domain in host
        for domain in ("boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.ashbyhq.com", "jobs.lever.co")
    )


def _source_from_url(url: str) -> str:
    host = urllib_parse.urlparse(url).netloc.lower()
    if "boards.greenhouse.io" in host or "job-boards.greenhouse.io" in host:
        return "greenhouse"
    if "jobs.ashbyhq.com" in host:
        return "ashby"
    if "jobs.lever.co" in host:
        return "lever"
    return ""


def _build_provider_search_queries(include_keywords: Iterable[str]) -> list[str]:
    keywords = [kw.strip().lower() for kw in include_keywords if kw and kw.strip()]
    if not keywords:
        keywords = ["android", "kotlin", "mobile"]

    keywords = keywords[:4]
    domains = (
        "boards.greenhouse.io",
        "jobs.lever.co",
        "jobs.ashbyhq.com",
    )
    queries: list[str] = []
    for domain in domains:
        for keyword in keywords:
            queries.append(f"site:{domain} {keyword} remote")
    return queries


def _decode_url(value: str) -> str:
    decoded = value
    for _ in range(3):
        next_value = urllib_parse.unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    return decoded


def _normalize_provider_url(url: str) -> str:
    text = (url or "").strip().rstrip(".,)")
    if not text:
        return ""

    parsed = urllib_parse.urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return ""
    if not _is_provider_url(text):
        return ""

    normalized = urllib_parse.urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            "",
            parsed.query,
            "",
        )
    )
    return normalized
