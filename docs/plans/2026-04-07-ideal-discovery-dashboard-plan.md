# Ideal Jobharbor Career-Ops Implementation Plan

## Purpose

This is the ready-to-implement plan for making Jobharbor work in the ideal way:

```text
Automatic company/job discovery
  -> DB-backed filtering, dedupe, queueing, evaluation, reports, PDFs
  -> career-ops workspace artifacts for transparency
  -> dashboard for review and lifecycle updates
  -> user manually applies
  -> user marks Applied/Submitted after the fact
```

This plan is intentionally specific. An implementation agent should be able to
start at `Phase A` and work through the remaining phases without relying on
prior chat context.

## Current Baseline

Repository:

```text
/home/dev/projects/jobharbor
branch: feat/mvp-greenhouse
latest known plan commit: d75c719 Document ideal discovery dashboard plan
```

Implemented foundation:

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
- Portal config:
  - `src/jobharbor/portal_config.py`
  - provider inference for Greenhouse, Ashby, Lever, SmartRecruiters, Workable,
    custom, and unknown
  - scan-method normalization for `api`, `http`, `browser`, `search`, `agent`
  - aliases for career-ops-style values such as `greenhouse_api`, `websearch`,
    and `playwright`
  - capability-gated skipping for unsupported entries
- Discovery connectors currently active:
  - Greenhouse
  - Ashby
  - Lever
  - SmartRecruiters
  - Y Combinator in the older fallback connector path
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
  - lifecycle status separate from `ApplicationStatus`
- Evaluation/reporting:
  - `EvaluationResult`
  - `Evaluation` table
  - `Artifact` table
  - deterministic stub provider
  - command provider with strict JSON validation
  - `EVALUATION_PROVIDER=stub|command|codex`
  - `EVALUATION_COMMAND`
  - `EVALUATION_TIMEOUT_SECONDS`
- PDF artifacts:
  - deterministic local PDF artifact renderer
  - tracker PDF links when PDF artifacts exist
- Pipeline inbox:
  - `data/pipeline.md`
  - `PipelineItem` table
  - `jobharbor pipeline --limit N --concurrency 1`
- Apply assist:
  - `jobharbor apply-assist <application_id> --questions-file <path>`
  - appends `## Draft Application Answers` to reports
  - `submit_allowed=false`
- Dashboard/API:
  - `/review/applications`
  - `/review/dashboard`
  - dashboard reads DB/artifact state, not separate frontend state

Last known full quality gate:

```bash
env UV_CACHE_DIR=/home/dev/projects/jobharbor/.uv-cache uv run --python 3.12 --extra dev pytest -q
```

Last known result:

```text
247 passed, 4 warnings
```

## Target Career-Ops Workspace Contract

The workspace is the human-readable surface. The DB remains authoritative for
execution state.

```text
JOBHARBOR_HOME/
  cv.md
  config/profile.yml
  portals.yml
  data/applications.md
  data/pipeline.md
  data/scan-history.tsv
  reports/
  output/
  jds/
  prompts/
  templates/
```

Career-ops compatibility requirements:

- `cv.md` is the master CV text used by reports, PDF, and apply assist.
- `config/profile.yml` is the user profile/rubric input.
- `portals.yml` is the company and query catalog. Do not hardcode catalog data
  in Python.
- `data/applications.md` is deterministic tracker export, regenerated from DB.
- `data/pipeline.md` is a manual URL inbox, backed by `PipelineItem` rows.
- `data/scan-history.tsv` records transparent discovery outcomes and skip
  reasons.
- `reports/` stores evaluation and apply-assist markdown.
- `output/` stores generated PDFs and future fill plans.

## Ideal Runtime Flow

### First-Time Setup

```bash
cd /home/dev/projects/jobharbor
export JOBHARBOR_HOME="$PWD/workspace"
export JOBHARBOR_PROFILE_PATH="$JOBHARBOR_HOME/config/profile.yml"
export DATABASE_URL="sqlite:///$PWD/jobharbor.db"
env UV_CACHE_DIR="$PWD/.uv-cache" uv run --python 3.12 --extra dev jobharbor bootstrap
```

User edits:

```text
$JOBHARBOR_HOME/cv.md
$JOBHARBOR_HOME/config/profile.yml
$JOBHARBOR_HOME/portals.yml
```

### Automatic Mode

```bash
env UV_CACHE_DIR="$PWD/.uv-cache" uv run --python 3.12 --extra dev uvicorn jobharbor.main:app --host 0.0.0.0 --port 8000
```

Expected automatic behavior:

1. Scheduler starts.
2. Scheduler runs one scan on startup and then on interval.
3. Discovery reads `JOBHARBOR_HOME/portals.yml`.
4. Supported portal entries fetch jobs through connectors.
5. Unsupported/capability-gated entries are skipped with visible reasons.
6. Jobs are deduped and filtered.
7. Promising jobs become applications.
8. Evaluations, reports, and PDFs are created.
9. Tracker export and dashboard show the same DB-backed opportunities.
10. User manually applies outside Jobharbor.
11. User marks the application as Applied/Submitted.

### Dashboard

```text
http://127.0.0.1:8000/review/dashboard
```

Dashboard must show:

- application ID
- company
- role
- job/apply URL
- location
- score
- recommendation
- execution status
- lifecycle/tracker status
- report link
- PDF link
- notes
- actions that do not submit:
  - mark Applied/Submitted
  - mark Discarded
  - update note
  - open job URL
  - open report
  - open PDF

### Manual Inbox Mode

```bash
env UV_CACHE_DIR="$PWD/.uv-cache" uv run --python 3.12 --extra dev jobharbor pipeline --limit 3 --concurrency 1
env UV_CACHE_DIR="$PWD/.uv-cache" uv run --python 3.12 --extra dev jobharbor tracker
```

This remains useful for testing hand-picked jobs, but it is not the final ideal
path. The final ideal path is automatic discovery into dashboard review.

## Product Rules

- Never submit an application automatically.
- Never mark `ApplicationStatus.submitted` from discovery, evaluation, PDF, or
  apply-assist automation.
- Only explicit user actions can mark an application Applied/Submitted.
- Keep DB authoritative for execution state.
- Keep workspace files transparent and deterministic where possible.
- Keep agent usage optional.
- Scheduled scans must work without an agent.
- Live network access must not be required by the default test suite.
- Dashboard must not introduce a separate state model.

## Implementation Sequencing

Work in this order:

```text
A. Company catalog import
B. Provider completeness
C. Scan history and skip reasons
D. Automatic scan-to-dashboard E2E
E. Dashboard review actions
F. Runtime/demo gate
G. Optional first-class agent provider
```

Commit at the end of each phase after its focused gate and the full gate pass.

Full gate for every phase:

```bash
env UV_CACHE_DIR=/home/dev/projects/jobharbor/.uv-cache uv run --python 3.12 --extra dev pytest -q
```

Before every commit:

```bash
rm -rf uv.lock src/jobharbor.egg-info jobharbor.db
git status --short
```

Do not commit generated local DBs, virtualenvs, or `uv.lock` unless the repo
deliberately decides to adopt a lockfile.

## Phase A: Full Company Catalog Import

Goal:

- Make `templates/portals.example.yml` match the career-ops company/query
  catalog while preserving Jobharbor's provider/capability model.

Dependencies:

- Clean source copy of `santifer/career-ops/templates/portals.example.yml`.
- If using internet, use the raw GitHub file or a cloned repo. Do not scrape a
  collapsed web preview into YAML.

Files to modify:

- `templates/portals.example.yml`
- `tests/test_portal_config.py`
- `tests/test_portal_provider_mapping.py`
- optionally `docs/plans/2026-04-07-ideal-discovery-dashboard-plan.md` if source
  counts differ from the historical 76/19 reference

Implementation steps:

1. Fetch or copy the clean upstream YAML.
2. Add a source comment at the top of `templates/portals.example.yml`:

   ```yaml
   # Adapted from santifer/career-ops templates/portals.example.yml.
   # Jobharbor normalizes provider fields and capability-gates unsupported scan methods.
   ```

3. Normalize fields:
   - `api` -> `api_url`
   - `greenhouse_api` -> `api`
   - `websearch` -> `search`
   - `playwright` -> `browser`
   - infer `provider`
   - infer `provider_slug`
   - infer or set `scan_method`
   - preserve notes when present
4. Keep search/browser/agent entries disabled unless Phase B/C implements them.
5. Enable only connector-safe companies where provider and slug are valid for:
   - Greenhouse
   - Ashby
   - Lever
   - SmartRecruiters
6. Add tests:
   - template loads with `load_portals_config`
   - title filter loads
   - expected number of tracked companies load
   - expected number of search queries load
   - every enabled company either produces a connector target or a skip reason
   - no unknown provider values except explicit `unknown`
   - no unknown scan methods
   - at least one enabled company for each active supported provider, if present
7. Run bootstrap test to ensure new users receive the full catalog.

Focused gate:

```bash
env UV_CACHE_DIR=/home/dev/projects/jobharbor/.uv-cache uv run --python 3.12 --extra dev pytest -q tests/test_portal_config.py tests/test_portal_provider_mapping.py tests/test_workspace.py tests/test_cli_bootstrap.py
```

Acceptance:

- `jobharbor bootstrap` creates a full career-ops-compatible `portals.yml`.
- Supported companies feed connector targets.
- Unsupported companies are preserved but disabled or skipped safely.
- No catalog data is hardcoded in Python.

## Phase B: Provider Completeness

Goal:

- Make the catalog useful by adding real provider coverage where feasible.

Provider status target:

| Provider | Target behavior |
| --- | --- |
| `greenhouse` | Active connector; keep stable |
| `ashby` | Active connector; keep stable |
| `lever` | Active connector; keep stable |
| `smartrecruiters` | Active connector; keep stable |
| `workable` | Add connector if non-browser fetch path is stable |
| `workday` | Keep skipped unless stable non-browser fetch path exists |
| `custom` | Convert to pipeline/search/browser path, not ad hoc scraping |
| `unknown` | Skip with reason |
| `search` | Add explicit capability and query-driven discovery |
| `browser` | Add explicit capability and bounded runtime |
| `agent` | Optional, never required for scheduled scan |

### Phase B1: Workable Connector

Files to add:

- `src/jobharbor/connectors/workable.py`
- `tests/test_workable_parsing.py`

Files to modify:

- `src/jobharbor/workers/discover_stage.py`
- `src/jobharbor/portal_config.py`
- `src/jobharbor/services/auto_discovery.py`
- `tests/test_discover_stage.py`
- `tests/test_portal_config.py`

Implementation steps:

1. Implement a connector only if Workable exposes a stable JSON or HTML endpoint
   that can be normalized without browser automation.
2. Normalize to existing job dict shape:
   - `external_id`
   - `title`
   - `company`
   - `location`
   - `url`
   - `posted_at`
   - `description`
3. Add `workable` to connector target extraction and builder.
4. Preserve partial failure semantics.
5. Keep tests fixture-based, not live-network.

Focused gate:

```bash
env UV_CACHE_DIR=/home/dev/projects/jobharbor/.uv-cache uv run --python 3.12 --extra dev pytest -q tests/test_workable_parsing.py tests/test_discover_stage.py tests/test_portal_config.py
```

Acceptance:

- Workable entries can produce jobs when fixture payloads are valid.
- A failed Workable company does not fail the whole scan.

### Phase B2: Workday Decision Gate

Files to add or modify only if implementation is viable:

- `src/jobharbor/connectors/workday.py`
- `tests/test_workday_parsing.py`

Implementation steps:

1. Determine whether configured Workday URLs can be fetched without browser
   automation.
2. If yes, implement connector with fixture tests.
3. If no, keep Workday disabled/capability-gated and document reason in
   `portals.yml` comments and scan history.

Acceptance:

- Workday behavior is explicit: either real connector with tests or deterministic
  skip reason.

### Phase B3: Search Capability

Files to modify:

- `src/jobharbor/portal_config.py`
- `src/jobharbor/services/auto_discovery.py`
- `src/jobharbor/workers/discover_stage.py`
- `tests/test_auto_discovery.py`
- `tests/test_discover_stage.py`

Implementation steps:

1. Add an explicit setting for enabled capabilities, for example:

   ```text
   JOBHARBOR_DISCOVERY_CAPABILITIES=http,search
   ```

2. Load enabled `search_queries` only when `search` capability is present.
3. Feed queries into the existing search fetcher or a new query-aware fetcher.
4. Convert provider URLs into connector targets.
5. Convert generic result URLs into `PipelineItem` rows if appropriate.
6. Persist skip reasons when search is disabled.
7. Keep search disabled by default.

Acceptance:

- Search entries no longer need to be hardcoded.
- Default tests do not call live search engines.

### Phase B4: Browser Capability

Files to modify:

- `src/jobharbor/browser/playwright_session.py`
- `src/jobharbor/workers/discover_stage.py`
- browser/provider adapters as needed

Implementation steps:

1. Add capability setting for `browser`.
2. Keep browser disabled by default.
3. Implement only bounded fetches with timeouts.
4. Add tests with fake browser/session objects.
5. Browser runtime failure must log/skip, not crash scheduled scan.

Acceptance:

- Browser-only entries become actionable only when configured.
- No default test requires a real browser.

## Phase C: Scan History and Skip Reasons

Goal:

- Make automatic discovery transparent enough to debug from workspace files.

Files to add:

- `src/jobharbor/scan_history.py`
- `tests/test_scan_history.py`

Files to modify:

- `src/jobharbor/workers/discover_stage.py`
- `src/jobharbor/workspace.py` if path helpers need additions

Data contract:

```text
url	first_seen	source	title	company	status	reason
```

Allowed statuses:

- `added`
- `skipped_title`
- `skipped_dup`
- `skipped_capability`
- `failed_fetch`
- `failed_parse`

Implementation steps:

1. Implement a deterministic TSV writer/appender service.
2. Write rows when:
   - portal entry is skipped for missing capability
   - job is inserted
   - duplicate job is skipped
   - fetch or parse fails in a controlled provider path
3. Do not make TSV authoritative for execution state.
4. Keep output stable in tests.

Focused gate:

```bash
env UV_CACHE_DIR=/home/dev/projects/jobharbor/.uv-cache uv run --python 3.12 --extra dev pytest -q tests/test_scan_history.py tests/test_discover_stage.py
```

Acceptance:

- User can open `data/scan-history.tsv` and understand why entries were added or
  skipped.

## Phase D: Automatic Scan-to-Dashboard E2E

Goal:

- Prove the ideal automatic path without manual inbox input or live network.

Files to add:

- `tests/test_auto_scan_to_dashboard_e2e.py`

Implementation steps:

1. Create a temp workspace with:
   - `cv.md`
   - `config/profile.yml`
   - `portals.yml` containing supported companies
2. Use fake connectors or monkeypatched connector builder.
3. Run the pipeline through `PipelineCoordinator` or `run_scan_cycle` with test
   settings.
4. Assert:
   - discovered jobs persisted with rich fields
   - applications created
   - evaluations created
   - reports created
   - PDFs created if included in automatic path, otherwise explicitly not part
     of automatic scan
   - tracker export includes application rows and report/PDF links
   - dashboard API returns the same applications
   - `ApplicationStatus.submitted` is not set automatically

Focused gate:

```bash
env UV_CACHE_DIR=/home/dev/projects/jobharbor/.uv-cache uv run --python 3.12 --extra dev pytest -q tests/test_auto_scan_to_dashboard_e2e.py
```

Acceptance:

- One test proves the ideal automatic scan-to-review-dashboard path.

## Phase E: Dashboard Review Actions

Goal:

- Make the dashboard a practical review surface for applications the user might
  submit manually.

Files to modify:

- `src/jobharbor/api/review.py`
- `tests/test_review_dashboard.py`
- optionally add `src/jobharbor/templates/` or static HTML rendering helpers if
  inline HTML grows too large

Implementation steps:

1. Extend `/review/applications` response with:
   - application ID
   - company
   - role
   - job URL
   - location
   - execution status
   - tracker status
   - evaluation score
   - recommendation
   - report path
   - PDF path
   - notes
2. Extend `/review/dashboard` table with the same fields.
3. Add explicit user-action endpoints:
   - `POST /review/{id}/submitted`
   - `POST /review/{id}/discarded`
   - `POST /review/{id}/note`
4. Ensure dashboard actions update DB and regenerate tracker export if needed.
5. Do not add a submit-application endpoint.
6. Do not automate form submission.

Focused gate:

```bash
env UV_CACHE_DIR=/home/dev/projects/jobharbor/.uv-cache uv run --python 3.12 --extra dev pytest -q tests/test_review_dashboard.py tests/test_review_api.py tests/test_tracker_export.py
```

Acceptance:

- User can review jobs and mark lifecycle outcomes in the dashboard.
- Dashboard and `data/applications.md` remain consistent.

## Phase F: Runtime and Demo Gate

Goal:

- Make it easy to see Jobharbor working without remembering internal commands.

Files to modify:

- `README.md`
- `scripts/verify_mvp.sh`
- `docker-compose.yml`
- `ops/systemd/jobharbor.service`
- optionally `.env.example`

Implementation steps:

1. Add a documented local demo:

   ```bash
   export JOBHARBOR_HOME="$PWD/workspace"
   export JOBHARBOR_PROFILE_PATH="$JOBHARBOR_HOME/config/profile.yml"
   export DATABASE_URL="sqlite:///$PWD/jobharbor.db"
   uv run --python 3.12 --extra dev jobharbor bootstrap
   uv run --python 3.12 --extra dev jobharbor pipeline --limit 3
   uv run --python 3.12 --extra dev jobharbor tracker
   uv run --python 3.12 --extra dev uvicorn jobharbor.main:app --reload
   ```

2. Add automatic mode instructions for scheduler startup.
3. Add env docs for:
   - `JOBHARBOR_HOME`
   - `DATABASE_URL`
   - `JOBHARBOR_CONFIG_PATH`
   - `JOBHARBOR_PROFILE_PATH`
   - `EVALUATION_PROVIDER`
   - `EVALUATION_COMMAND`
   - `EVALUATION_TIMEOUT_SECONDS`
   - discovery capabilities setting if added in Phase B
4. Update `scripts/verify_mvp.sh` to run:
   - full tests
   - bootstrap smoke
   - pipeline inbox smoke
   - tracker export smoke
   - dashboard render smoke without starting live network discovery
5. Ensure Docker uses `/app/workspace` for `JOBHARBOR_HOME`.

Focused gate:

```bash
./scripts/verify_mvp.sh
```

Acceptance:

- A clean local demo works from documented commands.
- A container deployment has a workspace mount/path.
- Verification does not depend on live job boards.

## Phase G: Optional First-Class Agent Provider

Goal:

- Replace the command-compatible `codex` alias with a first-class provider only
  if needed.

Rules:

- Use official OpenAI documentation for current API details.
- Keep `stub` and `command` providers working.
- Keep scheduled scans functional without an agent.
- Strictly validate all provider output before persistence.
- Provider failure must not mark anything submitted/applied.

Files likely to add or modify:

- `src/jobharbor/agents/codex_provider.py`
- `src/jobharbor/agents/openai_provider.py` if using the OpenAI API
- `tests/test_agent_codex_provider.py`
- `tests/test_agent_command_provider.py`
- `README.md`

Acceptance:

- Agent-backed evaluation can be enabled explicitly.
- Stub remains the default.
- Invalid or missing agent output fails safely.

## Final Acceptance Checklist

The ideal scenario is complete when all of these are true:

1. `jobharbor bootstrap` creates a full career-ops-compatible workspace.
2. `portals.yml` contains the complete normalized company/query catalog.
3. Automatic scheduler scans read `portals.yml`.
4. Supported companies produce connector jobs without manual URL paste.
5. Unsupported/capability-gated companies are skipped with visible reasons.
6. Rich jobs are persisted.
7. Promising jobs become applications.
8. Evaluations are persisted.
9. Reports are written to `reports/`.
10. PDFs are written to `output/` where configured.
11. `jobharbor tracker` exports `data/applications.md` with report/PDF links.
12. `/review/dashboard` shows the same DB-backed application state.
13. Dashboard actions can mark manually applied jobs as submitted/applied.
14. Apply assist can draft answers but cannot submit.
15. No automation path submits applications.
16. Full quality gate passes:

    ```bash
    env UV_CACHE_DIR=/home/dev/projects/jobharbor/.uv-cache uv run --python 3.12 --extra dev pytest -q
    ```

17. Runtime/demo gate passes:

    ```bash
    ./scripts/verify_mvp.sh
    ```
