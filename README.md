# jobharbor

Personal Job Agent (Greenhouse -> Ashby -> Lever).

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

## Workspace Bootstrap

Jobharbor keeps user-editable career-ops files under `JOBHARBOR_HOME`. If the
environment variable is not set, the default workspace is `./workspace`.

Create the workspace with:

```bash
jobharbor bootstrap
```

For local testing, point bootstrap at an explicit directory:

```bash
jobharbor bootstrap --home /path/to/jobharbor-workspace
```

Bootstrap creates missing directories and files such as `cv.md`,
`config/profile.yml`, `portals.yml`, `data/applications.md`,
`data/pipeline.md`, `data/scan-history.tsv`, `reports/`, `output/`, `jds/`,
`prompts/`, and `templates/`. Existing files are preserved.

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
| `connector_rollout` | Connector order used by discovery (`greenhouse`, `ashby`, `lever`). | Trim or reorder to experiment with sources. |

3. Build and run with Docker Compose:

```bash
docker compose up -d --build
```

4. The container boots the scan scheduler on startup (runs one cycle immediately and every 6 hours) and the SQLite file stays under `./data/jobharbor.db` thanks to `DATABASE_URL=sqlite:////app/data/jobharbor.db`.
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
