# Ideal Discovery-to-Dashboard Implementation Plan

## Purpose

This is the follow-on plan for turning the current career-ops hybrid foundation
into the ideal user flow:

```text
Jobharbor discovers jobs automatically
  -> filters/dedupes/persists rich job details
  -> queues promising opportunities
  -> evaluates and creates report/PDF artifacts
  -> exposes them in the career-ops workspace and review dashboard
  -> user manually decides whether to apply
  -> user marks lifecycle status after applying
```

Important wording:

- "Submitted applications" in the dashboard must mean applications the user has
  manually marked as submitted/applied.
- Jobharbor must never submit an application automatically.
- The dashboard is a review/control surface, not a separate source of truth.

## Current Baseline

As of branch `feat/mvp-greenhouse` after commit `bbf654d`, the following pieces
exist:

- Workspace bootstrap:
  - `JOBHARBOR_HOME`
  - `jobharbor bootstrap`
  - `cv.md`
  - `config/profile.yml`
  - `portals.yml`
  - `data/applications.md`
  - `data/pipeline.md`
  - `data/scan-history.tsv`
  - `reports/`
  - `output/`
  - `jds/`
  - `prompts/`
  - `templates/`
- Portal config foundation:
  - `src/jobharbor/portal_config.py`
  - provider inference for Greenhouse, Ashby, Lever, SmartRecruiters, Workable,
    custom, and unknown
  - capability-gated skipping for browser/search/agent entries
  - connector target extraction for supported providers
- Rich job persistence:
  - `Job.title`
  - `Job.company`
  - `Job.url`
  - `Job.location`
  - `Job.posted_at`
  - `Job.description`
  - `Job.provider`
  - `Job.source_url`
  - `Job.scan_query_name`
- Tracker:
  - `jobharbor tracker`
  - `tracker show`
  - `tracker set-status`
  - `tracker note`
  - deterministic `data/applications.md`
  - lifecycle status separate from execution status
- Reports/evaluation:
  - structured `EvaluationResult`
  - `Evaluation` table
  - `Artifact` table
  - deterministic stub provider
  - command provider with strict JSON validation
  - `EVALUATION_PROVIDER=stub|command|codex`
  - `EVALUATION_COMMAND`
  - `EVALUATION_TIMEOUT_SECONDS`
- PDF artifacts:
  - deterministic local PDF artifact writer
  - PDF links in tracker when artifacts exist
- Pipeline inbox:
  - `data/pipeline.md` parser/writer
  - `PipelineItem` table
  - `jobharbor pipeline --limit N --concurrency 1`
- Apply assist:
  - `jobharbor apply-assist <application_id> --questions-file <path>`
  - appends `## Draft Application Answers` to reports
  - fill plans always have `submit_allowed=false`
- Review dashboard:
  - `/review/applications`
  - `/review/dashboard`
  - dashboard reads the same DB/artifact state as tracker

Current quality gate:

```text
env UV_CACHE_DIR=/home/dev/projects/jobharbor/.uv-cache uv run --python 3.12 --extra dev pytest -q
```

Last known result:

```text
247 passed, 4 warnings
```

## Target User Experience

Fresh setup:

```bash
cd /home/dev/projects/jobharbor
export JOBHARBOR_HOME="$PWD/workspace"
export JOBHARBOR_PROFILE_PATH="$JOBHARBOR_HOME/config/profile.yml"
export DATABASE_URL="sqlite:///$PWD/jobharbor.db"
uv run --python 3.12 --extra dev jobharbor bootstrap
```

User edits:

```text
$JOBHARBOR_HOME/cv.md
$JOBHARBOR_HOME/config/profile.yml
$JOBHARBOR_HOME/portals.yml
```

Automatic mode:

```bash
uv run --python 3.12 --extra dev uvicorn jobharbor.main:app --host 0.0.0.0 --port 8000
```

Expected behavior:

- Scheduler runs discovery on startup and interval.
- `portals.yml` drives discovery.
- Supported companies are fetched through real connectors.
- Unsupported companies are skipped with durable reasons.
- Promising jobs are queued as applications.
- Reports and PDFs are generated.
- Dashboard shows reviewable opportunities with job/report/PDF links.
- User manually applies outside Jobharbor.
- User marks applied/submitted through CLI or dashboard action.

Manual inbox mode:

```bash
uv run --python 3.12 --extra dev jobharbor pipeline --limit 3
uv run --python 3.12 --extra dev jobharbor tracker
```

Dashboard:

```text
http://127.0.0.1:8000/review/dashboard
```

The dashboard should let the user review:

- discovered/queued opportunities
- title/company/location/apply URL
- report link
- PDF link
- evaluation score/recommendation
- lifecycle status
- notes
- actions that do not submit:
  - mark Applied
  - mark Discarded
  - add note
  - open report
  - open apply URL

## Non-Negotiable Product Rules

- Do not build spray-and-pray application automation.
- Never submit a job application automatically.
- Keep the user in the loop before application submission.
- Keep the database authoritative for execution state.
- Keep Markdown/YAML/TSV files as transparent user-facing workspace artifacts.
- Keep agent usage optional and behind provider interfaces.
- Do not make scheduled scans depend on an agent.
- Do not hardcode the career-ops company list in Python.
- `portals.yml` must be the company/catalog data source.
- Dashboard must read DB/exported state, not introduce a separate state model.
- Treat `ApplicationStatus.submitted` as user-confirmed submission only.

## Remaining Gaps

### Provider Gaps

Currently active connector-backed providers:

- `greenhouse`
- `ashby`
- `lever`
- `smartrecruiters`

Recognized but not active as real connectors:

- `workday`
- `workable`
- `custom`
- `unknown`

Capability-gated but not active:

- `browser`
- `search`
- `agent`

Evaluation providers:

- `stub`: active default
- `command`: active
- `codex`: currently command-compatible alias requiring `EVALUATION_COMMAND`
- `openai_api`: not implemented

### Company Catalog Gap

The original plan called for porting:

- 76 tracked-company presets
- 19 search-query presets

from `santifer/career-ops` `templates/portals.example.yml`.

This has not been completed. The current `templates/portals.example.yml` has a
valid representative subset and schema examples, not the full upstream catalog.

Reason:

- The raw upstream YAML was not cleanly available through the browsing tool
  during earlier implementation.
- Do not fabricate the 76-company catalog.
- Use a clean source file before importing.

## Phase A: Full Portal Catalog Import

Goal:

- Replace the representative `templates/portals.example.yml` with a complete,
  validated, career-ops-derived catalog.

Files to modify:

- `templates/portals.example.yml`
- `tests/test_portal_config.py`
- `tests/test_portal_provider_mapping.py`

Implementation steps:

1. Obtain a clean copy of `santifer/career-ops/templates/portals.example.yml`.
2. Preserve source attribution in comments at the top of the local template.
3. Normalize all entries to Jobharbor's schema:
   - `api` -> `api_url`
   - `websearch` -> `search`
   - `greenhouse_api` -> `api`
   - `playwright` -> `browser`
   - infer `provider`
   - infer `provider_slug`
   - infer or set `scan_method`
4. Keep all `search`, `browser`, `agent`, `workday`, `workable`, and `custom`
   entries disabled unless implemented in later phases.
5. Enable connector-safe Greenhouse/Ashby/Lever/SmartRecruiters companies only
   when:
   - URL maps cleanly to a provider slug
   - connector can fetch without browser/search/agent capability
6. Add tests that assert:
   - template loads
   - no invalid provider values
   - no invalid scan methods
   - all enabled companies produce connector targets or explicit skip reasons
   - catalog contains the expected company/query counts

Quality gate:

```bash
uv run --python 3.12 --extra dev pytest -q tests/test_portal_config.py tests/test_portal_provider_mapping.py
uv run --python 3.12 --extra dev pytest -q
```

Acceptance:

- `jobharbor bootstrap` creates a full, valid `portals.yml`.
- Supported companies become connector targets.
- Unsupported companies are retained but skipped safely.
- No company catalog is hardcoded in Python.

## Phase B: Provider Completeness

Goal:

- Expand real discovery coverage beyond the four currently active providers.

Recommended order:

1. Workable
2. Workday
3. Search
4. Browser
5. Custom
6. Agent-assisted discovery

### Workable

Files to add:

- `src/jobharbor/connectors/workable.py`
- `tests/test_workable_parsing.py`

Files to modify:

- `src/jobharbor/workers/discover_stage.py`
- `src/jobharbor/portal_config.py`
- `src/jobharbor/services/auto_discovery.py`

Acceptance:

- `https://apply.workable.com/{slug}` entries fetch jobs through a connector.
- Workable entries no longer skip solely because provider is unsupported.
- Failure of one Workable company does not fail the whole scan.

### Workday

Files to add:

- `src/jobharbor/connectors/workday.py`
- `tests/test_workday_parsing.py`

Acceptance:

- Workday entries stay skipped until a stable, non-browser fetch path is proven.
- If Workday requires browser/runtime complexity, implement it under the
  browser capability phase instead of scraping ad hoc.

### Search

Files to modify:

- `src/jobharbor/services/auto_discovery.py`
- `src/jobharbor/workers/discover_stage.py`
- `src/jobharbor/portal_config.py`

Acceptance:

- `search_queries` from `portals.yml` drive search discovery when
  `search` capability is enabled.
- Search results become provider URLs or pending pipeline items.
- Search is disabled by default unless explicitly configured.
- Query failures are recorded in `data/scan-history.tsv` or run logs.

### Browser

Files to modify or add:

- `src/jobharbor/browser/playwright_session.py`
- provider/browser adapters as needed
- tests with fakes, not live browser network calls

Acceptance:

- Browser-only companies are skipped unless browser capability is enabled.
- Browser runtime failures do not break scheduled scans.
- Browser fetches are bounded with timeouts.

## Phase C: Scan History and Skip Reasons

Goal:

- Make automatic discovery transparent enough to debug.

Files to add or modify:

- `src/jobharbor/scan_history.py`
- `src/jobharbor/workers/discover_stage.py`
- `tests/test_scan_history.py`

Implementation steps:

1. Persist `data/scan-history.tsv` rows for:
   - `added`
   - `skipped_title`
   - `skipped_dup`
   - `skipped_capability`
   - `failed_fetch`
   - `failed_parse`
2. Include:
   - URL
   - first_seen
   - source
   - title
   - company
   - status
   - reason
3. Keep DB authoritative for execution state.
4. Keep TSV deterministic in tests.

Acceptance:

- User can tell why a portal entry or job was skipped.
- Capability-gated companies produce visible skip rows.

## Phase D: Automated Scan-to-Review E2E

Goal:

- Prove the automatic path end to end without manual pipeline inbox input.

Files to add:

- `tests/test_auto_scan_to_dashboard_e2e.py`

Implementation steps:

1. Build fake connectors for Greenhouse/Ashby/Lever/SmartRecruiters.
2. Provide a temp `JOBHARBOR_HOME` with `portals.yml`.
3. Run the pipeline with stub provider.
4. Assert:
   - jobs persisted with rich details
   - applications created
   - evaluations created
   - report artifacts created
   - tracker export includes rows
   - dashboard API includes the same applications
   - no application is automatically marked submitted

Acceptance:

- A single test demonstrates the ideal automatic discovery path without live
  network.

## Phase E: Dashboard Actions

Goal:

- Let the dashboard support the lifecycle actions needed for real review.

Files to modify:

- `src/jobharbor/api/review.py`
- `tests/test_review_dashboard.py`
- optionally small HTML templates if the inline HTML grows too large

Implementation steps:

1. Add dashboard-visible columns:
   - application ID
   - company
   - role
   - status
   - tracker status
   - score
   - recommendation
   - job/apply URL
   - report link
   - PDF link
   - notes
2. Add API routes:
   - mark applied/submitted
   - mark discarded
   - update note
   - optionally re-export tracker
3. Keep all actions explicit user actions.
4. Do not implement automatic submission.

Acceptance:

- User can review discovered opportunities in the dashboard.
- User can mark a manually submitted application as Applied/Submitted.
- Tracker and dashboard remain consistent.

## Phase F: Runtime Configuration and Deployment Gate

Goal:

- Make it easy to see Jobharbor working without remembering many commands.

Files to modify:

- `README.md`
- `docker-compose.yml`
- `ops/systemd/jobharbor.service`
- `scripts/verify_mvp.sh`

Implementation steps:

1. Document a one-command local demo.
2. Add env examples:
   - `JOBHARBOR_HOME`
   - `DATABASE_URL`
   - `JOBHARBOR_CONFIG_PATH`
   - `EVALUATION_PROVIDER`
   - `EVALUATION_COMMAND`
   - `EVALUATION_TIMEOUT_SECONDS`
3. Ensure container uses `/app/workspace`.
4. Add verification script steps for:
   - bootstrap
   - pipeline inbox smoke
   - tracker export
   - dashboard endpoint
5. Keep live network tests out of the default suite.

Acceptance:

- A user can clone, bootstrap, run, and open the dashboard with documented
  commands.
- CI/local default tests do not depend on live job boards or search engines.

## Phase G: Optional Real Agent Provider

Goal:

- Replace command-only Codex alias with a first-class Codex/OpenAI provider if
  desired.

Important:

- This phase should use official OpenAI documentation for current API details.
- Keep `stub` and `command` providers working.

Acceptance:

- Agent output is strictly validated before persistence.
- Provider failure does not mark applications submitted.
- Scheduled scans remain usable without an agent.

## Final Acceptance: Ideal Scenario

The ideal scenario is complete when all of these are true:

1. `jobharbor bootstrap` creates a complete workspace with a full company
   catalog.
2. Automatic scheduler scan reads `portals.yml`.
3. Supported companies are discovered through real connectors.
4. Unsupported/capability-gated companies are skipped with visible reasons.
5. Promising jobs become applications.
6. Applications get evaluations, reports, and PDF artifacts.
7. `jobharbor tracker` exports `data/applications.md` with links.
8. `/review/dashboard` shows the same applications, reports, PDFs, and statuses.
9. User can mark manually submitted applications as Applied/Submitted.
10. Jobharbor never submits applications automatically.
11. Full quality gate passes:

```bash
uv run --python 3.12 --extra dev pytest -q
```

12. A documented local demo works from a clean workspace.

