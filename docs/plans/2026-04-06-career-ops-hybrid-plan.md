# Jobharbor + Career-Ops Hybrid Plan

## Purpose

Explore how Jobharbor should evolve if we want the best parts of
`santifer/career-ops` without throwing away Jobharbor's service-oriented
foundation.

This is a planning document only. It is intentionally not an implementation
plan with code changes yet.

For a no-context implementation handoff, use
`docs/plans/2026-04-06-career-ops-hybrid-implementation.md`.

## Starting Point

### Jobharbor Today

Jobharbor is a Python service with a deterministic scheduled pipeline:

```text
discover -> normalize -> dedupe -> score -> queue -> prefill -> review -> notify
```

Strengths:

- Runs as a service via FastAPI, APScheduler, Docker, and systemd.
- Uses SQLite/SQLModel for durable state.
- Has explicit pipeline stages and unit tests.
- Already has connectors for Greenhouse, Ashby, Lever, SmartRecruiters, and Y Combinator.
- Already has discovery mechanisms for RSS feeds, career-page link extraction, provider URL extraction, and provider seed slugs.
- Has notification routing and a review queue API.
- Has a conservative human-in-the-loop policy through `ready_for_review`.

Current limitations relative to career-ops:

- Job records currently store only `source`, `external_id`, and status, so company/title/url/description are mostly pipeline context, not durable application data.
- Scoring is rule/filter oriented, not a rich CV-vs-JD evaluation.
- The main user output is API state and notifications, not report/PDF/tracker artifacts.
- There is no file-based application tracker or pipeline inbox.
- Discovery defaults are hardcoded in Python rather than a user-editable portal config.
- Prefill currently records payloads, but there is no full apply-assist workflow with form-question answers.

### Career-Ops Today

Career-ops is an agent-first, file-based job-search workspace.

Important pieces to borrow:

- `cv.md` as the candidate source of truth.
- `config/profile.yml` for identity, targets, compensation, location, and narrative.
- `portals.yml` for scanner configuration.
- `data/applications.md` as the human-readable tracker.
- `data/pipeline.md` as a pending URL inbox.
- `data/scan-history.tsv` for URL-level scan dedupe and audit history.
- `reports/` for per-role evaluations.
- `output/` for tailored PDFs.
- `templates/states.yml` as canonical tracker states.
- Prompt/mode files for evaluation, PDF generation, scanner, batch processing, tracker, apply assist, outreach, deep research, and interview prep.

Career-ops scanner defaults:

- 19 preconfigured search queries across Ashby, Greenhouse, Lever, Wellfound, Workable, RemoteFront, and broad cross-portal queries.
- 76 tracked companies in `templates/portals.example.yml`.
- Each tracked company can include:
  - `name`
  - `careers_url`
  - `api`
  - `scan_method`
  - `scan_query`
  - `notes`
  - `enabled`
- Companies are grouped around AI labs, voice AI, AI platforms, contact-center AI, enterprise comms, LLMOps, automation, Ashby-based companies, Lever-based companies, European tech, DACH, France, UK/Ireland, Nordics, and Iberia.

## Product Direction

Jobharbor should not become a clone of career-ops. It should become a hybrid:

```text
Jobharbor service kernel
  - scheduler
  - DB
  - connectors
  - dedupe
  - resumable pipeline
  - notifications
  - API

Career workspace layer
  - cv.md
  - profile.yml
  - portals.yml
  - applications.md
  - pipeline.md
  - scan-history.tsv
  - reports/
  - output/
  - prompt templates
```

The best-of-both-worlds principle:

- Use the database for correctness, state transitions, history, and service reliability.
- Use Markdown/YAML/TSV artifacts for transparency, agent ergonomics, and human workflow.
- Do not make Markdown the only source of truth for execution state.
- Do not make the DB the only interface the user can understand or edit.

## Intended User Experience

The target user experience is a private recruiting assistant, not a
spray-and-pray application bot.

The user maintains a small workspace:

- `cv.md`: canonical CV.
- `config/profile.yml`: target roles, locations, work authorization, compensation, deal-breakers, narrative, proof points, and preferences.
- `portals.yml`: companies and job boards to watch.
- `data/pipeline.md`: manual URL inbox for jobs the user wants processed.
- `data/applications.md`: human-readable tracker.
- `reports/`: role evaluations and application strategy.
- `output/`: generated tailored CVs/PDFs.

The service handles the repetitive work:

- scheduled scans
- provider API pulls
- career page discovery where supported
- dedupe
- hard filters
- structured evaluation
- queueing
- report generation
- PDF generation
- notifications
- status persistence

The user handles judgment:

- tune profile and filters
- review reports
- decide whether to apply
- submit applications manually
- update outcomes
- correct bad recommendations so future evaluations improve

### Daily Loop

In manual mode, the user might run:

```text
jobharbor scan
jobharbor pipeline
jobharbor tracker
```

In daemon mode:

- Jobharbor scans on a schedule.
- It only notifies the user when a role passes filters and reaches review.
- The notification points to the tracker row, report, PDF if available, and apply URL.

### Highest-Value Behavior

The goal is selectivity.

If Jobharbor scans 200 jobs and only surfaces 8 worth serious attention, that
is a successful run. The system should be optimized for conserving user
attention and recruiter attention, not for maximizing application volume.

The recommended user habit:

- Weekly: refine `profile.yml` and `portals.yml`.
- Daily: review the notification queue or `applications.md`.
- Per role: read the report before applying.
- After applying/interviewing: update status and notes.
- After bad recommendations: update filters/rubric/profile so future scans improve.

### Example End-to-End Flow

```text
1. User updates profile.yml with target roles and constraints.
2. User updates portals.yml with companies and boards to watch.
3. Jobharbor scan discovers jobs and records scan history.
4. Hard filters remove obvious misses.
5. Promising jobs become application candidates.
6. Evaluation produces score, rationale, report, and recommended action.
7. High-fit jobs get a tailored CV/PDF and draft application answers.
8. Tracker row is exported to applications.md.
9. User reviews the report and applies manually if worthwhile.
10. User marks the tracker row as applied, responded, interview, offer, rejected, discarded, or skipped.
```

## Functional Changes

### 1. Discovery Becomes User-Configurable

Today, Jobharbor has hardcoded defaults:

- `DEFAULT_FEED_URLS`
- `DEFAULT_MOBILE_COMPANY_CAREER_URLS`
- `DEFAULT_PROVIDER_TARGET_SEEDS`
- generated provider search queries from include keywords

Hybrid behavior:

- Introduce a `portals.yml` workspace config inspired by career-ops.
- Keep hardcoded defaults only as bootstrap defaults.
- Load tracked companies, API URLs, scan methods, scan queries, title filters, and enabled flags from YAML.
- Persist scan provenance so users can tell why a job was discovered.

Jobharbor should support these discovery inputs:

- RSS/public feeds, as it already does.
- Direct provider API, especially Greenhouse `boards-api.greenhouse.io`.
- Known provider boards: Greenhouse, Ashby, Lever, SmartRecruiters, Workday where feasible.
- Direct career pages.
- Search query results where an agent/search provider is available.

Important difference from career-ops:

- Career-ops assumes an agent can run WebSearch and Playwright as part of the scanner.
- Jobharbor should model this capability explicitly. A scan source should declare whether it needs:
  - HTTP only
  - browser rendering
  - search provider
  - agent assistance

This makes the system agent-agnostic instead of assuming Claude Code or Codex.

### 2. Jobs Need Richer Durable Data

To behave like career-ops, Jobharbor needs durable fields beyond `source` and
`external_id`.

Likely additions:

- `title`
- `company`
- `url`
- `location`
- `description`
- `posted_at`
- `source_url`
- `scan_query_name`
- `provider`
- `raw_payload`

Alternative:

- Keep `jobs` minimal and add a `job_snapshots` or `job_details` table keyed by `job_id`.

Recommendation:

- Add a separate detail/snapshot table if we expect descriptions and raw payloads to be large or mutable.
- Add core display fields (`title`, `company`, `url`) to `jobs` if the UI/API needs them constantly.

### 3. The Review Queue Becomes an Artifact Queue

Current behavior:

- Eligible jobs create `Application` rows.
- Prefill creates a payload.
- Notify sends a link to review.

Hybrid behavior:

- Eligible jobs create or update an application.
- Evaluation generates a report and score rationale.
- PDF generation creates a tailored CV artifact when applicable.
- Apply-assist generates draft answers and optionally a fill plan.
- Review queue points to:
  - job title/company/url
  - score
  - report path
  - PDF path
  - draft answers path or report section
  - status transition actions

### 4. Scoring Evolves From Filter to Evaluation

Keep existing filters. They are useful gates:

- include keywords
- exclude keywords
- location policy
- work authorization
- connector rollout/source policy

Add a second layer:

- structured CV-vs-JD evaluation
- weighted dimensions
- recommendation threshold
- gap/mitigation notes
- compensation/location risk
- role archetype classification
- suggested application strategy

Proposed scoring flow:

```text
hard filters -> structured evaluation -> decision policy
```

Hard filters answer: "Should we spend evaluation time on this?"

Structured evaluation answers: "Is this worth applying to, and why?"

Decision policy answers: "Queue, skip, hold, or ask for manual review?"

### 5. Agent-Agnostic Evaluation

Career-ops uses prompt files directly through Claude Code. Jobharbor should instead define an interface:

```text
EvaluationProvider.evaluate(job, profile, cv, rubric) -> EvaluationResult
```

Provider implementations can be:

- `codex_cli`
- `claude_cli`
- `openai_api`
- `manual_stub`
- `local_fixture` for tests

The output should be structured first, then rendered:

- `evaluation.json` or DB row for deterministic downstream use.
- `reports/{id}-{company}-{date}.md` for humans/agents.

This avoids coupling the product to a single agent runtime.

### Agent Role: Codex as Analyst, Not State Machine

Codex should be the reasoning and customization layer, not the core execution
engine.

Jobharbor should own reliable mechanics:

- scheduled scans
- connector execution
- DB state
- dedupe
- queueing
- status transitions
- artifact path persistence
- tracker export/import
- notification delivery
- retries and resumability

Codex should own judgment-heavy and writing-heavy work:

- setup and personalization
- `profile.yml` edits
- `portals.yml` edits
- rubric and prompt-template edits
- role fit evaluation
- report drafting
- tailored CV recommendations
- application-answer drafting
- high-value company/role research
- feedback incorporation when the user says a score or recommendation is wrong

Codex should not be required for every scheduled scan. A better flow is:

```text
Jobharbor scans 200 jobs.
Jobharbor filters and dedupes to 20 plausible jobs.
Jobharbor queues 8 strong candidates for agent evaluation.
Codex evaluates those 8 against cv.md and profile.yml.
Jobharbor stores structured results and exports report/tracker/PDF paths.
The user reviews and decides whether to apply.
```

This keeps agent usage focused where it has the highest leverage. It also keeps
the system cheaper, more deterministic, and easier to test.

Implementation implication:

- Agent calls should sit behind provider interfaces.
- Provider outputs should be structured and validated before they affect state.
- Prompt files should be editable workspace/system artifacts, not hardcoded Python strings.
- A `manual_stub` or fixture provider should exist for tests and offline runs.
- Jobharbor should be useful without an agent, but more valuable with one.

### 6. Career-Ops Tracker Compatibility

Career-ops tracker row shape:

```markdown
| # | Date | Company | Role | Score | Status | PDF | Report | Notes |
```

Jobharbor can export this from DB state.

Recommendation:

- DB remains authoritative for application state.
- `data/applications.md` is generated or reconciled, not blindly appended by many writers.
- Status edits in Markdown can be imported only through an explicit command such as `jobharbor tracker sync`.

This prevents drift while keeping the transparent tracker UX.

### Tracker Interaction Model

The tracker should support three interaction styles:

- Markdown-first: user opens `data/applications.md` and reads/edits it directly.
- CLI-first: user runs `jobharbor tracker` commands.
- UI/API-first: user uses a web review page, TUI, or API endpoint backed by the same DB state.

Recommended first implementation:

- DB is authoritative.
- `data/applications.md` is a deterministic export.
- Manual edits to `data/applications.md` are imported only through an explicit sync command.
- If both DB and Markdown changed the same row, the sync command reports a conflict instead of guessing.

#### Tracker Views

The user should be able to answer these questions quickly:

- What should I review today?
- Which roles scored highest?
- Which jobs have generated PDFs?
- Which applications have I submitted?
- Which companies responded?
- Which applications are in interview stage?
- Which roles were skipped and why?
- Which reports need manual review because extraction/evaluation was incomplete?

Proposed tracker commands:

```text
jobharbor tracker
jobharbor tracker --status ready_for_review
jobharbor tracker --status applied
jobharbor tracker --min-score 4.0
jobharbor tracker --company Anthropic
jobharbor tracker show 42
jobharbor tracker open-report 42
jobharbor tracker open-pdf 42
jobharbor tracker set-status 42 applied
jobharbor tracker note 42 "Applied via Greenhouse. Mentioned agent work."
jobharbor tracker sync
jobharbor tracker export
```

`open-report` and `open-pdf` may be CLI path printers in headless/server
contexts rather than GUI openers.

#### Tracker Row Shape

Use the career-ops-compatible shape for Markdown export:

```markdown
| # | Date | Company | Role | Score | Status | PDF | Report | Notes |
|---|------|---------|------|-------|--------|-----|--------|-------|
| 42 | 2026-04-06 | Anthropic | Forward Deployed Engineer | 4.4/5 | Evaluated | [PDF](../output/cv-anthropic-2026-04-06.pdf) | [Report](../reports/042-anthropic-2026-04-06.md) | Review comp assumptions |
```

Possible extra columns later:

- `URL`
- `Source`
- `Location`
- `Next Action`
- `Last Updated`

Recommendation:

- Keep the exported Markdown tracker close to career-ops initially for dashboard compatibility.
- Put richer data in DB and reports instead of widening the Markdown table too early.

#### Tracker Status Model

Career-ops uses human tracker states like:

- `Evaluated`
- `Applied`
- `Responded`
- `Interview`
- `Offer`
- `Rejected`
- `Discarded`
- `SKIP`

Jobharbor currently uses application states like:

- `drafting`
- `ready_for_review`
- `submitted`
- `failed`
- `abandoned`

Proposed mapping:

```text
drafting          -> Drafting
ready_for_review  -> Evaluated
submitted         -> Applied
failed            -> Failed
abandoned         -> Discarded
```

New tracker-level states can exist without immediately expanding the core
application state machine:

```text
responded
interview
offer
rejected
skip
```

Open decision:

- Either expand `ApplicationStatus` to include the full job-search lifecycle.
- Or add a separate `tracker_status`/`outcome_status` field for post-submit lifecycle tracking.

Recommendation:

- Add a separate lifecycle/tracker status. It keeps the current application state machine simple while still tracking the user's real job-search pipeline.

#### Tracker Sync Rules

To prevent file/DB drift:

- `jobharbor tracker export` regenerates `data/applications.md` from DB.
- `jobharbor tracker sync` imports allowed edits from Markdown.
- Allowed Markdown edits:
  - status
  - notes
  - possibly date
- Disallowed Markdown edits:
  - application number
  - company
  - role
  - report path
  - PDF path
  - score, unless explicitly using an override command
- If a disallowed field changes, report it as a warning and keep DB values.
- If both DB and Markdown changed status since last export, report a conflict.

This lets the user treat Markdown as a friendly surface without letting it
corrupt execution state.

#### Tracker Max-Value Use

The tracker should not be only a log. It should be the user's decision surface.

High-value tracker affordances:

- "Review today" view: high-score, not-yet-applied roles with report/PDF ready.
- "Stale" view: applied roles with no response after N days.
- "Follow-up" view: responded/interview roles with next-action notes.
- "Learning" view: skipped/rejected roles with reasons, so profile filters can improve.
- "Portfolio" view: roles where tailored artifacts exist and could be reused.

The tracker should make it easy to ask:

```text
What are the 5 applications worth my attention right now?
```

That is more valuable than simply counting total applications.

### 7. Pipeline Inbox Compatibility

Career-ops uses `data/pipeline.md` for pending URLs.

Jobharbor can support this as an ingestion queue:

```markdown
- [ ] https://example.com/job | Company | Title
- [x] https://example.com/job | Company | Title
```

Proposed behavior:

- `scan` writes new candidates to `data/pipeline.md` and DB.
- `pipeline` processes pending items and marks them done after successful artifact generation.
- The DB stores the canonical queue item state.
- The Markdown file stays a human-editable inbox for adding URLs manually.

## Porting Career-Ops Companies and Job Boards

### What Can Be Ported Directly

Career-ops `templates/portals.example.yml` can become Jobharbor's initial
`templates/portals.example.yml` or `config/portals.example.yml`.

Directly reusable data:

- Title filters: positive, negative, and seniority boost terms.
- Search query names and query text.
- Company names.
- Career URLs.
- Greenhouse API URLs.
- Notes.
- Enabled flags.

### What Needs Translation

Career-ops fields are written for an agent scanner. Jobharbor needs an explicit execution model.

Suggested normalized schema:

```yaml
title_filter:
  positive: []
  negative: []
  seniority_boost: []

search_queries:
  - name: Ashby - AI PM
    query: 'site:jobs.ashbyhq.com "AI Product Manager" remote'
    enabled: true
    requires: search

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

Additional Jobharbor fields to consider:

- `provider`: `greenhouse`, `ashby`, `lever`, `smartrecruiters`, `workday`, `workable`, `custom`, `unknown`
- `provider_slug`: normalized slug for connector construction
- `scan_method`: `api`, `http`, `browser`, `search`, `agent`
- `requires`: capability list such as `[http]`, `[browser]`, `[search]`
- `regions`: optional tags like `us`, `remote`, `emea`, `dach`
- `role_tags`: optional tags like `ai`, `mobile`, `platform`, `solutions`
- `priority`: optional numeric priority for scan order
- `owner_notes`: user-maintained notes

### Provider Mapping Rules

Career-ops URLs can be mapped automatically:

- `https://job-boards.greenhouse.io/{slug}` -> `provider=greenhouse`, `provider_slug={slug}`, API usually available at `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`
- `https://boards.greenhouse.io/{slug}` -> `provider=greenhouse`, `provider_slug={slug}`
- `https://jobs.ashbyhq.com/{slug}` -> `provider=ashby`, `provider_slug={slug}`
- `https://jobs.lever.co/{slug}` -> `provider=lever`, `provider_slug={slug}`
- `https://jobs.smartrecruiters.com/{slug}` -> `provider=smartrecruiters`, `provider_slug={slug}`
- `https://apply.workable.com/{slug}` -> `provider=workable`, connector not currently present
- custom company career pages -> `provider=custom`, likely `scan_method=browser` or `search`

### Porting Strategy

Do not hardcode the 76 companies into Python. Use a YAML template:

- Add `templates/portals.example.yml` or `config/portals.example.yml`.
- Add a loader and validator.
- During bootstrap, copy the template into the user's workspace as `portals.yml`.
- Jobharbor reads `portals.yml` at scan time.
- Existing Python defaults remain fallback only.

Phased import:

1. Import Greenhouse API-backed companies first. They are easiest and most reliable.
2. Import Ashby and Lever companies next using existing connectors.
3. Import SmartRecruiters where existing connector support is adequate.
4. Keep Workable/custom/company-site entries in YAML but mark them as requiring browser/search until support is implemented.
5. Keep search queries disabled or capability-gated until a search provider is configured.

Why not import everything as active immediately:

- Some career-ops entries depend on WebSearch or Playwright.
- Jobharbor's current direct HTML fetcher will miss many SPA-rendered careers pages.
- Enabling all custom/search entries without capability checks would produce noisy failures.

## Suggested Architecture

### Workspace Layer

New concept:

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
```

Default:

- If `JOBHARBOR_HOME` is unset, use the project root in development and `/app/workspace` in containers.

Rules:

- User-owned files are never overwritten by updates.
- Templates can be updated.
- Bootstrap creates missing files, but does not replace existing files.

### Data Model Layer

Candidate additions:

- `JobDetail` or expanded `Job`.
- `Evaluation`.
- `Artifact`.
- `ScanSource`.
- `PipelineItem`.

Keep `Application` status transitions, but consider aligning statuses with tracker concepts:

- `drafting`
- `ready_for_review`
- `evaluated`
- `applied`
- `responded`
- `interview`
- `offer`
- `rejected`
- `discarded`
- `failed`
- `abandoned`

Open question:

- Do we expand `ApplicationStatus`, or keep internal statuses smaller and map them to external tracker states?

Recommendation:

- Keep internal statuses conservative initially.
- Add a separate tracker/export status if needed.

### Service Layer

New or expanded services:

- `PortalConfigService`: load and validate `portals.yml`.
- `ScanHistoryService`: append/read `scan-history.tsv` and/or DB scan records.
- `PipelineInboxService`: reconcile `data/pipeline.md` with DB queue items.
- `EvaluationService`: call a provider and return structured evaluation.
- `ReportRenderer`: render structured evaluation to Markdown.
- `PdfRenderer`: render CV/profile/evaluation to HTML/PDF.
- `TrackerExportService`: render DB state to `data/applications.md`.

### CLI Layer

Add CLI commands after the services exist:

```text
jobharbor bootstrap
jobharbor scan
jobharbor ingest <url-or-file>
jobharbor pipeline
jobharbor tracker
jobharbor verify
```

The API can call the same services later.

## Phased Plan

### Phase 0: Decide the Contract

Deliverables:

- Workspace contract.
- `portals.yml` schema.
- tracker row schema.
- scan history schema.
- evaluation result schema.
- artifact naming conventions.

Acceptance:

- We can explain which state is DB-authoritative and which state is file-exported.
- We can explain how manual file edits are imported or ignored.

### Phase 1: Portal Config MVP

Deliverables:

- Port `career-ops` title filters and company list into a Jobharbor template.
- Loader validates `title_filter`, `search_queries`, and `tracked_companies`.
- Discovery stage can build provider targets from YAML instead of hardcoded defaults.
- Capability-gate browser/search-only sources.

Acceptance:

- Greenhouse/Ashby/Lever companies from the template can be scanned through existing connectors.
- Browser/search/custom entries are skipped with clear run logs unless capability is enabled.

### Phase 2: Rich Job Persistence

Deliverables:

- Persist title/company/url/location/description or job details.
- Store discovery provenance.
- Update queue/review APIs to expose display fields.

Acceptance:

- Review queue can show meaningful job information without relying on transient pipeline context.

### Phase 3: Report and Tracker Export

Deliverables:

- Structured evaluation placeholder or provider stub.
- Markdown report renderer.
- `data/applications.md` exporter.
- Artifact paths stored in DB.

Acceptance:

- A queued application can produce a report path and tracker row.
- The tracker can be regenerated from DB.

### Phase 4: Agent Evaluation

Deliverables:

- Provider interface.
- Codex CLI provider or generic external-command provider.
- Prompt templates stored as files.
- Structured output validation.

Acceptance:

- The system can evaluate one JD against `cv.md` and `profile.yml` and produce a stable JSON result plus Markdown report.

### Phase 5: PDF Generation

Deliverables:

- HTML CV template.
- PDF renderer, probably Playwright-backed.
- PDF artifact naming and DB linkage.

Acceptance:

- A high-fit application produces a tailored PDF and tracker row marks PDF as available.

### Phase 6: Pipeline Inbox and Batch

Deliverables:

- `data/pipeline.md` parser/exporter.
- `jobharbor pipeline` command.
- Batch queue with concurrency limits and retries.

Acceptance:

- New URLs can be pasted into `pipeline.md`, processed, and reflected in reports/tracker.

### Phase 7: Apply Assist

Deliverables:

- Form question extraction plan.
- Draft answer generation.
- Report section for application answers.
- Optional Playwright fill plan.

Acceptance:

- Jobharbor can assist with application forms but cannot submit without explicit human action.

## Risks and Tradeoffs

### File/DB Drift

Risk:

- If both DB and Markdown are writable, they can disagree.

Mitigation:

- Make DB authoritative for execution.
- Make exports deterministic.
- Require explicit import/sync for manual tracker edits.

### Browser/Search Capability

Risk:

- Career-ops assumes agent browser/search access. A server process may not have it.

Mitigation:

- Capability-gate sources.
- Prefer provider APIs where possible.
- Use browser/search as optional adapters, not core assumptions.

### Over-Automation

Risk:

- A richer pipeline can drift toward spray-and-pray automation.

Mitigation:

- Preserve no-auto-submit as a hard rule.
- Use evaluation thresholds to discourage weak-fit applications.
- Keep manual review before apply.

### Prompt Fragility

Risk:

- Rich evaluation quality depends on prompt quality and candidate profile quality.

Mitigation:

- Use structured output schemas.
- Store prompt templates in versioned files.
- Include provider stubs/fixtures for tests.
- Let users refine `profile.yml`, `cv.md`, and scoring/rubric files over time.

## Open Questions

- Should Jobharbor use the exact career-ops tracker states, or map internal statuses to them?
- Should `applications.md` be regenerated every run, append-only, or syncable with conflict detection?
- Should reports be generated for every eligible job or only above a threshold?
- Should the scanner write directly to DB, `data/pipeline.md`, or both?
- Should `portals.yml` live in the repo root, `config/`, or `JOBHARBOR_HOME`?
- Which provider should be implemented first for evaluation: Codex CLI, OpenAI API, or a generic command adapter?
- Do we need the Go TUI, a FastAPI web page, or is Markdown/API enough for the first parity milestone?

## Recommended First Concrete Slice

Start with portal config and workspace contract, not LLM evaluation.

Reason:

- The company/job-board port is high leverage and fits existing Jobharbor discovery.
- It improves the project without committing to a specific agent provider.
- It forces the right data-model decisions before report/PDF generation.

Proposed first slice:

1. Define `portals.yml` schema and workspace location.
2. Port the 76 tracked companies and 19 queries as a template.
3. Load enabled Greenhouse/Ashby/Lever entries into discovery.
4. Skip browser/search-only entries with explicit run-log reasons.
5. Persist enough job details for review and later reports.

After that, add the report/tracker/PDF layer.
