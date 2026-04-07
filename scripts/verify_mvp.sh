#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV_CACHE_DIR="${UV_CACHE_DIR:-${ROOT_DIR}/.uv-cache}"
RUN=(env "UV_CACHE_DIR=${UV_CACHE_DIR}" uv run --python 3.12 --extra dev)
SMOKE_HOME="$(mktemp -d)"
SMOKE_DB="${SMOKE_HOME}/jobharbor.db"

cleanup() {
  rm -rf "${SMOKE_HOME}"
}
trap cleanup EXIT

echo "[verify] full test suite"
(cd "${ROOT_DIR}" && "${RUN[@]}" pytest -q)

echo "[verify] bootstrap smoke"
(cd "${ROOT_DIR}" && env JOBHARBOR_HOME="${SMOKE_HOME}/workspace" DATABASE_URL="sqlite:///${SMOKE_DB}" "${RUN[@]}" jobharbor bootstrap)

echo "[verify] pipeline inbox smoke"
(cd "${ROOT_DIR}" && env JOBHARBOR_HOME="${SMOKE_HOME}/workspace" DATABASE_URL="sqlite:///${SMOKE_DB}" "${RUN[@]}" jobharbor pipeline --limit 3 --concurrency 1)

echo "[verify] tracker export smoke"
(cd "${ROOT_DIR}" && env JOBHARBOR_HOME="${SMOKE_HOME}/workspace" DATABASE_URL="sqlite:///${SMOKE_DB}" "${RUN[@]}" jobharbor tracker)

echo "[verify] dashboard render smoke"
(cd "${ROOT_DIR}" && env JOBHARBOR_HOME="${SMOKE_HOME}/workspace" DATABASE_URL="sqlite:///${SMOKE_DB}" "${RUN[@]}" python - <<'PY'
from sqlmodel import Session

from jobharbor.api.review import review_dashboard
from jobharbor.db import get_engine, init_db
from jobharbor.main import health

assert health() == {"ok": True}
engine = get_engine()
init_db(engine=engine)
with Session(engine) as session:
    dashboard = review_dashboard(session=session)
assert dashboard.status_code == 200
assert "Jobharbor Review" in dashboard.body.decode("utf-8")
print("dashboard render ok")
PY
)

echo "[verify] all checks passed"
