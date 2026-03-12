#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTEST="${ROOT_DIR}/.venv/bin/pytest"
PYTHON="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTEST}" ]]; then
  echo "missing pytest executable at ${PYTEST}" >&2
  exit 1
fi

if [[ ! -x "${PYTHON}" ]]; then
  echo "missing python executable at ${PYTHON}" >&2
  exit 1
fi

echo "[verify] unit tests"
"${PYTEST}" -q tests/test_health.py tests/test_config.py tests/test_models_statuses.py

echo "[verify] pipeline smoke"
"${PYTEST}" -q tests/test_pipeline_e2e_smoke.py

echo "[verify] api health"
"${PYTHON}" - <<'PY'
from fastapi.testclient import TestClient

from jobharbor.main import app

client = TestClient(app)
response = client.get("/health")
assert response.status_code == 200
assert response.json() == {"ok": True}
print("health check ok")
PY

echo "[verify] all checks passed"
