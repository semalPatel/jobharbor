# Email Ready-for-Review Notifications Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Send an email notification when an application reaches `ready_for_review` and avoid repeat sends for the same application.

**Architecture:** Add a concrete notify stage to the runtime pipeline that reads ready-for-review applications from the repository and sends notifications through the existing notification router configured for email provider. Persist idempotency using `run_logs` (`source=notify:application:<id>`) so repeated scan cycles skip already-notified applications without requiring schema migrations.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, pytest.

---

### Task 1: Add failing tests for notify stage behavior

**Files:**
- Create: `tests/test_notify_stage.py`
- Modify: none
- Test: `tests/test_notify_stage.py`

### Task 2: Implement notify stage and pipeline wiring

**Files:**
- Create: `src/jobharbor/workers/notify_stage.py`
- Modify: `src/jobharbor/runner.py`
- Test: `tests/test_notify_stage.py`

### Task 3: Verify end-to-end test pass for touched areas

**Files:**
- Modify: none
- Test: `tests/test_notify_stage.py`, `tests/test_pipeline_e2e_smoke.py`, `tests/test_main_scheduler_config.py`
