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

3. The container boots the scan scheduler on startup (runs one cycle immediately and every 6 hours) and the SQLite file stays under `./data/jobharbor.db` thanks to `DATABASE_URL=sqlite:////app/data/jobharbor.db`.
4. Verify API health:

```bash
curl -fsS http://localhost:8080/health
```

## systemd Service

Install [ops/systemd/jobharbor.service](ops/systemd/jobharbor.service) to `/etc/systemd/system/jobharbor.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now jobharbor
```
