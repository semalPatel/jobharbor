# YAML Configuration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow operators to describe cadence, keywords, and general pipeline options via a declarative YAML file so every configurable value can be edited before the scheduler launches.

**Architecture:** Introduce a YAML-backed config loader that merges `config.yaml` into the existing `Settings`/pipeline runtime, expose a quick CLI script for validating that file, and document the workflow in the README so running the container always consumes the YAML values before any scan executes.

**Tech Stack:** Python 3.12, PyYAML (new dependency), FastAPI startup hook, SQLModel/session utilities, existing scheduler runner.

---

### Task 1: YAML schema + loader

**Files:**
- Create: `src/jobharbor/config_schema.py`
- Modify: `src/jobharbor/config.py`
- Test: `tests/test_yaml_config.py`

**Step 1: Write the failing test**

```python
from jobharbor.config import load_yaml_config

def test_yaml_loader_reads_scan_interval(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("scan_interval_hours: 2\ninclude_domain_keywords: [android]")
    config = load_yaml_config(path)
    assert config.scan_interval_hours == 2
    assert "android" in config.include_domain_keywords
```

**Step 2: Run the test to confirm failure**

`./.venv/bin/pytest tests/test_yaml_config.py::test_yaml_loader_reads_scan_interval -q`
Expected: FAIL, `load_yaml_config` undefined or missing behavior.

**Step 3: Implement the YAML loader**

```python
import yaml
from dataclasses import dataclass

@dataclass
class YamlConfig:
    scan_interval_hours: int | None = None
    include_domain_keywords: list[str] | None = None
    # ... other optional fields

def load_yaml_config(path: Path) -> YamlConfig:
    with open(path, "r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh)
    return YamlConfig(**(payload or {}))
```

**Step 4: Run the test to verify it passes**

`./.venv/bin/pytest tests/test_yaml_config.py::test_yaml_loader_reads_scan_interval -q`
Expected: PASS.

**Step 5: Commit**

```
git add src/jobharbor/config_schema.py src/jobharbor/config.py tests/test_yaml_config.py
git commit -m "feat: add yaml config loader"
```

### Task 2: Integrate YAML values into Settings + scheduler

**Files:**
- Modify: `src/jobharbor/config.py`
- Modify: `src/jobharbor/main.py:1-60`
- Test: `tests/test_main_scheduler_config.py`

**Step 1: Write failing test**

```python
from jobharbor.main import app

def test_yaml_config_applies_scan_interval(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("scan_interval_hours: 3")
    monkeypatch.setenv("JOBHARBOR_CONFIG_PATH", str(config))
    settings = Settings()
    assert settings.scan_interval_hours == 3
```

**Step 2: Run test to confirm failure**

`./.venv/bin/pytest tests/test_main_scheduler_config.py::test_yaml_config_applies_scan_interval -q`
Expected: FAIL because `JOBHARBOR_CONFIG_PATH` ignored.

**Step 3: Implement integration**

1. Update `Settings` to optionally load `load_yaml_config(Path(os.getenv("JOBHARBOR_CONFIG_PATH", "")))` and override defaults.
2. Adjust `main.py` startup to accept the combined settings when bootstrapping the scheduler (pass through to `run_scan_cycle` if needed).

**Step 4: Run the test to ensure PASS**

`./.venv/bin/pytest tests/test_main_scheduler_config.py::test_yaml_config_applies_scan_interval -q`
Expected: PASS.

**Step 5: Commit**

```
git add src/jobharbor/config.py src/jobharbor/main.py tests/test_main_scheduler_config.py
git commit -m "feat: wire yaml config into scheduler"
```

### Task 3: Provide helper script + documentation

**Files:**
- Create: `scripts/apply_config.py`
- Modify: `README.md`
- Test: `n/a (manual verification)`

**Step 1: Write the failing test**

*(Document that this task is manual; no automated test yet.)*

**Step 2: N/A**

**Step 3: Implement helper**

1. The script reads `config.yaml`, verifies required keys (`scan_interval_hours`, `include_domain_keywords`, etc.), and prints “Config valid”; optionally copies values into `.env`.
2. Document the workflow in `README.md` under “Homelab Deployment” or a new “Configuration” section, showing sample `config.yaml` and how to run the script before `docker compose up`.

**Step 4: Manual verification**

Run `python scripts/apply_config.py config.yaml` with a sample file; expect “Config valid”.

**Step 5: Commit**

```
git add scripts/apply_config.py README.md
git commit -m "docs: describe yaml config usage"
```

