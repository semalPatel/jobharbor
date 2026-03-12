# jobharbor

Personal Job Agent (Greenhouse -> Ashby -> Lever).

## Local Development

```bash
python3 -m venv .venv
./.venv/bin/pip install -e .[dev]
./.venv/bin/pytest -q
```

## Homelab Deployment

1. Copy `.env.example` to `.env` and fill credentials.
2. Build and run with Docker Compose:

```bash
docker compose up -d --build
```

3. Verify API health:

```bash
curl -fsS http://localhost:8080/health
```

## systemd Service

Install [ops/systemd/jobharbor.service](ops/systemd/jobharbor.service) to `/etc/systemd/system/jobharbor.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now jobharbor
```
