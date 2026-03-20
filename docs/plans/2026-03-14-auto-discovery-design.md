# Auto-Discovery Design

## Goal
Enable the service to discover jobs without preconfigured company slugs by ingesting public hiring feeds, extracting provider slugs when available, and persisting openings from any apply URL.

## Scope
- Add an auto-discovery source that reads public RSS feeds.
- Persist feed jobs directly as discovered jobs (any URL accepted).
- Extract Greenhouse/Ashby/Lever slugs from discovered URLs and optionally enrich via existing connectors.
- Wire the discover pipeline stage so scans actually populate the `jobs` table.

## Out of Scope
- Autonomous job submission automation.
- Full browser scraping crawler.
- Schema migrations for richer job metadata fields.

## Architecture
1. `AutoDiscoveryService`
- Fetch and parse RSS feeds into normalized job dicts.
- Produce generic jobs (`source=feed`, deterministic `external_id` from URL hash).
- Extract known provider targets from discovered URLs for connector enrichment.

2. `DiscoverStageWorker`
- Run auto-discovery feed collection.
- Build connector list from extracted targets.
- Run existing `DiscoveryService` for provider connectors.
- Merge/dedupe discovered jobs and persist new `Job` rows.

3. Runtime wiring
- Replace `discover` noop stage with real discover worker in `runner.py`.

## Data Flow
- Startup scan cycle -> discover stage
- Feed jobs (any URL) -> persist to `jobs`
- URL pattern matches -> provider connector discovery -> persist to `jobs`
- Downstream stages keep current behavior (existing noops except notify)

## Error Handling
- Feed parse/fetch failures do not crash the process unless they prevent all discovery work.
- Connector failures are already captured by `DiscoveryService` as partial failures.

## Verification
- Unit tests for RSS parsing and URL provider extraction.
- Unit tests for discover stage persistence and dedupe.
- Existing discovery service tests remain green.
