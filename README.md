# jobharbor

Personal Job Agent (Greenhouse -> Ashby -> Lever).

## Local Development

```bash
python3 -m venv .venv
./.venv/bin/pip install -e .[dev]
./.venv/bin/pytest -q
```

## MVP Verification

```bash
./scripts/verify_mvp.sh
```

## Homelab Deployment

1. Copy `.env.example` to `.env`, fill credentials, and leave `DATABASE_URL` unset so Compose overrides it.
2. Build and run with Docker Compose:

```bash
docker compose up -d --build
```

3. Create a `config.yaml` with the values you care about and run the helper before `docker compose up`. A sample config looks like:

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

If it succeeds, set `JOBHARBOR_CONFIG_PATH=$(pwd)/config.yaml` (or leave configuration in the repo root as `config.yaml`) so the service can discover it automatically.

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
