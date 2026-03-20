# Auto-Discovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Auto-discover and persist job openings without manual company slug input, including openings with arbitrary apply URLs.

**Architecture:** Add a feed-driven auto-discovery service and a concrete discover stage worker. Persist new jobs by source/external_id, and enrich with existing connectors when provider slugs are extracted from discovered URLs.

**Tech Stack:** Python 3.12, SQLModel, pytest.

---

### Task 1: Add failing tests for auto-discovery service and discover stage

**Files:**
- Create: `tests/test_auto_discovery.py`
- Create: `tests/test_discover_stage.py`

### Task 2: Implement auto-discovery service and discover stage worker

**Files:**
- Create: `src/jobharbor/services/auto_discovery.py`
- Create: `src/jobharbor/workers/discover_stage.py`

### Task 3: Wire discover stage into runtime pipeline

**Files:**
- Modify: `src/jobharbor/runner.py`

### Task 4: Verify behavior

**Files:**
- Test: `tests/test_auto_discovery.py`
- Test: `tests/test_discover_stage.py`
- Test: `tests/test_discovery_service.py`
- Test: `tests/test_pipeline_e2e_smoke.py`
