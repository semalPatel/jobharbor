# jobharbor

Personal job discovery and review dashboard for DB-backed, manually submitted applications.

## Local Development

```bash
python3 -m venv .venv
./.venv/bin/pip install -e '.[dev]'
./.venv/bin/pytest -q
```

## MVP Verification

```bash
./scripts/verify_mvp.sh
```

The verifier runs the full offline test suite plus bootstrap, pipeline inbox,
tracker export, and dashboard render smokes. It does not call live job boards.

## Workspace Bootstrap

Jobharbor keeps user-editable career-ops files under `JOBHARBOR_HOME`. If the
environment variable is not set, the default workspace is `./workspace`.

Create the workspace with:

```bash
export JOBHARBOR_HOME="$PWD/workspace"
export JOBHARBOR_PROFILE_PATH="$JOBHARBOR_HOME/config/profile.yml"
export DATABASE_URL="sqlite:///$PWD/jobharbor.db"
uv run --python 3.12 --extra dev jobharbor bootstrap
```

For local testing, point bootstrap at an explicit directory:

```bash
jobharbor bootstrap --home /path/to/jobharbor-workspace
```

Bootstrap creates missing directories and files such as `cv.md`,
`config/profile.yml`, `portals.yml`, `data/applications.md`,
`data/pipeline.md`, `data/scan-history.tsv`, `reports/`, `output/`, `jds/`,
`prompts/`, and `templates/`. Existing files are preserved.

`portals.yml` can define `title_filter`, `search_queries`, and
`tracked_companies`. Enabled Greenhouse, Ashby, Lever, and SmartRecruiters
company entries with `api` or `http` scan methods feed the existing discovery
connectors. Entries requiring `browser`, `search`, or `agent` capabilities are
kept in the file but skipped until those capabilities are enabled. Search is
disabled by default; enable it explicitly with:

```bash
export JOBHARBOR_DISCOVERY_CAPABILITIES=http,search
```

Automatic mode starts the scheduler, runs one scan on startup, and then repeats
on the configured interval:

```bash
uv run --python 3.12 --extra dev uvicorn jobharbor.main:app --host 0.0.0.0 --port 8000
```

Review the DB-backed dashboard at:

```text
http://127.0.0.1:8000/review/dashboard
```

Export the career-ops-compatible tracker with:

```bash
jobharbor tracker
jobharbor tracker show 42
jobharbor tracker set-status 42 Applied
jobharbor tracker note 42 "Applied via Greenhouse."
```

Queued applications now get a deterministic stub evaluation report under
`reports/` before any live agent provider is configured. The tracker links the
latest report artifact when one exists.

To use an external evaluator, set `EVALUATION_PROVIDER=command` and provide an
`EVALUATION_COMMAND`. Jobharbor sends JSON on stdin and expects validated
EvaluationResult JSON on stdout. `EVALUATION_PROVIDER=stub` remains the default
so scheduled scans can run without an agent.

Jobharbor can also persist PDF artifacts through the local renderer interface.
When a PDF artifact exists, `jobharbor tracker` links it from the `PDF` column;
renderer failures leave existing reports and tracker rows intact.

For a manual inbox flow, paste jobs into `data/pipeline.md` and run:

```bash
uv run --python 3.12 --extra dev jobharbor pipeline --limit 3
uv run --python 3.12 --extra dev jobharbor pipeline --limit 3 --concurrency 1
uv run --python 3.12 --extra dev jobharbor tracker
```

Pipeline items are stored in the database, deduped by URL, processed into
applications, and rewritten back to `data/pipeline.md` as processed rows.

After a report exists, draft application answers without submitting:

```bash
jobharbor apply-assist 42 --questions-file questions.txt
```

The review API also exposes a lightweight dashboard at `/review/dashboard`.
It reads the same database state as `jobharbor tracker` and links job, report,
and PDF artifacts when available. Dashboard actions can mark an application as
applied/submitted, mark it discarded, or update notes. Jobharbor does not submit
applications automatically.

### Environment

| Variable | Description |
| --- | --- |
| `JOBHARBOR_HOME` | Workspace root containing `cv.md`, `portals.yml`, `data/`, `reports/`, and `output/`. |
| `DATABASE_URL` | SQLModel database URL, for example `sqlite:///$PWD/jobharbor.db`. |
| `JOBHARBOR_CONFIG_PATH` | Optional YAML runtime config path. |
| `JOBHARBOR_PROFILE_PATH` | Profile/rubric path, normally `$JOBHARBOR_HOME/config/profile.yml`. |
| `JOBHARBOR_DISCOVERY_CAPABILITIES` | Comma-separated discovery capabilities. Default: `http`. Optional: `search`, `browser`, `agent`. |
| `EVALUATION_PROVIDER` | `stub`, `command`, or `codex`. Default: `stub`. |
| `EVALUATION_COMMAND` | Command used when `EVALUATION_PROVIDER=command` or `codex`. |
| `EVALUATION_TIMEOUT_SECONDS` | External evaluator timeout. Default: `60`. |

## Homelab Deployment

1. Copy `.env.example` to `.env`, fill credentials, and leave `DATABASE_URL` unset so Compose overrides it.
2. Create a `config.yaml` with the values you care about, run the helper, and point `JOBHARBOR_CONFIG_PATH` at it (or keep the file at `config.yaml` in the repo root). A sample config looks like:

```yaml
scan_interval_hours: 6
include_domain_keywords:
  - android
  - kotlin
allowed_location_keywords:
  - remote
allowed_work_auth:
  - us_authorized
connector_rollout:
  - greenhouse
  - ashby
  - lever
discovery_capabilities:
  - http
```

Run the validator as:

```bash
python scripts/apply_config.py config.yaml
```

If it succeeds, either run `export JOBHARBOR_CONFIG_PATH="$(pwd)/config.yaml"` in the shell that launches Docker Compose or copy the absolute path (e.g., `/full/path/config.yaml`) into `.env` so the service can discover it automatically.

### Supported YAML values

The helper currently recognizes these top-level keys; leave entries empty to fall back to the runtime defaults.

| Key | Description | Notes |
| --- | --- | --- |
| `scan_interval_hours` | Scan cadence in hours. | Must be positive; defaults to `6`. |
| `include_domain_keywords` | Keywords/phrases that must appear in the job text. | Matching is phrase-based and case-insensitive. |
| `exclude_domain_keywords` | Keywords/phrases that reject a job if present. | Phrase-based matching. |
| `allowed_location_keywords` | Location keywords that must appear. | Leave empty to skip location filtering. |
| `allowed_work_auth` | Normalized work-authorization strings (e.g., `us_authorized`). | Spaces/punctuation become underscores. |
| `connector_rollout` | Connector order used by discovery (`greenhouse`, `ashby`, `lever`, `smartrecruiters`). | Trim or reorder to experiment with sources. |
| `discovery_capabilities` | Enabled discovery capabilities (`http`, optionally `search`, `browser`, `agent`). | Keep `search`, `browser`, and `agent` off unless explicitly configured. |

3. Build and run with Docker Compose:

```bash
docker compose up -d --build
```

4. The container boots the scan scheduler on startup (runs one cycle immediately and every 6 hours), uses `/app/workspace` for `JOBHARBOR_HOME`, and keeps the SQLite file under `./data/jobharbor.db` thanks to `DATABASE_URL=sqlite:////app/data/jobharbor.db`.
5. Verify API health:

```bash
curl -fsS http://localhost:8080/health
```

## systemd Service

Install [ops/systemd/jobharbor.service](ops/systemd/jobharbor.service) to `/etc/systemd/system/jobharbor.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now jobharbor
```
