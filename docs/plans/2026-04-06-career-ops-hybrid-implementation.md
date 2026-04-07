# Career-Ops Hybrid Implementation Plan

## Purpose

This is the handoff-grade implementation plan for evolving Jobharbor into a
hybrid of:

- Jobharbor's existing reliable service kernel: scheduler, DB, connectors,
  dedupe, queueing, API, notifications, and tests.
- Career-ops' agent-friendly workspace: `cv.md`, `profile.yml`, `portals.yml`,
  `applications.md`, `pipeline.md`, `scan-history.tsv`, `reports/`, `output/`,
  and prompt/template files.

This document should be sufficient for an implementation agent that has no
prior conversation context. It intentionally restates the important project
context, target behavior, file paths, data contracts, phases, tests, and
acceptance criteria.

## Non-Negotiable Product Rules

- Do not build spray-and-pray application automation.
- Never submit a job application automatically.
- Keep the user in the loop before application submission.
- Keep the database authoritative for execution state.
- Keep Markdown/YAML/TSV files available as transparent user-facing workspace
  artifacts.
- Keep agent usage optional and behind provider interfaces.
- Do not make scheduled scans depend on an agent.
- Do not hardcode the career-ops company list in Python; load it from YAML.
- Preserve existing tests unless a phase explicitly changes the behavior they
  cover.

## Current Repo Context

Project root: `/home/dev/projects/jobharbor`

Language/runtime:

- Python 3.12
- FastAPI
- APScheduler
- SQLModel/SQLite
- PyYAML
- pytest

Important files:

- `pyproject.toml`: package metadata and dependencies.
- `src/jobharbor/main.py`: FastAPI app and scheduler startup.
- `src/jobharbor/runner.py`: builds and runs the pipeline stages.
- `src/jobharbor/models.py`: SQLModel models and status enums.
- `src/jobharbor/db.py`: engine/session/bootstrap helpers.
- `src/jobharbor/config.py`: settings and YAML override integration.
- `src/jobharbor/config_schema.py`: current `config.yaml` loader.
- `src/jobharbor/services/pipeline.py`: pipeline stage coordinator.
- `src/jobharbor/services/auto_discovery.py`: RSS/search/provider URL discovery.
- `src/jobharbor/services/discovery_service.py`: connector orchestration.
- `src/jobharbor/workers/discover_stage.py`: discovery stage worker.
- `src/jobharbor/workers/score_stage.py`: hard-filter score stage.
- `src/jobharbor/workers/queue_stage.py`: application queue stage.
- `src/jobharbor/workers/prefill_stage.py`: profile/prefill stage.
- `src/jobharbor/workers/review_stage.py`: review-count stage.
- `src/jobharbor/workers/notify_stage.py`: notification stage.
- `src/jobharbor/api/review.py`: review API.
- `tests/`: existing unit and smoke tests.

Current pipeline order:

```text
discover -> normalize -> dedupe -> score -> queue -> prefill -> review -> notify
```

Current model limitations:

- `Job` stores only `id`, `source`, `external_id`, and `status`.
- `Application` stores only `id`, `job_id`, and `status`.
- Rich job details such as title/company/url/description are transient dict
  fields in pipeline context.
- There is no workspace directory concept.
- There is no `portals.yml` loader.
- There is no tracker export/import.
- There is no evaluation provider abstraction.
- There is no report/PDF artifact model.

## Target User Experience

The user should maintain a workspace:

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

Manual usage:

```text
jobharbor bootstrap
jobharbor scan
jobharbor pipeline
jobharbor tracker
jobharbor tracker show 42
jobharbor tracker set-status 42 applied
jobharbor tracker note 42 "Applied via Greenhouse."
```

Daemon usage:

- Scheduler runs discovery.
- Promising jobs are queued for review/evaluation.
- Notifications point to the review queue, report, PDF if available, and apply
  URL.

High-value behavior:

- Scan many jobs.
- Filter/dedupe cheaply.
- Spend agent/evaluation effort only on promising jobs.
- Produce reports/PDFs/application answers for serious opportunities.
- Let the user decide whether to apply.
- Learn from user corrections by updating `profile.yml`, `portals.yml`, and
  rubrics/prompts.

## Global Architecture

### Service Kernel

Jobharbor remains responsible for:

- scheduled scans
- connector execution
- persistence
- dedupe
- queueing
- status transitions
- artifact metadata
- tracker export/import
- notifications
- retry/resume behavior
- API and CLI orchestration

### Workspace Layer

Human-facing files live under `JOBHARBOR_HOME`.

Rules:

- Bootstrap creates missing user-owned files.
- Bootstrap must not overwrite existing user-owned files.
- Templates can live in the repo and be copied into the workspace only if the
  target file is missing.
- DB is authoritative for execution state.
- Workspace files are transparent interaction surfaces.

### Agent Layer

Codex or another agent is used for:

- profile/rubric/template editing
- role evaluation
- report drafting
- tailored CV recommendations
- application answer drafting
- optional high-value research
- user feedback incorporation

Codex is not required for:

- scheduled scans
- dedupe
- connector fetching
- DB writes
- status transitions
- tracker export
- notifications

All agent calls must sit behind provider interfaces with structured output
validation.

## Data Contracts

### Workspace Path

Add a setting:

```text
JOBHARBOR_HOME
```

Default behavior:

- Development: project root or `./workspace` should be chosen explicitly during
  implementation. Prefer `./workspace` to avoid mixing generated user data with
  repo files.
- Container: `/app/workspace`.

Implement as a path setting in `Settings`, with helper methods or a new
`WorkspacePaths` service.

### `portals.yml`

Initial schema:

```yaml
title_filter:
  positive:
    - "AI"
    - "LLM"
  negative:
    - "Junior"
  seniority_boost:
    - "Senior"

search_queries:
  - name: Ashby - AI PM
    query: 'site:jobs.ashbyhq.com "AI Product Manager" remote'
    enabled: false
    requires:
      - search

tracked_companies:
  - name: Anthropic
    careers_url: https://job-boards.greenhouse.io/anthropic
    provider: greenhouse
    provider_slug: anthropic
    api_url: https://boards-api.greenhouse.io/v1/boards/anthropic/jobs
    scan_method: api
    enabled: true
    notes: AI lab
```

Accepted `provider` values:

- `greenhouse`
- `ashby`
- `lever`
- `smartrecruiters`
- `workday`
- `workable`
- `custom`
- `unknown`

Accepted `scan_method` values:

- `api`
- `http`
- `browser`
- `search`
- `agent`

Accepted `requires` values:

- `http`
- `browser`
- `search`
- `agent`

Provider mapping:

- `https://job-boards.greenhouse.io/{slug}` -> `provider=greenhouse`, `provider_slug={slug}`
- `https://boards.greenhouse.io/{slug}` -> `provider=greenhouse`, `provider_slug={slug}`
- `https://jobs.ashbyhq.com/{slug}` -> `provider=ashby`, `provider_slug={slug}`
- `https://jobs.lever.co/{slug}` -> `provider=lever`, `provider_slug={slug}`
- `https://jobs.smartrecruiters.com/{slug}` -> `provider=smartrecruiters`, `provider_slug={slug}`
- `https://apply.workable.com/{slug}` -> `provider=workable`, `provider_slug={slug}`
- custom company career pages -> `provider=custom`

Career-ops import target:

- Port the 19 search-query presets and 76 tracked-company presets from
  `santifer/career-ops` `templates/portals.example.yml`.
- Keep search/browser-only sources disabled or capability-gated unless the
  implementation supports them.
- Prioritize active support for Greenhouse API, Ashby, Lever, and existing
  SmartRecruiters connector paths.

### `data/applications.md`

Career-ops-compatible export shape:

```markdown
| # | Date | Company | Role | Score | Status | PDF | Report | Notes |
|---|------|---------|------|-------|--------|-----|--------|-------|
| 42 | 2026-04-06 | Anthropic | Forward Deployed Engineer | 4.4/5 | Evaluated | [PDF](../output/cv-anthropic-2026-04-06.pdf) | [Report](../reports/042-anthropic-2026-04-06.md) | Review comp assumptions |
```

Rules:

- DB is authoritative.
- Export regenerates the file deterministically.
- Sync imports only allowed edits:
  - status
  - notes
  - possibly date
- Sync rejects or warns on changes to:
  - number
  - company
  - role
  - score unless explicitly overridden
  - report path
  - PDF path

Tracker status labels:

- `Drafting`
- `Evaluated`
- `Applied`
- `Responded`
- `Interview`
- `Offer`
- `Rejected`
- `Discarded`
- `SKIP`
- `Failed`

Map current internal statuses:

```text
drafting          -> Drafting
ready_for_review  -> Evaluated
submitted         -> Applied
failed            -> Failed
abandoned         -> Discarded
```

Prefer adding a separate lifecycle/tracker status rather than overloading
`ApplicationStatus`.

### `data/pipeline.md`

Shape:

```markdown
# Pipeline

## Pending

- [ ] https://example.com/job | Company | Title

## Processed

- [x] https://example.com/job | Company | Title
```

Rules:

- Users can paste URLs manually.
- Scanner can append discovered candidates.
- DB should track canonical queue state.
- Sync/import should dedupe by URL and normalized company/role.

### `data/scan-history.tsv`

Shape:

```text
url	first_seen	source	title	company	status	reason
https://example.com/job	2026-04-06	Greenhouse - AI Engineer	AI Engineer	Example	added	
https://example.com/other	2026-04-06	Ashby - AI PM	Intern PM	Example	skipped_title	negative keyword: Intern
```

Statuses:

- `added`
- `skipped_title`
- `skipped_dup`
- `skipped_capability`
- `failed_fetch`
- `failed_parse`

### Evaluation Result

Structured result should be persisted before rendering Markdown:

```json
{
  "application_id": 42,
  "job_id": 99,
  "company": "Anthropic",
  "role": "Forward Deployed Engineer",
  "score": 4.4,
  "recommendation": "apply",
  "summary": "Strong fit because ...",
  "dimensions": [
    {
      "name": "role_fit",
      "score": 4.5,
      "rationale": "..."
    }
  ],
  "gaps": ["..."],
  "risks": ["..."],
  "next_actions": ["..."],
  "draft_answers": []
}
```

Recommendations:

- `apply`
- `review`
- `hold`
- `skip`

Validation rules:

- `score` must be numeric and within `[0, 5]`.
- `recommendation` must be one of the accepted values.
- Required fields must be present before any state transition depends on the
  result.

## Phase 0: Workspace and Contract Foundation

Goal:

- Establish workspace paths, templates, and contracts without changing discovery
  behavior yet.

Files to add:

- `src/jobharbor/workspace.py`
- `src/jobharbor/cli.py`
- `templates/portals.example.yml`
- `templates/profile.example.yml`
- `templates/applications.md`
- `templates/pipeline.md`
- `templates/states.yml`
- `tests/test_workspace.py`
- `tests/test_cli_bootstrap.py`

Files to modify:

- `pyproject.toml`
- `src/jobharbor/config.py`
- `README.md`

Implementation steps:

1. Add `Settings.jobharbor_home`.
2. Add `WorkspacePaths` with properties for `cv_md`, `profile_yml`,
   `portals_yml`, `applications_md`, `pipeline_md`, `scan_history_tsv`,
   `reports_dir`, `output_dir`, and `jds_dir`.
3. Add a bootstrap service that creates directories and copies templates only
   when target files are missing.
4. Add a CLI entry point in `pyproject.toml`, for example:

```toml
[project.scripts]
jobharbor = "jobharbor.cli:main"
```

5. Implement `jobharbor bootstrap`.
6. Document `JOBHARBOR_HOME` and bootstrap usage in `README.md`.

Tests:

- `tests/test_workspace.py`
  - resolves paths under explicit temp `JOBHARBOR_HOME`
  - creates expected directories
  - does not overwrite existing files
- `tests/test_cli_bootstrap.py`
  - `jobharbor bootstrap` creates workspace files in a temp directory

Acceptance:

- A new user can run `jobharbor bootstrap`.
- Workspace files are created in a controlled location.
- Existing user files are preserved.
- Existing test suite still passes.

## Phase 1: Portal Config MVP

Goal:

- Port career-ops company/job-board presets into Jobharbor as YAML-driven scan
  configuration.

Files to add:

- `src/jobharbor/portal_config.py`
- `tests/test_portal_config.py`
- `tests/test_portal_provider_mapping.py`

Files to modify:

- `templates/portals.example.yml`
- `src/jobharbor/config.py`
- `src/jobharbor/workers/discover_stage.py`
- `src/jobharbor/services/auto_discovery.py`
- `README.md`

Implementation steps:

1. Create dataclasses or Pydantic-style models:
   - `PortalConfig`
   - `TitleFilterConfig`
   - `SearchQueryConfig`
   - `TrackedCompanyConfig`
2. Implement `load_portals_config(path: Path) -> PortalConfig`.
3. Implement provider inference from URL.
4. Implement capability checks:
   - Base MVP supports `http` and existing connector/API paths.
   - `browser`, `search`, and `agent` sources should be skipped unless explicitly
     enabled/configured.
5. Port career-ops defaults into `templates/portals.example.yml`.
6. Normalize career-ops fields:
   - `api` -> `api_url`
   - inferred `provider`
   - inferred `provider_slug`
   - inferred or explicit `scan_method`
7. Modify discovery to load `portals.yml` if present.
8. Build provider targets from enabled tracked companies.
9. Use existing connectors for Greenhouse, Ashby, Lever, and SmartRecruiters.
10. Log skipped capability-gated entries into run logs or context summary.

Tests:

- `test_loads_title_filter`
- `test_loads_tracked_companies`
- `test_infers_greenhouse_provider_slug`
- `test_infers_ashby_provider_slug`
- `test_infers_lever_provider_slug`
- `test_browser_only_company_is_skipped_without_browser_capability`
- `test_greenhouse_api_company_builds_connector_target`
- Existing `tests/test_discover_stage.py` remains green.

Acceptance:

- YAML config can represent all career-ops tracked companies and queries.
- Greenhouse/Ashby/Lever entries feed existing discovery connectors.
- Unsupported sources do not crash scans.
- Hardcoded defaults remain fallback behavior when no `portals.yml` exists.

## Phase 2: Rich Job Persistence

Goal:

- Persist enough job data for tracker/report/review surfaces.

Files to modify:

- `src/jobharbor/models.py`
- `src/jobharbor/db.py` if bootstrap handling needs adjustment
- `src/jobharbor/workers/discover_stage.py`
- `src/jobharbor/workers/queue_stage.py`
- `src/jobharbor/api/review.py`
- `tests/test_models_statuses.py`
- `tests/test_discover_stage.py`
- `tests/test_application_queue.py`
- `tests/test_review_api.py`

Recommended model:

- Add core display fields to `Job`:
  - `title: str | None`
  - `company: str | None`
  - `url: str | None`
  - `location: str | None`
  - `posted_at: str | None`
  - `description: str | None`
- Add provenance fields:
  - `provider: str | None`
  - `source_url: str | None`
  - `scan_query_name: str | None`

If description/raw payload size becomes a problem, add a later `JobDetail`
table. Do not overcomplicate Phase 2 unless tests force it.

Implementation steps:

1. Expand `Job` with nullable fields and indexes only where needed.
2. Update discovery persistence to upsert/populate fields.
3. Update queue stage to preserve detail fields when creating jobs from context.
4. Update review API response model to include `title`, `company`, `url`,
   `location`, and `source`.
5. Ensure old minimal rows still work.

Tests:

- job model includes new nullable fields.
- discovery persists title/company/url from discovered dicts.
- queue stage creates job with rich fields.
- review queue returns rich job fields.
- duplicate source/external_id still dedupes.

Acceptance:

- Review queue can display meaningful job information.
- Later report/tracker phases do not need transient pipeline context to know
  company/title/url.

## Phase 3: Tracker Export and Lifecycle Status

Goal:

- Add career-ops-compatible tracker export without making Markdown the canonical
  execution state.

Files to add:

- `src/jobharbor/tracker.py`
- `tests/test_tracker_export.py`
- `tests/test_tracker_status_mapping.py`

Files to modify:

- `src/jobharbor/models.py`
- `src/jobharbor/cli.py`
- `README.md`

Model choices:

- Add a tracker/lifecycle status field rather than overloading
  `ApplicationStatus`.
- Candidate field:
  - `tracker_status: str | None = Field(default=None, index=True)`
- Candidate note field:
  - `notes: str | None = None`

Implementation steps:

1. Define canonical tracker labels.
2. Implement mapping from `ApplicationStatus` to tracker label.
3. Implement `TrackerRow`.
4. Implement `TrackerExportService.export_applications`.
5. Implement `jobharbor tracker`.
6. Implement filters:
   - `--status`
   - `--min-score` can be stubbed until evaluation exists
   - `--company`
7. Implement commands:
   - `tracker show <id>`
   - `tracker set-status <id> <status>`
   - `tracker note <id> <note>`
   - `tracker export`
8. Defer full `tracker sync` if needed, but define parser tests now.

Tests:

- exports header and rows in career-ops-compatible shape.
- maps current statuses correctly.
- setting tracker status does not violate `ApplicationStatus` transitions.
- notes are escaped or sanitized for Markdown table output.
- export is deterministic.

Acceptance:

- User can open `data/applications.md` and see applications.
- User can update lifecycle status through CLI.
- Export can be regenerated from DB.

## Phase 4: Report Artifacts With Stub Evaluation

Goal:

- Create report infrastructure before integrating a real agent provider.

Files to add:

- `src/jobharbor/evaluation.py`
- `src/jobharbor/reports.py`
- `tests/test_evaluation_schema.py`
- `tests/test_report_renderer.py`

Files to modify:

- `src/jobharbor/models.py`
- `src/jobharbor/runner.py`
- `src/jobharbor/services/pipeline.py`
- `README.md`

Model additions:

- `Evaluation` table:
  - `id`
  - `application_id`
  - `job_id`
  - `score`
  - `recommendation`
  - `summary`
  - `payload_json`
  - `provider`
  - `created_at` if existing style supports it
- `Artifact` table:
  - `id`
  - `application_id`
  - `kind`
  - `path`
  - `created_at`

Implementation steps:

1. Define `EvaluationResult` structured type.
2. Add validation for score and recommendation.
3. Implement `StubEvaluationProvider` that creates deterministic fixture output
   from job title/company and profile presence.
4. Implement `ReportRenderer` that writes Markdown:
   - title/company
   - URL
   - score
   - recommendation
   - summary
   - gaps
   - risks
   - next actions
5. Add an `evaluate` stage or insert evaluation after `queue` and before
   `prefill/review`.
6. Store `Evaluation` and `Artifact` rows.
7. Export report links through tracker once artifacts exist.

Tests:

- invalid score rejected.
- invalid recommendation rejected.
- stub provider returns deterministic result.
- renderer produces expected Markdown fields.
- artifact row is stored.
- tracker export includes report link when report exists.

Acceptance:

- A queued application can produce a report without a live agent.
- Report output is deterministic in tests.

## Phase 5: Agent Provider Integration

Goal:

- Add Codex/generic agent evaluation behind a provider interface.

Files to add:

- `src/jobharbor/agents/base.py`
- `src/jobharbor/agents/command_provider.py`
- `src/jobharbor/agents/codex_provider.py` if Codex-specific behavior is needed
- `prompts/evaluation.md`
- `tests/test_agent_command_provider.py`

Files to modify:

- `src/jobharbor/evaluation.py`
- `src/jobharbor/config.py`
- `README.md`

Implementation steps:

1. Define provider protocol:

```text
evaluate(job, application, cv_text, profile_text, prompt_text) -> EvaluationResult
```

2. Add settings:
   - `evaluation_provider`: `stub`, `command`, `codex`, `openai_api` later
   - `evaluation_command`: optional command template for generic provider
   - `evaluation_timeout_seconds`
3. Load `cv.md`, `config/profile.yml`, and prompt template from workspace.
4. For command provider, pass input as JSON on stdin and expect JSON on stdout.
5. Validate output strictly before persisting.
6. On provider failure, mark evaluation failed without corrupting application
   state.
7. Keep `stub` as default for tests/offline runs.

Tests:

- command provider passes expected JSON input.
- malformed provider output is rejected.
- provider timeout is handled.
- failed provider does not transition application to applied/submitted.
- stub provider remains default in test settings.

Acceptance:

- Agent evaluation can be enabled without changing pipeline internals.
- Jobharbor remains usable without an agent.

## Phase 6: PDF Artifact Generation

Goal:

- Add tailored CV/PDF artifact pipeline.

Files to add:

- `src/jobharbor/pdf.py`
- `templates/cv-template.html`
- `tests/test_pdf_renderer.py`

Files to modify:

- `src/jobharbor/models.py` if `Artifact` kind enum/validation is needed.
- `src/jobharbor/tracker.py`
- `pyproject.toml` if adding a Python PDF dependency.
- `README.md`
- `Dockerfile` if browser runtime dependencies are added.

Recommendation:

- Use an interface first:

```text
PdfRenderer.render(application, evaluation, cv_text, profile) -> Path
```

- Implement a deterministic HTML writer in tests.
- Add Playwright-backed PDF generation only after the interface is stable.

Implementation steps:

1. Render tailored CV HTML from `cv.md`, profile, and evaluation.
2. Store HTML as intermediate artifact if useful.
3. Generate PDF when browser runtime is configured.
4. Store `Artifact(kind="pdf", path=...)`.
5. Update tracker export to link PDF.
6. If PDF generation fails, keep report and tracker row; mark PDF unavailable.

Tests:

- HTML renderer includes candidate/job fields.
- PDF renderer failure does not fail whole evaluation.
- tracker marks PDF unavailable when absent and links it when present.

Acceptance:

- High-fit applications can have a PDF artifact.
- Lack of browser support does not break scanning/evaluation.

## Phase 7: Pipeline Inbox

Goal:

- Add `data/pipeline.md` as a user-editable URL inbox backed by DB state.

Files to add:

- `src/jobharbor/pipeline_inbox.py`
- `tests/test_pipeline_inbox.py`

Files to modify:

- `src/jobharbor/cli.py`
- `src/jobharbor/models.py` if adding `PipelineItem`.
- `src/jobharbor/workers/discover_stage.py`
- `README.md`

Model addition:

- `PipelineItem`:
  - `id`
  - `url`
  - `company`
  - `title`
  - `status`: `pending`, `processing`, `processed`, `failed`, `skipped`
  - `source`
  - `application_id`

Implementation steps:

1. Implement parser for checkbox Markdown rows.
2. Implement deterministic writer.
3. Implement import from `data/pipeline.md` to DB.
4. Implement export from DB to `data/pipeline.md`.
5. Update scan to add new candidates as pending pipeline items when appropriate.
6. Implement `jobharbor pipeline` to process pending items.
7. Dedupe by URL and normalized company/title.

Tests:

- parses pending and processed rows.
- preserves unknown comments/sections if feasible, or documents rewrite behavior.
- imports new URL once.
- marks processed after successful evaluation/report.
- duplicate URL is skipped.

Acceptance:

- User can paste URLs into `data/pipeline.md`.
- Jobharbor can process them into applications/reports/tracker rows.

## Phase 8: Batch Processing

Goal:

- Process multiple pending URLs with bounded concurrency and resumability.

Files to add:

- `src/jobharbor/batch.py`
- `tests/test_batch_processing.py`

Files to modify:

- `src/jobharbor/cli.py`
- `src/jobharbor/models.py` if batch run table is needed.

Implementation steps:

1. Add `jobharbor pipeline --limit N`.
2. Add `jobharbor pipeline --concurrency N` only if async/process execution is
   implemented cleanly.
3. Track per-item status in DB.
4. Retry transient failures only.
5. Do not run unlimited agent calls.
6. Keep reports/tracker export deterministic.

Tests:

- limit is respected.
- failed item remains retryable.
- processed item is not reprocessed.
- concurrency setting does not duplicate work.

Acceptance:

- User can process a backlog without manually running one command per URL.

## Phase 9: Apply Assist

Goal:

- Draft form answers and optional fill plans without submitting applications.

Files to add:

- `src/jobharbor/apply_assist.py`
- `prompts/apply_assist.md`
- `tests/test_apply_assist.py`

Files to modify:

- `src/jobharbor/reports.py`
- `src/jobharbor/agents/base.py`
- `src/jobharbor/cli.py`
- `README.md`

Implementation steps:

1. Add `jobharbor apply-assist <application_id>`.
2. Load job, evaluation, report, CV, and profile.
3. Accept pasted questions or a local text file first.
4. Generate draft answers through provider interface.
5. Append or update a report section:
   - `## Draft Application Answers`
6. Optionally emit a fill plan:

```json
{
  "application_id": 42,
  "fields": [
    {
      "question": "Why this role?",
      "answer": "..."
    }
  ],
  "submit_allowed": false
}
```

7. Keep submit disabled by design.

Tests:

- drafts answers from fixture questions.
- report section is added deterministically.
- `submit_allowed` is always false.
- missing evaluation/report returns a clear error.

Acceptance:

- User can get application answers from existing context.
- The system cannot submit automatically.

## Phase 10: Optional UI/TUI/API Improvements

Goal:

- Add better review surfaces after the core workflow is stable.

Options:

- Extend FastAPI review endpoints.
- Add a simple server-rendered review page.
- Build or port a TUI similar to career-ops dashboard.

Do not start here. The tracker export, CLI, and reports should be stable first.

Acceptance:

- UI/TUI reads the same DB/exported state as CLI.
- UI/TUI does not introduce a separate state model.

## Implementation Sequencing Guidance

Recommended first PR:

```text
Phase 0 only: workspace contract and bootstrap CLI
```

Recommended second PR:

```text
Phase 1 only: portals.yml loader, template, provider mapping, and discovery integration
```

Recommended third PR:

```text
Phase 2 only: rich job persistence and review queue fields
```

Do not combine agent evaluation, PDF generation, and tracker sync in the same
PR. Those have different failure modes and should be reviewed separately.

## Verification Commands

Use the repo's existing pattern:

```bash
python3 -m venv .venv
./.venv/bin/pip install -e '.[dev]'
./.venv/bin/pytest -q
```

For targeted work, run specific tests first:

```bash
./.venv/bin/pytest tests/test_portal_config.py -q
./.venv/bin/pytest tests/test_discover_stage.py -q
./.venv/bin/pytest tests/test_review_api.py -q
```

Then run the full suite before final handoff if practical.

## Definition of Done for the Full Hybrid

The full hybrid is done when:

- `jobharbor bootstrap` creates a usable workspace.
- `portals.yml` drives discovery.
- Career-ops company/job-board presets are available as a template.
- Jobs persist title/company/url enough for review and reports.
- `data/pipeline.md` can ingest user-pasted URLs.
- `data/applications.md` exports tracker rows deterministically.
- Tracker lifecycle status can be updated without corrupting application state.
- Evaluations are structured and provider-backed.
- Stub evaluation works offline and in tests.
- Codex/generic command evaluation can be enabled.
- Markdown reports are generated.
- PDFs can be generated when browser/PDF support is configured.
- Apply assist can draft answers and cannot submit.
- Scheduled scans remain useful without an agent.
- Existing service deployment remains possible through Docker/systemd.

## Immediate Next Implementation Task

Start with Phase 0.

Do not implement agent evaluation first. The workspace, portal config, and data
ownership decisions need to exist before agent output has somewhere stable to
land.
